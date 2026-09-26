"""
bgy_scanners/bgy_scanner_day.py - Scanner diurno per il tabellone SACBO.
Versione 2.5.3

- URL, timeout, attese, scroll, user-agent: da config_data.json (scanner_day)
- Naming file: scan_YYYY-MM-DD_HH-MM.csv (via bgy_dates)

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
- Il click sul tab "Arrivi" è ora esplicito (Playwright navigava all'URL
  con #arrivals ma il JavaScript non attivava la tab).
- Fallback URL diretto se il click fallisce.
- Diagnostica: logga quanti voli sono stati estratti per ogni tab.
"""
import os
import re
import sys
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
from bgy_core.bgy_paths import RAW_DIR
from bgy_core.bgy_retry import retry_on_failure
from bgy_core.bgy_config_manager import config_manager
from bgy_core.bgy_dates import scan_filename

logger = get_logger("ScannerDay")


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

                    for i in range(15):
                        title = page.title()
                        if "Just a moment" not in title and "Attention" not in title:
                            break
                        page.wait_for_timeout(1000)

                    _dismiss_overlays(page)
                    page.wait_for_timeout(1000)

                    if is_arrivals:
                        fp_before = _body_fingerprint(page)

                        clicked = _click_arrivals_tab(page)
                        if clicked:
                            changed, _ = _wait_body_change(
                                page, fp_before,
                                max_wait_ms=10000, poll_ms=500
                            )
                            if not changed:
                                logger.warning(
                                    "⚠️ Il click sul tab 'Arrivi' NON ha cambiato "
                                    "il contenuto della pagina. Salto l'acquisizione "
                                    "degli arrivi per evitare di duplicare le partenze."
                                )
                                continue
                            logger.info("✅ Contenuto pagina cambiato dopo il click")
                        else:
                            logger.warning(
                                "⚠️ Impossibile cliccare il tab 'Arrivi'. "
                                "Salto l'acquisizione degli arrivi."
                            )
                            continue

                    page.evaluate(f"window.scrollBy(0, {scroll_px})")
                    page.wait_for_timeout(wait_scroll)

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


def run_scan():
    """Esegue la scansione diurna."""
    logger.info("🚀 Avvio scansione diurna...")
    os.makedirs(RAW_DIR, exist_ok=True)

    df = fetch_board_data()
    if df.empty:
        logger.error("❌ Nessun dato acquisito")
        return None

    df, _ = _sanity_check_d_a(df)

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
    logger.info(f"✅ Scansione completata: {len(df)} voli (D={n_d}, A={n_a})")
    return out_file


if __name__ == "__main__":
    run_scan()