"""
bgy_scanners/bgy_scanner_day.py - Scanner diurno per il tabellone SACBO.
Versione 2.6.0

- URL, timeout, attese, scroll, user-agent: da config_data.json (scanner_day)
- Naming file: scan_YYYY-MM-DD_HH-MM.csv (via bgy_dates)
- Failover automatico su Avionio se SACBO è irraggiungibile (Cloudflare)

Novità v2.6.0 (failover SACBO → Avionio):
- Se Cloudflare blocca lo scanner dopo il retry di fetch_board_data(),
  il sistema chiama fetch_as_scan_rows() di bgy_scanner_alt e produce
  un scan_*.csv equivalente, con fonte_scan='avionio'.
- Aggiunta colonna fonte_scan in scan_*.csv (valori: 'sacbo' | 'avionio').
- scanner_day_status.json include ora il campo fonte_scan.
- Il messaggio finale del check 9 distingue le due fonti.
- Il fallback copre solo le prossime 4-6 ore di voli (limite Avionio),
  quindi l'email di stato avverte se la copertura è parziale.

Novità v2.5.9 (recupero scansioni mancate):
- run_scan() accetta parametri is_recovery e recovered_slot.

Novità v2.5.8 (screenshot full-board):
- _capture_screenshot() cattura l'INTERO tabellone, non solo il viewport.

Novità v2.5.7 (screenshot puliti):
- _hide_extra_elements() nasconde via JS gli elementi estranei al tabellone.

Novità v2.5.4 (diagnostica Cloudflare):
- Lo scanner scrive bgy_data/bgy_logs/scanner_day_status.json.

Fix v2.5.3:
- Stealth mode con playwright-stealth v2.0.0+ (classe Stealth).

Fix v2.5.2:
- Safety net in run_scan() contro duplicazione D/A.

Fix v2.5.1:
- Click esplicito sul tab "Arrivi".
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

# Numero di tentativi massimi su SACBO prima di passare ad Avionio.
# Ogni tentativo è ~5 minuti di Chromium. Non alzare oltre 2 senza motivo.
MAX_SACBO_ATTEMPTS = 2


_scan_status = {
    "timestamp": None,
    "challenge_superato": False,
    "tab_arrivi_cliccato": False,
    "body_arrivi_cambiato": False,
    "n_decolli": 0,
    "n_arrivi": 0,
    "screenshot_dep": None,
    "screenshot_arr": None,
    "is_recovery": False,
    "recovered_slot": None,
    "fonte_scan": "sacbo",
    "fallback_attivato": False,
    "messaggio": "",
}


def _reset_scan_status(is_recovery=False, recovered_slot=None):
    _scan_status["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _scan_status["challenge_superato"] = False
    _scan_status["tab_arrivi_cliccato"] = False
    _scan_status["body_arrivi_cambiato"] = False
    _scan_status["n_decolli"] = 0
    _scan_status["n_arrivi"] = 0
    _scan_status["screenshot_dep"] = None
    _scan_status["screenshot_arr"] = None
    _scan_status["is_recovery"] = bool(is_recovery)
    _scan_status["recovered_slot"] = recovered_slot
    _scan_status["fonte_scan"] = "sacbo"
    _scan_status["fallback_attivato"] = False
    _scan_status["messaggio"] = (
        f"Recupero scansione {recovered_slot} in corso"
        if is_recovery else "Scansione avviata"
    )


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
    """Rimuove banner cookie e modal di avviso che intercettano i click."""
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
    """Nasconde via JS gli elementi che non fanno parte del tabellone."""
    try:
        hidden = page.evaluate("""
            () => {
                let count = 0;
                const HIDE_STYLE = 'display: none !important;';
                function hasBigTable(el) {
                    const rows = el.querySelectorAll('table tr');
                    return rows.length > 5;
                }
                function tryHide(el) {
                    if (!el || el === document.body || el === document.documentElement) return false;
                    if (el.dataset && el.dataset.bgyHidden === '1') return false;
                    if (hasBigTable(el)) return false;
                    el.style.cssText += ';' + HIDE_STYLE;
                    el.dataset.bgyHidden = '1';
                    count++;
                    return true;
                }
                const keywords = [
                    'cerca un volo', 'cerca volo', 'for example',
                    'trasporti via terra', 'lavora con noi', 'bgy sostenibile',
                ];
                const tagSelector = 'div, section, aside, form, nav, article, header, span, p';
                document.querySelectorAll(tagSelector).forEach(el => {
                    const text = (el.innerText || '').toLowerCase().slice(0, 300);
                    for (const kw of keywords) {
                        if (text.includes(kw)) { tryHide(el); return; }
                    }
                });
                const placeholderHints = ['example', 'esempio', 'fr 9429', 'mad'];
                document.querySelectorAll('input').forEach(input => {
                    const ph = (input.placeholder || '').toLowerCase();
                    if (!placeholderHints.some(h => ph.includes(h))) return;
                    let el = input;
                    for (let i = 0; i < 6 && el.parentElement; i++) {
                        el = el.parentElement;
                        if (el.offsetWidth > 600 || el.tagName === 'FORM' || el.tagName === 'SECTION') {
                            if (tryHide(el)) return;
                        }
                    }
                    if (el && el.parentElement) tryHide(el.parentElement);
                });
                const classSelectors = [
                    '[class*="search-box"]', '[class*="searchBox"]',
                    '[class*="search_box"]', '[class*="flight-search"]',
                    '[class*="flightSearch"]', '[class*="cerca-volo"]',
                    '[class*="cercaVolo"]', '.c-search', '.search-flight',
                ];
                classSelectors.forEach(sel => {
                    try {
                        document.querySelectorAll(sel).forEach(el => tryHide(el));
                    } catch (e) { }
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
    """Prova a cliccare il tab 'Arrivi'."""
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
    """Cattura uno screenshot dell'INTERO tabellone (non solo il viewport)."""
    try:
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        is_arrivals = 'atterra' in movement_type.lower()
        prefix = "board_arr" if is_arrivals else "board_dep"
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"{prefix}_{ts}.png"
        filepath = os.path.join(SCREENSHOTS_DIR, filename)

        _hide_extra_elements(page)
        page.wait_for_timeout(500)

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

        if not captured:
            try:
                table = page.locator("table").first
                if table.count() > 0:
                    table.screenshot(path=filepath)
                    logger.info(f"📸 Screenshot (prima table): {filename}")
                    captured = True
            except Exception as e:
                logger.debug(f"Fallback table fallito: {str(e)[:80]}")

        if not captured:
            try:
                page.screenshot(path=filepath, full_page=True)
                logger.info(f"📸 Screenshot (full_page): {filename}")
                captured = True
            except Exception as e:
                logger.warning(f"Errore screenshot full_page: {e}")

        return filepath if captured else None
    except Exception as e:
        logger.warning(f"Errore screenshot ({movement_type}): {e}")
        return None


@retry_on_failure(max_retries=1, delay=2)
def fetch_board_data():
    """
    Acquisisce i dati del tabellone usando Playwright.

    Ritorna un DataFrame vuoto se:
      - Il challenge Cloudflare non viene superato (fallback ad Avionio).
      - Nessun volo viene estratto dal tabellone (no fallback).

    Lo stato del challenge è registrato in _scan_status['challenge_superato'].
    """
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

            challenge_failed_all = True

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

                    challenge_failed_all = False
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
                            page, fp_before, max_wait_ms=10000, poll_ms=500
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

            if challenge_failed_all:
                _scan_status["challenge_superato"] = False
                logger.error("❌ Challenge Cloudflare fallito per tutte le URL")

    except Exception as e:
        logger.error(f"Errore Playwright: {e}")
        _scan_status["messaggio"] = f"Errore Playwright: {str(e)[:120]}"

    return pd.DataFrame(all_flights) if all_flights else pd.DataFrame()


def _sanity_check_d_a(df):
    """Safety net: se D e A hanno lo stesso set, scarta gli A."""
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


def _fallback_to_avionio():
    """
    Fallback quando SACBO è irraggiungibile.
    Chiama bgy_scanner_alt.fetch_as_scan_rows() e ritorna un DataFrame
    nel formato di scan_*.csv, con fonte_scan='avionio'.
    """
    logger.warning("🔄 SACBO non disponibile, attivo fallback Avionio...")
    try:
        from bgy_scanners.bgy_scanner_alt import fetch_as_scan_rows
        rows = fetch_as_scan_rows()
        if not rows:
            logger.error("❌ Fallback Avionio: nessun dato disponibile")
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        _scan_status["fonte_scan"] = "avionio"
        _scan_status["fallback_attivato"] = True
        logger.info(f"✅ Fallback Avionio: {len(df)} voli recuperati")
        return df
    except Exception as e:
        logger.error(f"❌ Errore fallback Avionio: {e}")
        return pd.DataFrame()


def _componi_messaggio_finale(n_d, n_a):
    """Compone il messaggio human-readable per l'email di stato."""
    prefix = "Recupero scanner diurno" if _scan_status.get("is_recovery") else "Scanner diurno"
    fonte = _scan_status.get("fonte_scan", "sacbo")

    if fonte == "avionio":
        return (f"{prefix} OK da FONTE ALTERNATIVA (Avionio) "
                f"({n_d} D + {n_a} A) — copertura parziale")

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
    return f"{prefix} OK ({n_d} D + {n_a} A)"


def run_scan(is_recovery=False, recovered_slot=None):
    """
    Esegue la scansione diurna.

    Flusso:
      1. Tenta SACBO (fetch_board_data, con retry interno).
      2. Se il challenge Cloudflare fallisce, tenta di nuovo (fino a
         MAX_SACBO_ATTEMPTS tentativi totali).
      3. Se tutti i tentativi SACBO falliscono, chiama _fallback_to_avionio().
      4. Salva scan_*.csv con la colonna fonte_scan corretta.

    Parametri:
      - is_recovery (bool): True se questa è una scansione di recupero.
      - recovered_slot (str): slot originale mancato (YYYY-MM-DD HH:MM).
    """
    if is_recovery:
        logger.info(f"🚀 Avvio scansione diurna (RECUPERO di {recovered_slot})...")
    else:
        logger.info("🚀 Avvio scansione diurna...")

    os.makedirs(RAW_DIR, exist_ok=True)
    _reset_scan_status(is_recovery=is_recovery, recovered_slot=recovered_slot)

    try:
        df = pd.DataFrame()
        sacbo_attempts = 0

        while sacbo_attempts < MAX_SACBO_ATTEMPTS and df.empty:
            sacbo_attempts += 1
            logger.info(f"📡 Tentativo SACBO {sacbo_attempts}/{MAX_SACBO_ATTEMPTS}...")
            df = fetch_board_data()

            if not df.empty:
                break

            # Se il challenge è stato superato ma non ci sono voli,
            # è un problema diverso (tabella vuota). Non ritentare.
            if _scan_status.get("challenge_superato"):
                logger.warning(
                    "⚠️ Challenge superato ma nessun volo estratto. "
                    "Non ritento (possibile tabella vuota)."
                )
                break

            logger.warning(
                f"⚠️ Tentativo {sacbo_attempts}/{MAX_SACBO_ATTEMPTS} fallito "
                f"(Cloudflare non superato)"
            )

        # Fallback ad Avionio se tutti i tentativi SACBO hanno fallito
        if df.empty and not _scan_status.get("challenge_superato"):
            df = _fallback_to_avionio()

        if df.empty:
            logger.error("❌ Nessun dato acquisito né da SACBO né da Avionio")
            _write_scan_status("Nessun dato acquisito dal tabellone né da Avionio")
            return None

        # Assicura che la colonna fonte_scan esista
        if "fonte_scan" not in df.columns:
            df["fonte_scan"] = _scan_status.get("fonte_scan", "sacbo")

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

        logger.info(f"✅ Scansione completata: {len(df)} voli "
                    f"(D={n_d}, A={n_a}, fonte={_scan_status['fonte_scan']})")
        _write_scan_status()
        return out_file

    except Exception as e:
        logger.error(f"❌ Errore durante la scansione: {e}")
        _write_scan_status(f"Errore imprevisto: {str(e)[:120]}")
        raise


if __name__ == "__main__":
    run_scan()