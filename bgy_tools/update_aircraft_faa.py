"""
bgy_tools/update_aircraft_faa.py
Aggiorna l'anno di costruzione (built) per gli aerei americani usando il registro FAA.
"""
import os
import sys
import pandas as pd

sys.path.insert(0, os.getcwd())
from bgy_core import bgy_db

MASTER_PATH = "bgy_data/bgy_assets/MASTER.txt"

def main():
    if not os.path.exists(MASTER_PATH):
        print(f"ERRORE: File MASTER.txt non trovato in {MASTER_PATH}")
        print("Esegui prima 'py -3.12 -m bgy_tools.faa_bulk_check' per scaricarlo.")
        return

    print("1. Lettura del registro FAA...")
    df = pd.read_csv(MASTER_PATH, dtype=str, encoding='latin-1')
    df.columns = [c.strip().upper().replace('Ï»¿', '').replace('\ufeff', '') for c in df.columns]
    
    col_hex = 'MODE S CODE HEX'
    col_year = 'YEAR MFR'
    
    df[col_hex] = df[col_hex].str.upper().str.strip()
    df[col_year] = pd.to_numeric(df[col_year], errors='coerce').fillna(0).astype(int)
    
    # Creiamo un dizionario {icao24: anno}
    mappa_anni = dict(zip(df[col_hex], df[col_year]))
    print(f"   Caricati {len(mappa_anni)} record FAA.")

    print("\n2. Recupero degli icao24 dal nostro database...")
    ok, rows = bgy_db.execute_query(
        "SELECT icao24 FROM aircraft_icao24_db WHERE LEFT(icao24, 1) = 'a' AND (built IS NULL OR built = 0)"
    )
    if not ok:
        print("Errore DB:", rows)
        return

    da_aggiornare = []
    for r in rows:
        icao = str(r[0]).upper()
        if icao in mappa_anni and mappa_anni[icao] > 0:
            da_aggiornare.append((mappa_anni[icao], icao))

    print(f"   Trovati {len(da_aggiornare)} aerei da aggiornare con l'anno di costruzione.")

    if not da_aggiornare:
        print("Nessun aereo da aggiornare.")
        return

    print("\n3. Aggiornamento del database...")
    count = 0
    for anno, icao in da_aggiornare:
        bgy_db.execute_query(
            "UPDATE aircraft_icao24_db SET built = %s WHERE icao24 = %s",
            (anno, icao), fetch=False
        )
        bgy_db.execute_query(
            """INSERT INTO aircraft_hexdb (icao24, built, source, fetched_at) 
               VALUES (%s, %s, 'faa', NOW()) 
               ON CONFLICT (icao24) DO UPDATE SET built = EXCLUDED.built, source = 'faa', fetched_at = NOW()""",
            (icao, anno), fetch=False
        )
        count += 1

    print(f"✅ Aggiornati {count} aerei con l'anno di costruzione dalla FAA.")

if __name__ == "__main__":
    main()