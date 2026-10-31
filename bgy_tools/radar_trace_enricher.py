"""
bgy_tools/radar_trace_enricher.py - Arricchimento piste tramite tracce radar locali.
Versione 1.1.0

Novita v1.1.0 (30/10/2026, FIX-PISTE):
- Corregge le piste propagate erroneamente basandosi sulla rotta reale (rotta_deg).
- Include i voli con pista_fonte = 'propagato' tra quelli da verificare, non solo N/D.
- Se un decollo vira (track 110-245), la pista viene corretta in RWY 10.
"""
import os
import pandas as pd
from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import RAW_DIR, OUTPUT_CSV_DIR
from bgy_core.bgy_dates import normalize_date

logger = get_logger("TraceEnricher")

def _get_radar_data(date_str):
    date_norm = normalize_date(date_str)
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
    date_norm = normalize_date(date_str)
    report_path = os.path.join(OUTPUT_CSV_DIR, f"report_nightly_{date_norm}.csv")
    
    if not os.path.exists(report_path):
        return False, f"Report non trovato: {report_path}"

    logger.info(f"🔍 Avvio TraceEnricher per {date_norm}...")
    
    try:
        df_report = pd.read_csv(report_path)
    except Exception as e:
        return False, f"Errore lettura report: {e}"

    if 'pista_fonte' not in df_report.columns:
        df_report['pista_fonte'] = 'N/D'
    df_report['pista_fonte'] = df_report['pista_fonte'].fillna('N/D').astype(str)

    # Filtriamo i voli con pista N/D OPPURE propagata erroneamente
    mask_target = (
        (
            df_report['pista'].isna() | 
            df_report['pista'].astype(str).str.strip().isin(['', 'N/D', 'nan']) |
            (df_report['pista_fonte'].str.lower().str.strip() == 'propagato')
        ) &
        (df_report['icao24'].notna()) & 
        (df_report['icao24'].astype(str).str.strip() != '')
    )
    
    voli_target = df_report[mask_target].copy()
    
    if voli_target.empty:
        logger.info("✅ Nessun volo N/D o propagato da arricchire.")
        return True, "Nessun volo da arricchire"

    logger.info(f"Trovati {len(voli_target)} voli da verificare (N/D o propagati). Carico tracce radar...")
    
    df_radar = _get_radar_data(date_norm)
    if df_radar.empty:
        logger.warning("⚠️ Nessun file radar trovato per questa sessione.")
        return False, "Nessun file radar trovato"

    modificati = 0
    verificati = 0
    
    data_target = pd.to_datetime(date_norm).date()
    data_prec = data_target - pd.Timedelta(days=1)

    for idx, volo in voli_target.iterrows():
        icao = str(volo['icao24']).lower().strip()
        cs = volo.get('callsign', '?')
        direzione = str(volo.get('direzione_sacbo', '')).upper()
        pista_attuale = str(volo.get('pista', 'N/D')).strip()
        
        traccia = df_radar[df_radar['icao24'].astype(str).str.lower() == icao].copy()
        
        if traccia.empty:
            continue
            
        traccia = traccia[
            ((traccia['timestamp'].dt.date == data_target) & (traccia['timestamp'].dt.hour <= 10)) |
            ((traccia['timestamp'].dt.date == data_prec) & (traccia['timestamp'].dt.hour >= 20))
        ]
        
        if traccia.empty:
            continue
            
        traccia = traccia.sort_values('timestamp')
        punti_bassi = traccia[traccia['quota_ft'].notna() & (traccia['quota_ft'] <= 3000)]
        
        if punti_bassi.empty:
            continue
            
        if direzione == 'D':
            punto_contatto = punti_bassi.iloc[0]
        else:
            punto_contatto = punti_bassi.iloc[-1]
            
        track = punto_contatto['rotta_deg']
        if pd.isna(track):
            continue
        
        verificati += 1
        pista_dedotta = None
        
        # 1. Deduzione diretta
        if 70 <= track <= 120:
            pista_dedotta = "RWY 10"
        elif 250 <= track <= 300:
            pista_dedotta = "RWY 28"
        # 2. Gestione virata post-decollo o pre-atterraggio
        elif 110 < track < 200 or 200 < track < 250:
            if direzione == 'D':
                pista_dedotta = "RWY 10" # Decollo che vira: solitamente da pista 10
            elif direzione == 'A':
                pista_dedotta = "RWY 10" if track < 180 else "RWY 28"
            
        if pista_dedotta:
            if pista_attuale != pista_dedotta:
                df_report.at[idx, 'pista'] = pista_dedotta
                df_report.at[idx, 'pista_fonte'] = 'geometrico'
                logger.info(f"  ✅ {cs} ({direzione}): corretta da {pista_attuale} a {pista_dedotta} (track {track:.1f}°)")
                modificati += 1
            else:
                if df_report.at[idx, 'pista_fonte'].lower() == 'propagato':
                    df_report.at[idx, 'pista_fonte'] = 'radar_diretto'
                    modificati += 1

    if modificati > 0:
        df_report.to_csv(report_path, index=False, encoding='utf-8-sig')
        logger.info(f"💾 Report aggiornato salvato: {report_path} ({modificati} piste corrette)")
        return True, f"Corrette {modificati} piste"
    else:
        logger.info(f"Nessuna pista da correggere (verificati {verificati} voli).")
        return True, "Nessuna pista corretta"
