"""
bgy_reports/bgy_report_night.py - Report notturno integrato (SACBO + OpenSky).
Versione 2.5.4
- Fix matching: normalizzazione callsign SACBO con conversione IATA -> ICAO
- Fix extract_callsign_prefix per prefissi misti (W4, W6, 3F, V7)
- Distanze per fase da config
"""
import os
import math
import pandas as pd
from datetime import datetime

from bgy_core import (
    get_airline, get_country, get_aircraft_model,
    is_cargo_flight, load_rules, get_logger,
    estimate_passengers,
)
from bgy_core.bgy_paths import RAW_DIR, OUTPUT_CSV_DIR
from bgy_core.bgy_dates import (
    normalize_date, radar_filename, report_nightly_filename,
    night_session_date,
)
from bgy_core.bgy_config_manager import config_manager
from bgy_core.bgy_update_rules import iata_to_icao, extract_callsign_prefix
from bgy_utils.bgy_utils_meteo import save_night_weather

logger = get_logger("ReportNight")

BGY_LAT = 45.6739
BGY_LON = 9.7042


def _cfg():
    return config_manager.get_report_night_config()


# -----------------------------------------------------------------------------
# UTILITY
# -----------------------------------------------------------------------------

def _safe_float(value, default=None):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_int(value, default=0):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default


def _distance_from_phase(fase):
    cfg = _cfg()
    distances = cfg.get("distance_by_phase_km", {})
    return distances.get(fase)


def _find_scan_file_for_date(date_norm):
    new_name = radar_filename(date_norm)
    old_name = f"bgy_night_flights_{date_norm}.csv"
    for name in (new_name, old_name):
        if not name:
            continue
        p = os.path.join(RAW_DIR, name)
        if os.path.exists(p):
            return p
    return None


# -----------------------------------------------------------------------------
# NORMALIZZAZIONE CALLSIGN (fix matching)
# -----------------------------------------------------------------------------

def _normalize_callsign_sacbo(callsign):
    """
    Converte un callsign del tabellone SACBO in prefisso ICAO + numero volo.

    Esempi:
      'FR 3480'   -> ('RYR', '3480')
      'W4 3136'   -> ('WMT', '3136')
      'AZ 7048'   -> ('ITY', '7048')
      'RYR3480'   -> ('RYR', '3480')
      'XXX123'    -> ('', '')
    """
    if not callsign or not isinstance(callsign, str):
        return "", ""

    cs = callsign.strip().upper().replace(" ", "")

    # 1. Prova prefisso IATA (2 caratteri, alfabetico o misto)
    prefix2 = extract_callsign_prefix(cs, 2)
    if prefix2:
        icao_from_iata = iata_to_icao(prefix2)
        if icao_from_iata:
            numero = cs[len(prefix2):]
            return icao_from_iata, numero

    # 2. Prova prefisso ICAO (3 lettere)
    prefix3 = extract_callsign_prefix(cs, 3)
    if prefix3:
        numero = cs[len(prefix3):]
        return prefix3, numero

    return "", ""


def _normalize_callsign_radar(callsign):
    """
    Estrae prefisso ICAO (3 lettere) e numero volo da un callsign radar.
    """
    if not callsign or not isinstance(callsign, str):
        return "", ""

    cs = callsign.strip().upper().replace(" ", "")
    prefix = extract_callsign_prefix(cs, 3)
    if not prefix:
        return "", ""
    numero = cs[len(prefix):]
    return prefix, numero


def _callsigns_match(sacbo_callsign, radar_callsign):
    """
    Verifica se un callsign SACBO e uno radar corrispondono.
    Ritorna uno score: 0 (no match), 50 (match parziale), 100 (match esatto).
    """
    # Caso 1: confronto diretto
    sacbo_norm = sacbo_callsign.strip().upper().replace(" ", "")
    radar_norm = radar_callsign.strip().upper().replace(" ", "")
    if sacbo_norm == radar_norm:
        return 100

    # Caso 2: conversione IATA -> ICAO sul callsign SACBO
    sacbo_prefix, sacbo_numero = _normalize_callsign_sacbo(sacbo_callsign)
    radar_prefix, radar_numero = _normalize_callsign_radar(radar_callsign)

    if not sacbo_prefix or not radar_prefix:
        return 0

    if sacbo_prefix != radar_prefix:
        return 0

    if not sacbo_numero or not radar_numero:
        return 0

    if sacbo_numero == radar_numero:
        return 100

    if sacbo_numero.endswith(radar_numero) or radar_numero.endswith(sacbo_numero):
        return 50

    return 0


# -----------------------------------------------------------------------------
# CARICAMENTO DATI
# -----------------------------------------------------------------------------

def load_scheduled_flights(date_str):
    date_norm = normalize_date(date_str)
    date_clean = date_norm.replace("-", "")
    scheduled = []

    scan_files = []
    if os.path.isdir(RAW_DIR):
        for f in os.listdir(RAW_DIR):
            if not f.startswith("scan_") or not f.endswith(".csv"):
                continue
            if f.startswith(f"scan_{date_norm}_"):
                scan_files.append(f)
            elif f.startswith(f"scan_{date_clean}_"):
                scan_files.append(f)

    for f in scan_files:
        filepath = os.path.join(RAW_DIR, f)
        try:
            df = pd.read_csv(filepath)
            df = normalize_scan_columns(df)
            for _, row in df.iterrows():
                sched_time = row.get('orario_schedulato')
                if not sched_time:
                    continue
                try:
                    hour = int(str(sched_time).strip().split(':')[0])
                    if hour >= 23 or hour < 6:
                        scheduled.append(row.to_dict())
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Errore lettura {f}: {e}")

    if scheduled:
        df_sched = pd.DataFrame(scheduled)
        logger.info(f"📋 Caricati {len(df_sched)} voli schedulati notturni")
        return df_sched
    logger.info("📋 Nessun volo schedulato notturno trovato")
    return pd.DataFrame()


def normalize_scan_columns(df):
    col_map = {
        'flight_num': 'callsign_volo', 'numero_volo': 'callsign_volo',
        'type': 'tipo_movimento', 'sched_time': 'orario_schedulato',
        'actual_time': 'orario_effettivo', 'origin_dest': 'destinazione_origine',
        'stato_volo': 'stato_volo', 'status': 'stato_volo', 'stato': 'stato_volo'
    }
    df = df.rename(columns=col_map)
    required = ['callsign_volo', 'tipo_movimento', 'orario_schedulato', 'destinazione_origine']
    for col in required:
        if col not in df.columns:
            df[col] = ''
    return df


def load_radar_data(date_str):
    date_norm = normalize_date(date_str)
    filepath = _find_scan_file_for_date(date_norm)
    if filepath:
        try:
            df = pd.read_csv(filepath)
            logger.info(f"📡 Caricati {len(df)} dati radar da {os.path.basename(filepath)}")
            return df
        except Exception as e:
            logger.warning(f"Errore lettura radar: {e}")
    else:
        logger.info(f"📡 Nessun file radar per {date_norm}")
    return pd.DataFrame()


# -----------------------------------------------------------------------------
# MATCHING
# -----------------------------------------------------------------------------

def match_flights(scheduled_df, radar_df):
    if scheduled_df.empty and radar_df.empty:
        return pd.DataFrame()

    if not scheduled_df.empty:
        scheduled_df = scheduled_df.copy()
        scheduled_df['callsign_norm'] = scheduled_df['callsign_volo'].apply(
            lambda x: str(x).replace(' ', '').upper().strip())

    if not radar_df.empty:
        radar_df = radar_df.copy()
        radar_df['callsign_norm'] = radar_df['callsign'].apply(
            lambda x: str(x).replace(' ', '').upper().strip())

    if scheduled_df.empty:
        radar_df['is_scheduled'] = False
        radar_df['orario_schedulato'] = ''
        radar_df['destinazione_origine'] = ''
        return _enrich_final(_classify_unscheduled(radar_df))

    if radar_df.empty:
        scheduled_df['is_scheduled'] = True
        scheduled_df['timestamp'] = ''
        scheduled_df['pista'] = 'N/D'
        scheduled_df['fase_volo'] = 'Non rilevato'
        scheduled_df['direzione'] = 'N/D'
        scheduled_df['quota_ft'] = 0
        scheduled_df['rotta_deg'] = 0
        scheduled_df['distanza_km'] = 0
        scheduled_df['paese'] = 'N/D'
        scheduled_df['tipo_movimento'] = 'Passeggeri (non rilevato)'
        scheduled_df['matched_score'] = 0
        return _enrich_final(scheduled_df)

    matched = []
    used_radar = set()

    for idx_s, sched in scheduled_df.iterrows():
        sched_callsign = sched['callsign_volo']
        best_match = None
        best_score = -1

        for idx_r, radar in radar_df.iterrows():
            if idx_r in used_radar:
                continue
            radar_callsign = radar['callsign']
            score = _callsigns_match(sched_callsign, radar_callsign)
            if score > best_score:
                best_score = score
                best_match = (idx_r, radar)

        if best_match and best_score >= 50:
            idx_r, radar = best_match
            used_radar.add(idx_r)
            combined = {**sched.to_dict(), **radar.to_dict()}
            combined['is_scheduled'] = True
            combined['matched_score'] = best_score
            combined['tipo_movimento'] = 'Passeggeri (schedulato + radar)'
            matched.append(combined)
        else:
            combined = {**sched.to_dict()}
            combined['is_scheduled'] = True
            combined['timestamp'] = ''
            combined['pista'] = 'N/D'
            combined['fase_volo'] = 'Non rilevato'
            combined['direzione'] = 'N/D'
            combined['quota_ft'] = 0
            combined['rotta_deg'] = 0
            combined['distanza_km'] = 0
            combined['paese'] = 'N/D'
            combined['matched_score'] = 0
            combined['tipo_movimento'] = 'Passeggeri (solo schedulato)'
            matched.append(combined)

    unmatched = radar_df[~radar_df.index.isin(used_radar)].copy()
    unmatched = _classify_unscheduled(unmatched)
    for _, row in unmatched.iterrows():
        row_dict = row.to_dict()
        row_dict['matched_score'] = 0
        matched.append(row_dict)

    return _enrich_final(pd.DataFrame(matched))


def _classify_unscheduled(df):
    if df.empty:
        return df

    def classify(row):
        cs = str(row.get('callsign', '') or '')
        cargo, cargo_airline = is_cargo_flight(cs)
        if cargo:
            return f'Cargo ({cargo_airline})'
        return 'Non identificato / Sorvolo'

    df = df.copy()
    df['tipo_movimento'] = df.apply(classify, axis=1)
    return df


def _enrich_final(df):
    if df.empty:
        return df
    df = df.copy()

    df['compagnia_aerea'] = df['callsign'].apply(
        lambda x: get_airline(x) if pd.notna(x) else 'N/D')
    df['modello_aereo'] = df['callsign'].apply(
        lambda x: get_aircraft_model(x) if pd.notna(x) else 'N/D')

    if 'destinazione_origine' in df.columns:
        df['destinazione_finale'] = df.apply(
            lambda row: row['destinazione_origine']
            if pd.notna(row.get('destinazione_origine')) and row['destinazione_origine']
            else row.get('paese', 'N/D'), axis=1)
    else:
        df['destinazione_finale'] = df.get('paese', 'N/D')

    def resolve_country(row):
        dest = row.get('destinazione_origine', '')
        if pd.notna(dest) and dest and dest != '':
            return get_country(dest)
        paese = row.get('paese', '')
        if pd.notna(paese) and paese:
            return get_country(paese)
        return 'N/D'

    df['stato_destinazione'] = df.apply(resolve_country, axis=1)

    def _pax(row):
        modello = row.get('modello_aereo', 'N/D')
        if not modello or modello == 'N/D':
            return 0
        try:
            cs = str(row.get('callsign', '') or '').strip().upper()
            code = cs[:3] if len(cs) >= 3 else (cs[:2] if len(cs) >= 2 else '')
            pax, seats, lf = estimate_passengers(modello, code)
            return pax
        except Exception:
            return 0

    df['stima_passeggeri'] = df.apply(_pax, axis=1)

    try:
        from bgy_utils.bgy_utils_noise import get_max_noise
        from bgy_core import get_noise_stations
        if not get_noise_stations():
            load_rules()

        def _noise(row):
            timestamp = row.get('timestamp', '')
            if not timestamp or pd.isna(timestamp) or str(timestamp).strip() == '':
                return 0
            fase = row.get('fase_volo', '')
            if not fase or fase in ('Non rilevato', 'N/D') or pd.isna(fase):
                return 0
            modello = row.get('modello_aereo', 'N/D')
            if not modello or modello == 'N/D':
                modello = None
            quota = _safe_int(row.get('quota_ft'), 0)
            dist = _safe_float(row.get('distanza_km'), None)
            if dist is None or dist <= 0:
                dist = _distance_from_phase(fase)
            if dist is None:
                return 0
            rotta = _safe_float(row.get('rotta_deg'), 0)
            try:
                dlat = (dist / 111.0) * math.cos(math.radians(rotta))
                dlon = (dist / (111.0 * math.cos(math.radians(BGY_LAT)))) * math.sin(math.radians(rotta))
                lat = BGY_LAT + dlat
                lon = BGY_LON + dlon
            except Exception:
                return 0
            try:
                return get_max_noise(modello, fase, lat, lon, quota)
            except Exception as e:
                logger.debug(f"Errore noise per {row.get('callsign', '?')}: {e}")
                return 0

        df['stima_rumore_db'] = df.apply(_noise, axis=1)
    except Exception as e:
        logger.warning(f"Impossibile calcolare stima rumore: {e}")
        df['stima_rumore_db'] = 0

    return df


# -----------------------------------------------------------------------------
# GENERAZIONE
# -----------------------------------------------------------------------------

def generate_nightly_report(date_str=None):
    load_rules()
    date_norm = normalize_date(date_str) if date_str else night_session_date()
    logger.info(f"🌙 Avvio report notturno per {date_norm} (23:00-05:59)")

    scheduled_df = load_scheduled_flights(date_norm)
    radar_df = load_radar_data(date_norm)
    result_df = match_flights(scheduled_df, radar_df)

    if result_df.empty:
        logger.warning(f"⚠️ Nessun dato per {date_norm}")
        return None, f"Nessun dato per {date_norm}"

    os.makedirs(OUTPUT_CSV_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_CSV_DIR, report_nightly_filename(date_norm))

    final_columns = [
        'callsign', 'tipo_movimento', 'is_scheduled',
        'destinazione_finale', 'stato_destinazione',
        'compagnia_aerea', 'modello_aereo',
        'orario_schedulato', 'timestamp', 'pista', 'fase_volo',
        'direzione', 'quota_ft', 'rotta_deg', 'distanza_km',
        'paese', 'matched_score',
        'stima_passeggeri', 'stima_rumore_db'
    ]
    for col in final_columns:
        if col not in result_df.columns:
            result_df[col] = ''

    result_df[final_columns].to_csv(out_path, index=False, encoding='utf-8-sig')

    total = len(result_df)
    scheduled = len(result_df[result_df['is_scheduled'] == True]) if 'is_scheduled' in result_df.columns else 0
    cargo = len(result_df[result_df['tipo_movimento'].str.startswith('Cargo', na=False)]) if 'tipo_movimento' in result_df.columns else 0
    unknown = total - scheduled - cargo
    pax_tot = int(result_df['stima_passeggeri'].sum()) if 'stima_passeggeri' in result_df.columns else 0

    if 'stima_rumore_db' in result_df.columns:
        rumore_df = result_df[result_df['stima_rumore_db'] > 0]
        rumore_count = len(rumore_df)
        rumore_max = int(rumore_df['stima_rumore_db'].max()) if rumore_count > 0 else 0
    else:
        rumore_count = 0
        rumore_max = 0

    meteo_path = None
    meteo_msg = ""
    try:
        meteo_path = save_night_weather(date_norm)
        if meteo_path:
            meteo_msg = f", meteo salvato ({os.path.basename(meteo_path)})"
        else:
            meteo_msg = ", meteo non disponibile"
    except Exception as e:
        logger.warning(f"Errore salvataggio meteo: {e}")
        meteo_msg = ", errore meteo"

    msg = (f"✅ Report notturno: {total} voli "
           f"(Passeggeri: {scheduled}, Cargo: {cargo}, Non id: {unknown}, "
           f"PAX stimati: {pax_tot}, "
           f"Rumore su {rumore_count} voli, max {rumore_max} dB"
           f"{meteo_msg})")
    logger.info(msg)
    return out_path, msg


if __name__ == "__main__":
    path, msg = generate_nightly_report()
    print(msg)
    if path:
        print(f"📁 File: {path}")