"""
bgy_tools/update_aircraft_db.py - DATA-34: Scarica e aggiorna il DB statico degli aerei da OpenSky.
Versione 1.0.0
"""
import os
import sys
import csv
import io
import zipfile
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_db import execute_query, execute_many, is_enabled
from bgy_core.bgy_config_manager import config_manager

logger = get_logger("UpdateAircraftDB")

OPENSKY_URL = "https://opensky-network.org/datasets/metadata/aircraftDatabase.csv"

def get_our_icao24s():
    """Recupera gli icao24 unici presenti nel nostro DB (radar_detections e h24_reports)."""
    sql = """
        SELECT DISTINCT icao24 FROM radar_detections WHERE icao24 IS NOT NULL AND icao24 != ''
        UNION
        SELECT DISTINCT icao24 FROM h24_reports WHERE icao24 IS NOT NULL AND icao24 != ''
        UNION
        SELECT DISTINCT icao24 FROM nightly_reports WHERE icao24 IS NOT NULL AND icao24 != ''
    """
    ok, rows = execute_query(sql)
    if not ok:
        logger.error(f"Errore recupero icao24: {rows}")
        return set()
    return {r[0].lower() for r in rows if r[0]}

def download_and_update():
    logger.info("Avvio aggiornamento DB aerei da OpenSky...")
    if not is_enabled():
        logger.error("DB non abilitato.")
        return False

    our_icaos = get_our_icao24s()
    if not our_icaos:
        logger.warning("Nessun icao24 trovato nel nostro DB. Esco.")
        return True
    logger.info(f"Trovati {len(our_icaos)} icao24 unici nel nostro DB.")

    logger.info(f"Scaricamento da {OPENSKY_URL}...")
    try:
        r = requests.get(OPENSKY_URL, stream=True, timeout=60)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"Errore download OpenSky: {e}")
        return False

    content = io.StringIO(r.text)
    reader = csv.DictReader(content)
    
    updates = []
    for row in reader:
        icao24 = (row.get("icao24") or "").strip().lower()
        if icao24 in our_icaos:
            model = (row.get("model") or "").strip()
            typecode = (row.get("typecode") or "").strip()
            registration = (row.get("registration") or "").strip()
            operator = (row.get("operator") or "").strip()
            
            updates.append((icao24, registration, model, typecode, operator))

    if not updates:
        logger.warning("Nessun match trovato nel CSV di OpenSky per i nostri icao24.")
        return True

    logger.info(f"Trovati {len(updates)} aerei da aggiornare nel DB locale.")
    
    sql_insert = """
        INSERT INTO aircraft_icao24_db (icao24, registration, model, typecode, operator, updated_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT (icao24) DO UPDATE SET
            registration = EXCLUDED.registration,
            model = EXCLUDED.model,
            typecode = EXCLUDED.typecode,
            operator = EXCLUDED.operator,
            updated_at = NOW()
    """
    
    try:
        ok, count = execute_many(sql_insert, updates)
        if ok:
            logger.info(f"✅ DB aggiornato con successo: {count} record.")
            return True
        else:
            logger.error(f"❌ Errore inserimento DB: {count}")
            return False
    except Exception as e:
        logger.error(f"❌ Eccezione inserimento: {e}")
        return False

if __name__ == "__main__":
    download_and_update()
