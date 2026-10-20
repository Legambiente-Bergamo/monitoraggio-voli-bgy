import pandas as pd
import os
from bgy_core.bgy_db import execute_query
from bgy_core.bgy_paths import RAW_DIR

print("=== TEST ESTESO TRACE ENRICHER (Storico decolli N/D) ===\n")

sql = """
    SELECT data_riferimento, callsign, icao24, timestamp 
    FROM nightly_reports
    WHERE is_scheduled = TRUE 
      AND direzione_sacbo = 'D'
      AND (pista IS NULL OR pista = '' OR pista = 'N/D')
      AND icao24 IS NOT NULL AND icao24 != ''
    ORDER BY data_riferimento
"""
ok, rows = execute_query(sql)
if not ok:
    print("Errore query:", rows)
    exit(1)

by_month = {}
for r in rows:
    mese = str(r[0])[:7] # Conversione a stringa per estrarre YYYY-MM
    by_month.setdefault(mese, []).append(r)

successi = 0
falliti = 0
risultati = []

for mese, voli in by_month.items():
    print(f"--- Analisi mese: {mese} ({len(voli)} voli N/D) ---")
    
    radar_files = [os.path.join(RAW_DIR, f) for f in os.listdir(RAW_DIR) if f.startswith(f"radar_{mese}")]
    if not radar_files:
        print(f"  Nessun file radar per {mese}, salto.")
        continue
        
    dfs = [pd.read_csv(f) for f in radar_files]
    df_radar = pd.concat(dfs, ignore_index=True)
    df_radar['timestamp'] = pd.to_datetime(df_radar['timestamp'])
    
    for volo in voli:
        ds, cs, icao, ts_str = volo
        icao_clean = str(icao).lower().strip()
        data_dt = pd.to_datetime(ds)
        
        # Prendiamo la traccia di quell'aereo
        traccia = df_radar[df_radar['icao24'].astype(str).str.lower() == icao_clean].copy()
        
        # Filtriamo per la sessione notturna (dalle 20:00 del giorno prima alle 10:00 del giorno stesso)
        # (Approssimativo per non complicare troppo lo script)
        traccia = traccia[(traccia['timestamp'].dt.strftime('%Y-%m-%d') == str(ds)) | 
                          (traccia['timestamp'].dt.strftime('%Y-%m-%d') == str(data_dt - pd.Timedelta(days=1)))]
                          
        if traccia.empty:
            falliti += 1
            continue
            
        traccia = traccia.sort_values('timestamp')
        punti_bassi = traccia[traccia['quota_ft'] <= 2000]
        
        if punti_bassi.empty:
            falliti += 1
            continue
            
        punto_contatto = punti_bassi.iloc[0]
        track = punto_contatto['rotta_deg']
        
        pista = "N/D"
        if 70 <= track <= 120:
            pista = "RWY 10"
        elif 250 <= track <= 300:
            pista = "RWY 28"
            
        if pista != "N/D":
            successi += 1
            risultati.append((ds, cs, pista, track))
        else:
            falliti += 1

print(f"\n--- RIEPILOGO GENERALE ---")
print(f"Successi: {successi}")
print(f"Falliti: {falliti}")
print(f"Percentuale di recupero: {(successi/(successi+falliti)*100):.1f}%")

print("\n--- ESEMPI DI PISTE DEDOTTE ---")
for r in risultati[:20]:
    print(f"{r[0]} | {r[1]:<8} | Pista: {r[2]} | Track: {r[3]:.1f}°")
if len(risultati) > 20:
    print(f"... e altri {len(risultati)-20} voli recuperati.")
