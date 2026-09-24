"""
bgy_scanners/bgy_scanner_day.py - Scanner diurno per il tabellone SACBO.
Versione 2.5.1
- URL, timeout, attese, scroll, user-agent: da config_data.json (scanner_day)
- Naming file: scan_YYYY-MM-DD_HH-MM.csv (via bgy_dates)

Fix v2.5.1:
- Il click sul tab "Arrivi" è ora esplicito. Playwright navigava all'URL
  con #arrivals ma il JavaScript del sito non attivava la tab, quindi
  venivano estratti solo i dati della tab "Partenze" (default).
- Aggiunto fallback: se il click sul tab fallisce, prova l'URL diretto
  con #arrivals e attende un tempo maggiore.
- Aggiunta diagnostica: logga quanti voli sono stati estratti per ogni tab.
"""
import os
import re
import sys
import pandas as pd
from datetime import datetime
from playwright.sync_api import sync_playwright

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


def _click_arrivals_tab(page):
    """
    Prova a cliccare il tab 'Arrivi' con diversi selettori.
    Ritorna True se il click è riuscito.
    """
    # Candidati: testo visibile del tab (italiano + inglese)
    candidates = [
        "Arrivi", "ARRIVI", "arrivi",
        "Arrivals", "ARRIVALS", "arrivals",
        "Arrivo", "Arrivo",
    ]

    for text in candidates:
        try:
            # Prova: link o button con questo testo esatto
            loc = page.get_by_role("link", name=re.compile(text, re.IGNORECASE))
            if loc.count() > 0:
                loc.first.click(timeout=5000)
                logger.info(f"🖱️ Click su tab 'Arrivi' (role=link, text={text})")
                page.wait_for_timeout(3000)
                return True
        except Exception:
            pass

        try:
            loc = page.get_by_role("button", name=re.compile(text, re.IGNORECASE))
            if loc.count() > 0:
                loc.first.click(timeout=5000)
                logger.info(f"🖱️ Click su tab 'Arrivi' (role=button, text={text})")
                page.wait_for_timeout(3000)
                return True
        except Exception:
            pass

        try:
            # Fallback: cerca un elemento <a> o <li> con questo testo
            loc = page.locator(f"a:has-text('{text}'), li:has-text('{text}'), "
                               f"div[role='tab']:has-text('{text}')")
            if loc.count() > 0:
                loc.first.click(timeout=5000)
                logger.info(f"🖱️ Click su tab 'Arrivi' (selettore generico, text={text})")
                page.wait_for_timeout(3000)
                return True
        except Exception:
            pass

    logger.warning("⚠️ Nessun elemento 'Arrivi' trovato, provo con URL diretto")
    return False


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

    logger.info("🚀 Avvio Playwright...")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=ua)
            page = context.new_page()

            for entry in urls:
                try:
                    url, mov_type = entry
                except (ValueError, TypeError):
                    logger.warning(f"URL malformato in config: {entry}")
                    continue

                try:
                    logger.info(f"📡 Accesso ({mov_type})...")

                    # === STRATEGIA 1: naviga all'URL base, poi clicca il tab ===
                    base_url = url.split("#")[0]
                    page.goto(base_url, wait_until="networkidle", timeout=timeout)
                    page.wait_for_timeout(wait_load)

                    is_arrivals = "arriv" in url.lower() or "atterra" in mov_type.lower()

                    if is_arrivals:
                        # Prova il click sul tab "Arrivi"
                        clicked = _click_arrivals_tab(page)
                        if not clicked:
                            # === STRATEGIA 2: naviga direttamente all'URL con fragment ===
                            logger.info(f"🔄 Fallback: navigo a {url}")
                            page.goto(url, wait_until="networkidle", timeout=timeout)
                            page.wait_for_timeout(wait_load + 3000)

                    # Scroll per caricare tutti i voli
                    page.evaluate(f"window.scrollBy(0, {scroll_px})")
                    page.wait_for_timeout(wait_scroll)

                    # Estrai il testo
                    body_text = page.inner_text("body")
                    parsed = parse_flight_text(body_text, mov_type)

                    # Diagnostica: verifica che i voli estratti abbiano il tipo giusto
                    if parsed:
                        # Conta quanti hanno mov_type = 'A' (se siamo su arrivals)
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


def run_scan():
    """Esegue la scansione diurna."""
    logger.info("🚀 Avvio scansione diurna...")
    os.makedirs(RAW_DIR, exist_ok=True)

    df = fetch_board_data()
    if df.empty:
        logger.error("❌ Nessun dato acquisito")
        return None

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

    # Diagnostica finale
    n_d = len(df[df['tipo_movimento'] == 'D'])
    n_a = len(df[df['tipo_movimento'] == 'A'])
    logger.info(f"✅ Scansione completata: {len(df)} voli (D={n_d}, A={n_a})")
    return out_file


if __name__ == "__main__":
    run_scan()