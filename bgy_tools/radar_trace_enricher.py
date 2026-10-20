"""
bgy_tools/radar_trace_enricher.py - Arricchimento piste tramite tracce radar locali.
Versione 1.0.0

Novita v1.0.0 (20/10/2026):
- Legge il report notturno e i file radar locali.
- Per i voli con pista N/D e icao24 valido, cerca il punto a bassa quota
  e deduce la pista dal track (70-120 -> RWY 10, 250-300 -> RWY 28).
- Sovrascrive il CSV del report notturno con i dati aggiornati.
"""
import os
import pandas as pd
from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import RAW_DIR, OUTPUT_CSV_DIR
from bgy_core.bgy_dates import normalize_date

logger = get_logger("TraceEnricher")

def _get_radar_data(date_str):
    date_norm = normalize_date(date_str)
    # Convertiamo in datetime per gestire il giorno prima e dopo
    from datetime import datetime, timedelta
    dt = datetime.strptime(date_norm, "%Y-%m-%d")
    prev_date = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    next_date = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
    
    files = [
        os.path.join(RAW_DIR, f"radar_{date_norm}.csv"),
        os.path.join(RAW_DIR, f"radar_{next_date}.csv"),
        os.path.join(RAW_DIR, f"radar_{prev_date}.csv")
    ]
    
    dfs = []
    for f in files:
        if os.path.exists(f):
            try:
                df = pd.read_csv(f)
                if not df.empty:
                    dfs.append(df)
            except Exception as e:
                logger.warning(f"Errore lettura {f}: {e}")
                
    if not dfs:
        return pd.DataFrame()
        
    combined = pd.concat(dfs, ignore_index=True)
    combined['timestamp'] = pd.to_datetime(combined['timestamp'], errors='coerce')
    return combined

def enrich_runways(date_str):
    """
    Arricchisce il report notturno per la data specificata.
    Ritorna (ok, msg).
    """
    date_norm = normalize_date(date_str)
    report_path = os.path.join(OUTPUT_CSV_DIR, f"report_nightly_{date_norm}.csv")
    
    if not os.path.exists(report_path):
        return False, f"Report non trovato: {report_path}"

    logger.info(f"🔍 Avvio TraceEnricher per {date_norm}...")
    
    try:
        df_report = pd.read_csv(report_path)
    except Exception as e:
        return False, f"Errore lettura report: {e}"

    # Filtriamo i voli con pista N/D e icao24 valido
    mask_nd = (
        (df_report['pista'].isna() | (df_report['pista'].astype(str).str.strip().isin(['', 'N/D', 'nan']))) &
        (df_report['icao24'].notna()) & 
        (df_report['icao24'].astype(str).str.strip() != '')
    )
    
    voli_nd = df_report[mask_nd].copy()
    
    if voli_nd.empty:
        logger.info("✅ Nessun volo N/D con icao24 da arricchire.")
        return True, "Nessun volo da arricchire"

    logger.info(f"Trovati {len(voli_nd)} voli N/D con icao24 valido. Carico tracce radar...")
    
    df_radar = _get_radar_data(date_norm)
    if df_radar.empty:
        logger.warning("⚠️ Nessun file radar trovato per questa sessione.")
        return False, "Nessun file radar trovato"

    successi = 0
    modificati = 0
    
    # Data di riferimento per filtrare la sessione notturna
    data_target = pd.to_datetime(date_norm).date()
    data_prec = data_target - pd.Timedelta(days=1)

    for idx, volo in voli_nd.iterrows():
        icao = str(volo['icao24']).lower().strip()
        cs = volo.get('callsign', '?')
        direzione = str(volo.get('direzione_sacbo', '')).upper()
        
        # Filtriamo la traccia di questo aereo
        traccia = df_radar[df_radar['icao24'].astype(str).str.lower() == icao].copy()
        
        if traccia.empty:
            continue
            
        # Filtriamo per la sessione notturna (dalle 20:00 del giorno prima alle 10:00 del giorno stesso)
        traccia = traccia[
            ((traccia['timestamp'].dt.date == data_target) & (traccia['timestamp'].dt.hour <= 10)) |
            ((traccia['timestamp'].dt.date == data_prec) & (traccia['timestamp'].dt.hour >= 20))
        ]
        
        if traccia.empty:
            continue
            
        traccia = traccia.sort_values('timestamp')
        punti_bassi = traccia[traccia['quota_ft'] <= 2000]
        
        if punti_bassi.empty:
            continue
            
        # Per i decolli prendiamo il primo punto a bassa quota, per gli atterraggi l'ultimo
        if direzione == 'D':
            punto_contatto = punti_bassi.iloc[0]
        else:
            punto_contatto = punti_bassi.iloc[-1]
            
        track = punto_contatto['rotta_deg']
        
        pista_dedotta = None
        if 70 <= track <= 120:
            pista_dedotta = "RWY 10"
        elif 250 <= track <= 300:
            pista_dedotta = "RWY 28"
            
        if pista_dedotta:
            df_report.at[idx, 'pista'] = pista_dedotta
            successi += 1
            logger.info(f"  ✅ {cs} ({direzione}): pista dedotta {pista_dedotta} (track {track:.1f}°, quota {punto_contatto['quota_ft']} ft)")
            modificati += 1

    if modificati > 0:
        # Salvataggio
        df_report.to_csv(report_path, index=False, encoding='utf-8-sig')
        logger.info(f"💾 Report aggiornato salvato: {report_path} ({modificati} piste arricchite)")
        return True, f"Arricchiti {modificati} voli"
    else:
        logger.info("Nessun volo è stato arricchito (tracce assenti o track ambigui).")
        return True, "Nessun volo arricchito"