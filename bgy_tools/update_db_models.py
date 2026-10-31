"""
bgy_tools/update_db_models.py
Aggiorna tutti i modelli aerei nel database usando il dizionario locale (OpenSky).
Sovrascrive anche i modelli già esistenti, garantendo la massima precisione (ICAO24).
"""
import os
import sys
import json

# Aggiunge la directory principale al path per trovare bgy_core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core import bgy_db
from bgy_core.bgy_paths import DATA_DIR
from bgy_core.bgy_logger import get_logger

logger = get_logger("UpdateDBModels")

def main():
    dict_file = os.path.join(DATA_DIR, "aircraft_dictionary.json")
    if not os.path.exists(dict_file):
        print("Dizionario non trovato. Esegui prima update_aircraft_dict.py")
        return

    with open(dict_file, "r", encoding="utf-8") as f:
        data = json.load(f)["data"]

    print(f"Dizionario caricato con {len(data)} modelli.")
    conn = bgy_db.get_connection()
    if not conn:
        print("Errore connessione DB")
        return

    try:
        with conn.cursor() as cur:
            # 1. Aggiorna h24_reports
            print("Aggiornamento h24_reports in corso...")
            cur.execute("""
                SELECT DISTINCT icao24 FROM h24_reports 
                WHERE icao24 IS NOT NULL AND icao24 != ''
            """)
            h24_icaos = [row[0].strip().lower() for row in cur.fetchall() if row[0]]
            
            h24_batch = []
            for icao in h24_icaos:
                if icao in data:
                    h24_batch.append((data[icao], icao))
            
            if h24_batch:
                cur.executemany("UPDATE h24_reports SET modello_aereo = %s WHERE LOWER(icao24) = %s", h24_batch)
                print(f"  -> Aggiornati {len(h24_batch)} modelli in h24_reports.")

            # 2. Aggiorna nightly_reports
            print("Aggiornamento nightly_reports in corso...")
            cur.execute("""
                SELECT DISTINCT icao24 FROM nightly_reports 
                WHERE icao24 IS NOT NULL AND icao24 != ''
            """)
            nightly_icaos = [row[0].strip().lower() for row in cur.fetchall() if row[0]]
            
            nightly_batch = []
            for icao in nightly_icaos:
                if icao in data:
                    nightly_batch.append((data[icao], icao))
            
            if nightly_batch:
                cur.executemany("UPDATE nightly_reports SET modello_aereo = %s WHERE LOWER(icao24) = %s", nightly_batch)
                print(f"  -> Aggiornati {len(nightly_batch)} modelli in nightly_reports.")

        conn.commit()
        print("Database aggiornato con successo!")
    except Exception as e:
        conn.rollback()
        print(f"Errore: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()