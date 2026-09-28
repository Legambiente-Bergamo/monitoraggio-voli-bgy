"""
bgy_scanners/bgy_scanner_day.py - Scanner diurno per il tabellone SACBO.
Versione 2.5.8

- URL, timeout, attese, scroll, user-agent: da config_data.json (scanner_day)
- Naming file: scan_YYYY-MM-DD_HH-MM.csv (via bgy_dates)

Novità v2.5.8 (screenshot puliti):
- _hide_extra_elements() migliorato: target più aggressivo per il box
  "Cerca un volo" che era rimasto visibile.
  Strategie:
    1. Keyword match su più tag (div, section, aside, form, nav,
       article, span, header)
    2. Targeting via input placeholder ("FOR EXAMPLE", "esempio", ecc.)
    3. Targeting via classi comuni (search-box, flight-search, ecc.)
    4. Override con display:none !important per vincere su CSS
- Esclude dalla rimozione gli elementi che contengono una <table> con
  più di 5 righe (sono wrapper del tabellone, non nasconderli).

Novità v2.5.7 (screenshot puliti):
- Aggiunta _hide_extra_elements(page) che nasconde via JS gli elementi
  estranei al tabellone (box "Cerca un volo", fasce di navigazione,
  banner) prima di catturare lo screenshot.

Novità v2.5.6 (screenshot full-board):
- _capture_screenshot() ora cattura l'INTERO tabellone, non solo la
  porzione di viewport. Strategia a cascata:
    1. Cerca il selettore specifico del tab (#arr-table / #dep-table)
    2. Fallback: la prima <table> della pagina
    3. Fallback finale: full_page=True (tutta la pagina)

Novità v2.5.5 (screenshot):
- Ad ogni scansione vengono salvati due screenshot del tabellone:
    bgy_data/bgy_screenshots/board_dep_YYYY-MM-DD_HH-MM.png
    bgy_data/bgy_screenshots/board_arr_YYYY-MM-DD_HH-MM.png
- I path degli screenshot vengono aggiunti a scanner_day_status.json.

Novità v2.5.4 (diagnostica Cloudflare):
- Lo scanner scrive bgy_data/bgy_logs/scanner_day_status.json al termine
  di ogni scansione, con:
    * challenge_superato (bool)
    * tab_arrivi_cliccato (bool)
    * body_arrivi_cambiato (bool)
    * n_decolli, n_arrivi (int)
    * screenshot_dep, screenshot_arr (str o null)
    * messaggio (str, human-readable)
- Il file viene scritto anche in caso di errore/eccezione, così il check 9
  nell'email di stato può segnalare il problema.
- Nessun auto-fix: la diagnostica rileva e notifica, non ripara.

Fix v2.5.3:
- Aggiunto stealth mode con playwright-stealth v2.0.0+ (classe Stealth).
  Il sito SACBO è protetto da Cloudflare; senza stealth la pagina viene
  bloccata e il tab "Arrivi" non è cliccabile.
- Aggiunta rimozione overlay (banner cookie iubenda + alert-popup)
  prima del click sul tab "Arrivi". Senza questa rimozione, gli overlay
  intercettano i click e il tab non viene attivato.
- Verifica del cambio di contenuto dopo il click tramite fingerprint
  del body (md5). Se il body non cambia, gli arrivi vengono scartati.

Fix v2.5.2:
- Safety net in run_scan(): se D e A hanno lo stesso set di
  (callsign, orario), gli A vengono scartati e viene loggato un WARNING.

Fix v2.5.1:
- Il click sul tab "Arrivi" è ora esplicito.
- Fallback URL diretto se il click fallisce.
- Diagnostica: logga quanti voli sono stati estratti per ogni tab.
"""
import os
import re
import sys
import json
import hashlib
import pandas as pd
from datetime import datetime
from playwright.sync_api import sync_playwright

try:
    from playwright_stealth import Stealth
    _STEALTH_AVAILABLE = True
except ImportError:
    Stealth = None
    _STEALTH_AVAILABLE = False

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import RAW_DIR, LOGS_DIR
from bgy_core.bgy_retry import retry_on_failure
from bgy_core.bgy_config_manager import config_manager
from bgy_core.bgy_dates import scan_filename

logger = get_logger("ScannerDay")

STATUS_FILE = os.path.join(LOGS_DIR, "scanner_day_status.json")
SCREENSHOTS_DIR = os.path.join(os.path.dirname(LOGS_DIR), "bgy_screenshots")


_scan_status = {
    "timestamp": None,
    "challenge_superato": False,
    "tab_arrivi_cliccato": False,
    "body_arrivi_cambiato": False,
    "n_decolli": 0,
    "n_arrivi": 0,
    "screenshot_dep": None,
    "screenshot_arr": None,
    "messaggio": "",
}


def _reset_scan_status():
    _scan_status["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _scan_status["challenge_superato"] = False
    _scan_status["tab_arrivi_cliccato"] = False
    _scan_status["body_arrivi_cambiato"] = False
    _scan_status["n_decolli"] = 0
    _scan_status["n_arrivi"] = 0
    _scan_status["screenshot_dep"] = None
    _scan_status["screenshot_arr"] = None
    _scan_status["messaggio"] = "Scansione avviata"


def _write_scan_status(messaggio_finale=None):
    """Scrive lo stato su disco. Non solleva eccezioni."""
    try:
        if messaggio_finale:
            _scan_status["messaggio"] = messaggio_finale

        os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(_scan_status, f, indent=2, ensure_ascii=False)

        logger.info(f"📝 Status scanner scritto: {STATUS_FILE}")
    except Exception as e:
        logger.error(f"❌ Errore scrittura status scanner: {e}")


def _cfg():
    return config_manager.get_scanner_day_config()


def parse_flight_text(raw_text, movement_type):
    """Estrae i voli dal testo grezzo del tabellone."""
    flights = []
    clean_text = re.sub(r'\s+', ' ', raw_text)

    pattern = (r'([A-Z0-9]{2,4}\s?\d{1,4})\s*([A-Z\s\-\/\.]{2,35}?)\s*'
               r'\d{2}/\d{2}/\d{4}\s+(\d{2}:\d{2})\s*'
               r'\d{2}/\d{2}/\d{4}\s+(\d{2}:\d{2})(.*?)'
               r'(?=[A-Z0-9]{2,4}\s?\d{1,4}|$)')
    matches = re.findall(pattern, clean_text, re.DOTALL)

    for match in matches:
        try:
            flight_num = match[0].strip()
            dest_orig = re.sub(r'\d{2}/\d{2}/\d{4}', '', match[1].strip()).strip()
            sched_time = match[2].strip()
            actual_time = match[3].strip()
            status = match[4].strip() or "Operativo"
            mov_type = 'A' if 'atterraggio' in movement_type.lower() else 'D'

            flights.append({
                "callsign_volo": flight_num,
                "tipo_movimento": mov_type,
                "destinazione_origine": dest_orig,
                "orario_schedulato": sched_time,
                "orario_effettivo": actual_time,
                "stato_volo": status
            })
        except Exception as e:
            logger.warning(f"Errore parsing: {e}")
            continue

    return flights


def _body_fingerprint(page):
    """Restituisce un hash del body corrente, per rilevare cambi di contenuto."""
    try:
        text = page.inner_text("body")
        return hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()
    except Exception:
        return None


def _dismiss_overlays(page):
    """
    Rimuove banner cookie e modal di avviso che intercettano i click.
    Ritorna il numero di overlay rimossi.
    """
    try:
        removed = page.evaluate("""
            () => {
                let count = 0;
                const selectors = [
                    '#iubenda-cs-banner',
                    '.iubenda-cs-banner',
                    '#alert-popup',
                    '.modal-backdrop',
                    '.modal.show',
                    '.modal.fade.in',
                ];
                for (const sel of selectors) {
                    document.querySelectorAll(sel).forEach(el => {
                        el.remove();
                        count++;
                    });
                }
                document.body.classList.remove('modal-open');
                document.body.style.overflow = '';
                document.body.style.paddingRight = '';
                return count;
            }
        """)
        if removed > 0:
            logger.info(f"🧹 Rimossi {removed} overlay (cookie banner/modal)")
        return removed
    except Exception as e:
        logger.warning(f"Errore rimozione overlay: {e}")
        return 0


def _hide_extra_elements(page):
    """
    Nasconde via JS gli elementi che non fanno parte del tabellone:
    box di ricerca, banner, fasce di navigazione.

    Strategie combinate:
      1. Keyword match su molti tag HTML
      2. Targeting via input placeholder (FOR EXAMPLE, esempio, ecc.)
      3. Targeting via classi comuni (search-box, flight-search, ecc.)
      4. Override con display:none !important

    Esclude dalla rimozione gli elementi che contengono una <table> con
    più di 5 righe (sono wrapper del tabellone, non vanno nascosti).

    Ritorna il numero di elementi nascosti.
    """
    try:
        hidden = page.evaluate("""
            () => {
                let count = 0;
                const HIDE_STYLE = 'display: none !important;';

                // Helper: un elemento contiene una tabella "grande"?
                function hasBigTable(el) {
                    const rows = el.querySelectorAll('table tr');
                    return rows.length > 5;
                }

                // Helper: nascondi un elemento se non contiene una tabella grande
                function tryHide(el) {
                    if (!el || el === document.body || el === document.documentElement) return false;
                    if (el.dataset && el.dataset.bgyHidden === '1') return false;
                    if (hasBigTable(el)) return false;
                    el.style.cssText += ';' + HIDE_STYLE;
                    el.dataset.bgyHidden = '1';
                    count++;
                    return true;
                }

                // === Strategia 1: keyword match su molti tag ===
                const keywords = [
                    'cerca un volo',
                    'cerca volo',
                    'for example',
                    'trasporti via terra',
                    'lavora con noi',
                    'bgy sostenibile',
                ];
                const tagSelector = 'div, section, aside, form, nav, article, header, span, p';

                document.querySelectorAll(tagSelector).forEach(el => {
                    const text = (el.innerText || '').toLowerCase().slice(0, 300);
                    for (const kw of keywords) {
                        if (text.includes(kw)) {
                            tryHide(el);
                            return;
                        }
                    }
                });

                // === Strategia 2: targeting via input placeholder ===
                const placeholderHints = ['example', 'esempio', 'fr 9429', 'mad'];
                document.querySelectorAll('input').forEach(input => {
                    const ph = (input.placeholder || '').toLowerCase();
                    if (!placeholderHints.some(h => ph.includes(h))) return;

                    // Risali fino a un contenitore ragionevolmente ampio
                    let el = input;
                    for (let i = 0; i < 6 && el.parentElement; i++) {
                        el = el.parentElement;
                        if (el.offsetWidth > 600 || el.tagName === 'FORM' || el.tagName === 'SECTION') {
                            if (tryHide(el)) return;
                        }
                    }
                    // Se non ha funzionato, nascondi il wrapper diretto
                    if (el && el.parentElement) tryHide(el.parentElement);
                });

                // === Strategia 3: classi comuni ===
                const classSelectors = [
                    '[class*="search-box"]',
                    '[class*="searchBox"]',
                    '[class*="search_box"]',
                    '[class*="flight-search"]',
                    '[class*="flightSearch"]',
                    '[class*="cerca-volo"]',
                    '[class*="cercaVolo"]',
                    '.c-search',
                    '.search-flight',
                ];
                classSelectors.forEach(sel => {
                    try {
                        document.querySelectorAll(sel).forEach(el => tryHide(el));
                    } catch (e) { /* selettore non valido, ignora */ }
                });

                return count;
            }
        """)
        if hidden > 0:
            logger.info(f"🧹 Nascosti {hidden} elementi estranei al tabellone")
        return hidden
    except Exception as e:
        logger.debug(f"Errore hide extra: {e}")
        return 0


def _click_arrivals_tab(page):
    """
    Prova a cliccare il tab 'Arrivi'.
    Ritorna True se il click è riuscito (a livello di click).
    """
    candidates = [
        "[role='tab']:has-text('Arrivi')",
        "a[href='#arr-table']",
        "a:has-text('Arrivi')",
        "text=Arrivi",
    ]

    for sel in candidates:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                loc.click(timeout=8000)
                logger.info(f"🖱️ Click su tab 'Arrivi' (selettore: {sel})")
                return True
        except Exception as e:
            logger.debug(f"Selettore '{sel}' fallito: {str(e)[:100]}")
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    loc.evaluate("el => el.click()")
                    logger.info(f"🖱️ Click JS su tab 'Arrivi' (selettore: {sel})")
                    return True
            except Exception:
                continue

    logger.warning("⚠️ Nessun elemento 'Arrivi' trovato")
    return False


def _wait_body_change(page, fingerprint_before, max_wait_ms=10000, poll_ms=500):
    """Aspetta che il body cambi rispetto al fingerprint dato."""
    if fingerprint_before is None:
        return True, _body_fingerprint(page)

    steps = max(1, max_wait_ms // poll_ms)
    for _ in range(steps):
        page.wait_for_timeout(poll_ms)
        fp = _body_fingerprint(page)
        if fp is not None and fp != fingerprint_before:
            return True, fp
    return False, _body_fingerprint(page)


def _capture_screenshot(page, movement_type):
    """
    Cattura uno screenshot dell'INTERO tabellone (non solo il viewport),
    dopo aver nascosto gli elementi estranei (box di ricerca, banner).

    Ritorna il path del file salvato, o None in caso di errore.
    """
    try:
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

        is_arrivals = 'atterra' in movement_type.lower()
        prefix = "board_arr" if is_arrivals else "board_dep"
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"{prefix}_{ts}.png"
        filepath = os.path.join(SCREENSHOTS_DIR, filename)

        # --- Nascondi elementi estranei prima dello screenshot ---
        _hide_extra_elements(page)
        page.wait_for_timeout(500)

        # --- Tentativo 1: selettore specifico del tab ---
        specific_selectors = (
            ["#arr-table", "div#arr-table", "table#arr-table"]
            if is_arrivals
            else ["#dep-table", "div#dep-table", "table#dep-table"]
        )

        captured = False

        for sel in specific_selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0:
                    loc.screenshot(path=filepath)
                    logger.info(f"📸 Screenshot (elemento '{sel}'): {filename}")
                    captured = True
                    break
            except Exception as e:
                logger.debug(f"Selettore '{sel}' fallito: {str(e)[:80]}")

        # --- Tentativo 2: la prima <table> della pagina ---
        if not captured:
            try:
                table = page.locator("table").first
                if table.count() > 0:
                    table.screenshot(path=filepath)
                    logger.info(f"📸 Screenshot (prima table): {filename}")
                    captured = True
            except Exception as e:
                logger.debug(f"Fallback table fallito: {str(e)[:80]}")

        # --- Tentativo 3: tutta la pagina (full_page) ---
        if not captured:
            try:
                page.screenshot(path=filepath, full_page=True)
                logger.info(f"📸 Screenshot (full_page): {filename}")
                captured = True
            except Exception as e:
                logger.warning(f"Errore screenshot full_page: {e}")

        if captured:
            return filepath
        return None

    except Exception as e:
        logger.warning(f"Errore screenshot ({movement_type}): {e}")
        return None


@retry_on_failure(max_retries=3, delay=2)
def fetch_board_data():
    """Acquisisce i dati del tabellone usando Playwright."""
    cfg = _cfg()
    all_flights = []
    urls = cfg.get("urls", [])
    timeout = cfg.get("playwright_timeout_ms", 40000)
    wait_load = cfg.get("wait_after_load_ms", 3000)
    wait_scroll = cfg.get("wait_after_scroll_ms", 2000)
    scroll_px = cfg.get("scroll_pixels", 1500)
    ua = cfg.get("user_agent", "Mozilla/5.0")

    if not _STEALTH_AVAILABLE:
        logger.warning("⚠️ playwright-stealth non disponibile. "
                       "Il sito SACBO potrebbe bloccare Playwright.")
        _scan_status["messaggio"] = "playwright-stealth non installato"

    logger.info("🚀 Avvio Playwright (stealth mode)...")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context = browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent=ua,
                locale="it-IT",
                timezone_id="Europe/Rome",
            )
            page = context.new_page()

            if _STEALTH_AVAILABLE:
                try:
                    Stealth().apply_stealth_sync(page)
                    logger.info("🥷 Stealth applicato")
                except Exception as e:
                    logger.warning(f"Impossibile applicare stealth: {e}")

            for entry in urls:
                try:
                    url, mov_type = entry
                except (ValueError, TypeError):
                    logger.warning(f"URL malformato in config: {entry}")
                    continue

                try:
                    logger.info(f"📡 Accesso ({mov_type})...")

                    is_arrivals = "arriv" in url.lower() or "atterra" in mov_type.lower()
                    base_url = url.split("#")[0]

                    page.goto(base_url, wait_until="domcontentloaded", timeout=timeout)
                    page.wait_for_timeout(wait_load)

                    # --- Attesa challenge Cloudflare ---
                    challenge_ok = False
                    for i in range(15):
                        title = page.title()
                        if "Just a moment" not in title and "Attention" not in title:
                            challenge_ok = True
                            logger.info(f"✅ Challenge Cloudflare superato dopo {i+1}s")
                            break
                        page.wait_for_timeout(1000)

                    if not challenge_ok:
                        logger.error("❌ Challenge Cloudflare NON superato (15s)")
                        _scan_status["messaggio"] = (
                            "Cloudflare ha bloccato lo scanner: challenge non superato in 15s"
                        )
                        continue

                    _scan_status["challenge_superato"] = True

                    _dismiss_overlays(page)
                    page.wait_for_timeout(1000)

                    if is_arrivals:
                        fp_before = _body_fingerprint(page)

                        clicked = _click_arrivals_tab(page)
                        if not clicked:
                            logger.warning(
                                "⚠️ Impossibile cliccare il tab 'Arrivi'. "
                                "Salto l'acquisizione degli arrivi."
                            )
                            _scan_status["messaggio"] = (
                                "Tab 'Arrivi' non cliccabile: possibile modifica "
                                "al sito SACBO"
                            )
                            continue

                        _scan_status["tab_arrivi_cliccato"] = True

                        changed, _ = _wait_body_change(
                            page, fp_before,
                            max_wait_ms=10000, poll_ms=500
                        )
                        if not changed:
                            logger.warning(
                                "⚠️ Il click sul tab 'Arrivi' NON ha cambiato "
                                "il contenuto della pagina."
                            )
                            _scan_status["messaggio"] = (
                                "Click su tab 'Arrivi' eseguito ma il contenuto "
                                "non è cambiato"
                            )
                            continue

                        _scan_status["body_arrivi_cambiato"] = True
                        logger.info("✅ Contenuto pagina cambiato dopo il click")

                    page.evaluate(f"window.scrollBy(0, {scroll_px})")
                    page.wait_for_timeout(wait_scroll)

                    # --- Screenshot del tabellone (v2.5.8) ---
                    screenshot_path = _capture_screenshot(page, mov_type)
                    if screenshot_path:
                        if is_arrivals:
                            _scan_status["screenshot_arr"] = screenshot_path
                        else:
                            _scan_status["screenshot_dep"] = screenshot_path

                    body_text = page.inner_text("body")
                    parsed = parse_flight_text(body_text, mov_type)

                    if parsed:
                        n_a = sum(1 for f in parsed if f.get('tipo_movimento') == 'A')
                        n_d = sum(1 for f in parsed if f.get('tipo_movimento') == 'D')
                        logger.info(
                            f"✅ Estratti {len(parsed)} voli da tab '{mov_type}' "
                            f"(D={n_d}, A={n_a})"
                        )
                        all_flights.extend(parsed)
                    else:
                        logger.warning(f"⚠️ Nessun volo estratto da tab '{mov_type}'")

                except Exception as e:
                    logger.error(f"Errore ({mov_type}): {e}")

            browser.close()
    except Exception as e:
        logger.error(f"Errore Playwright: {e}")
        _scan_status["messaggio"] = f"Errore Playwright: {str(e)[:120]}"

    return pd.DataFrame(all_flights) if all_flights else pd.DataFrame()


def _sanity_check_d_a(df):
    """
    Safety net: se D e A hanno lo stesso set di (callsign, orario_schedulato),
    gli 'arrivi' sono in realtà un duplicato delle partenze. Scarta gli A.
    """
    if df.empty:
        return df, False

    d_rows = df[df['tipo_movimento'] == 'D']
    a_rows = df[df['tipo_movimento'] == 'A']

    if d_rows.empty or a_rows.empty:
        return df, False

    d_set = set(zip(
        d_rows['callsign_volo'].astype(str),
        d_rows['orario_schedulato'].astype(str)
    ))
    a_set = set(zip(
        a_rows['callsign_volo'].astype(str),
        a_rows['orario_schedulato'].astype(str)
    ))

    if d_set == a_set:
        logger.warning(
            f"⚠️ SAFETY NET: D e A hanno lo stesso set di "
            f"(callsign, orario_schedulato) — {len(d_set)} coppie identiche. "
            f"Scarto {len(a_rows)} righe A."
        )
        df = df[df['tipo_movimento'] != 'A'].copy()
        return df, True

    return df, False


def _componi_messaggio_finale(n_d, n_a):
    """Compone il messaggio human-readable per l'email di stato."""
    if not _scan_status["challenge_superato"]:
        return "Cloudflare ha bloccato lo scanner: challenge non superato"

    if not _scan_status["tab_arrivi_cliccato"]:
        return "Tab 'Arrivi' non cliccabile: possibile modifica al sito SACBO"

    if not _scan_status["body_arrivi_cambiato"]:
        return "Click su tab 'Arrivi' eseguito ma il contenuto non è cambiato"

    if n_a == 0:
        return f"Nessun arrivo estratto (D={n_d}, A={n_a}): possibile modifica al tabellone"

    if n_d == 0:
        return f"Nessun decollo estratto (D={n_d}, A={n_a}): possibile modifica al tabellone"

    return f"Scanner diurno OK ({n_d} D + {n_a} A)"


def run_scan():
    """Esegue la scansione diurna."""
    logger.info("🚀 Avvio scansione diurna...")
    os.makedirs(RAW_DIR, exist_ok=True)
    _reset_scan_status()

    try:
        df = fetch_board_data()
        if df.empty:
            logger.error("❌ Nessun dato acquisito")
            _write_scan_status("Nessun dato acquisito dal tabellone")
            return None

        df, sanity_changed = _sanity_check_d_a(df)

        before = len(df)
        df = df.drop_duplicates(
            subset=['callsign_volo', 'orario_schedulato', 'tipo_movimento'],
            keep='first'
        )
        if len(df) < before:
            logger.info(f"🗑️ Rimossi {before - len(df)} duplicati")

        now = datetime.now()
        df['scan_timestamp'] = now.strftime("%Y-%m-%d %H:%M:%S")

        out_file = os.path.join(RAW_DIR, scan_filename(now))
        df.to_csv(out_file, index=False, encoding="utf-8-sig")

        n_d = len(df[df['tipo_movimento'] == 'D'])
        n_a = len(df[df['tipo_movimento'] == 'A'])

        _scan_status["n_decolli"] = int(n_d)
        _scan_status["n_arrivi"] = int(n_a)

        if sanity_changed:
            _scan_status["messaggio"] = (
                f"Safety net: gli arrivi erano duplicati delle partenze. "
                f"Scartati. (D={n_d}, A={n_a})"
            )
        else:
            _scan_status["messaggio"] = _componi_messaggio_finale(n_d, n_a)

        logger.info(f"✅ Scansione completata: {len(df)} voli (D={n_d}, A={n_a})")
        _write_scan_status()
        return out_file

    except Exception as e:
        logger.error(f"❌ Errore durante la scansione: {e}")
        _write_scan_status(f"Errore imprevisto: {str(e)[:120]}")
        raise


if __name__ == "__main__":
    run_scan()