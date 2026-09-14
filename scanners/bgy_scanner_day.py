"""
scanners/bgy_scanner_day.py - Scanner diurno per il tabellone SACBO.
"""
import os
import re
import pandas as pd
from datetime import datetime
from playwright.sync_api import sync_playwright

from core.bgy_logger import get_logger
from core.bgy_paths import RAW_DIR
from core.bgy_retry import retry_on_failure

logger = get_logger("ScannerDay")


def parse_flight_text(raw_text, movement_type):
    """Estrae i voli dal testo grezzo del tabellone."""
    flights = []
    clean_text = re.sub(r'\s+', ' ', raw_text)
    
    pattern = r'([A-Z0-9]{2,4}\s?\d{1,4})\s*([A-Z\s\-\/\.]{2,35}?)\s*\d{2}/\d{2}/\d{4}\s+(\d{2}:\d{2})\s*\d{2}/\d{2}/\d{4}\s+(\d{2}:\d{2})(.*?)(?=[A-Z0-9]{2,4}\s?\d{1,4}|$)'
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


@retry_on_failure(max_retries=3, delay=2)
def fetch_board_data():
    """Acquisisce i dati del tabellone usando Playwright."""
    all_flights = []
    urls = [
        ("https://www.milanbergamoairport.it/it/voli-tempo-reale/#departure", "Decollo"),
        ("https://www.milanbergamoairport.it/it/voli-tempo-reale/#arrivals", "Atterraggio")
    ]
    
    logger.info("🚀 Avvio Playwright...")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = context.new_page()
            
            for url, mov_type in urls:
                try:
                    logger.info(f"📡 Accesso ({mov_type})...")
                    page.goto(url, wait_until="networkidle", timeout=40000)
                    page.wait_for_timeout(3000)
                    page.evaluate("window.scrollBy(0, 1500)")
                    page.wait_for_timeout(2000)
                    
                    parsed = parse_flight_text(page.inner_text("body"), mov_type)
                    if parsed:
                        all_flights.extend(parsed)
                        logger.info(f"✅ Estratti {len(parsed)} {mov_type}")
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
    df = df.drop_duplicates(subset=['callsign_volo', 'orario_schedulato'], keep='first')
    if len(df) < before:
        logger.info(f"🗑️ Rimossi {before - len(df)} duplicati")
    
    now = datetime.now()
    df['scan_timestamp'] = now.strftime("%Y-%m-%d %H:%M:%S")
    
    out_file = os.path.join(RAW_DIR, f"scan_{now.strftime('%Y%m%d_%H%M')}.csv")
    df.to_csv(out_file, index=False, encoding="utf-8-sig")
    
    logger.info(f"✅ Scansione completata: {len(df)} voli")
    return out_file


if __name__ == "__main__":
    run_scan()