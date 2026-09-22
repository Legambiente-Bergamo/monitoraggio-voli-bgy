"""
bgy_reports/bgy_report_night.py - Report notturno integrato (SACBO + OpenSky).
Versione 2.7.1
- Matching basato su finestra temporale + tipo movimento (callsign SACBO e radar
  hanno formati numerici diversi, non confrontabili direttamente)
- Il report contiene solo: voli passeggeri schedulati (con o senza radar)
  + cargo identificati. I sorvoli/transiti/non identificati sono esclusi.
- Arricchimento con fase, pista, quota, distanza, rumore.

Fix v2.7.1:
- DEDUPLICA in load_scheduled_flights(): i voli notturni vengono letti da
  TUTTE le scansioni SACBO della giornata (23:00, 02:00, 05:00). Senza
  deduplica, ogni volo compariva N volte (una per scansione), gonfiando
  il conteggio (es. 53 voli invece di 30). Ora si tiene una sola riga per
  coppia (callsign_volo, orario_schedulato), preferendo la scansione più
  recente (scan_files ordinati reverse).
"""
import os
import math
import pandas as pd
from datetime import datetime, timedelta

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
from bgy_utils.bgy_utils_meteo import save_night_weather

logger = get_logger("ReportNight")

BGY_LAT = 45.6739
BGY_LON = 9.7042

# Finestra temporale per il matching (minuti)
MATCH_WINDOW_BEFORE_MIN = 30      # 30 min prima dell'orario schedulato
MATCH_WINDOW_AFTER_MIN = 180      # 3 ore dopo l'orario schedulato


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


def _time_to_minutes(hhmm):
    """Converte 'HH:MM' in minuti dalla mezzanotte. Ritorna None se invalido."""
    if not hhmm:
        return None
    try:
        s = str(hhmm).strip()
        parts = s.split(":")
        if len(parts) < 2:
            return None
        hh = int(parts[0])
        mm = int(parts[1])
        return hh * 60 + mm
    except (ValueError, AttributeError):
        return None


def _timestamp_to_minutes_session(ts, session_date):
    """
    Converte un timestamp in minuti relativi alla sessione notturna.
    La sessione inizia alle 23:00 di session_date.
    Le 23:00-23:59 sono minuti 0-59.
    Le 00:00-05:59 sono minuti 60-419.
    """
    if not ts:
        return None
    try:
        dt = pd.to_datetime(ts)
    except Exception:
        return None
    # Calcola minuti dalla mezzanotte del giorno di sessione
    base = pd.to_datetime(f"{session_date} 23:00:00")
    diff = (dt - base).total_seconds() / 60
    # Se negativo, timestamp prima dell'inizio sessione (raro)
    if diff < -30:
        return None
    return int(diff)


def _scheduled_minutes_from_session(hhmm, session_date):
    """
    Converte un orario schedulato 'HH:MM' in minuti relativi alla sessione.
    Se l'orario è >= 23:00, appartiene al giorno di sessione.
    Se l'orario è < 06:00, appartiene al giorno successivo (minuti >= 60).
    """
    mins = _time_to_minutes(hhmm)
    if mins is None:
        return None
    if mins >= 23 * 60:
        # 23:00-23:59 -> 0-59
        return mins - 23 * 60
    if mins < 6 * 60:
        # 00:00-05:59 -> 60-419
        return mins + 60
    return None  # fuori fascia notturna


# -----------------------------------------------------------------------------
# CARICAMENTO DATI
# -----------------------------------------------------------------------------

def load_scheduled_flights(date_str):
    """
    Carica i voli schedulati notturni da tutte le scansioni SACBO della data.

    Fix v2.7.1: deduplica per (callsign_volo, orario_schedulato).
    Le scansioni sono ordinate in ordine decrescente (più recente prima),
    così in caso di duplicato si tiene la versione più aggiornata.
    """
    date_norm = normalize_date(date_str)
    date_clean = date_norm.replace("-", "")
    scheduled = []
    seen = set()  # chiavi (callsign, orario) già viste

    scan_files = []
    if os.path.isdir(RAW_DIR):
        for f in os.listdir(RAW_DIR):
            if not f.startswith("scan_") or not f.endswith(".csv"):
                continue
            if f.startswith(f"scan_{date_norm}_"):
                scan_files.append(f)
            elif f.startswith(f"scan_{date_clean}_"):
                scan_files.append(f)

    # Ordina per nome file decrescente: le scansioni più recenti
    # (es. scan_2026-09-15_05-00.csv) vengono processate per prime.
    # In caso di duplicato, si tiene la prima occorrenza (= la più recente).
    scan_files.sort(reverse=True)

    duplicates_skipped = 0

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
                        # Deduplica per (callsign, orario_schedulato)
                        callsign = str(row.get('callsign_volo', '')).strip()
                        orario = str(sched_time).strip()
                        key = (callsign, orario)
                        if key in seen:
                            duplicates_skipped += 1
                            continue
                        seen.add(key)
                        scheduled.append(row.to_dict())
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Errore lettura {f}: {e}")

    if scheduled:
        df_sched = pd.DataFrame(scheduled)
        logger.info(
            f"📋 Caricati {len(df_sched)} voli schedulati notturni "
            f"(da {len(scan_files)} scansioni, "
            f"{duplicates_skipped} duplicati scartati)"
        )
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
# MATCHING (finestra temporale + tipo movimento)
# -----------------------------------------------------------------------------

def _is_phase_compatible(tipo_movimento, fase_volo):
    """
    Verifica se la fase radar è compatibile col tipo movimento SACBO.
    tipo_movimento: 'A' o 'D'
    fase_volo: 'Atterraggio', 'Decollo', 'Avvicinamento', 'Sorvolo', ...
    """
    if tipo_movimento == 'D':
        return fase_volo == 'Decollo'
    if tipo_movimento == 'A':
        return fase_volo in ('Atterraggio', 'Avvicinamento')
    return False


def match_flights(scheduled_df, radar_df, session_date):
    """
    Esegue il matching tra voli schedulati (SACBO) e rilevamenti radar.
    Criteri:
      - tipo movimento compatibile con fase_volo
      - timestamp radar dentro finestra [sched-30min, sched+180min]
      - unicità: ogni radar può matchare al massimo un volo schedulato
      - tra i candidati, sceglie quello col timestamp più vicino
    """
    if scheduled_df.empty and radar_df.empty:
        return pd.DataFrame()

    # --- Nessun schedulato: solo cargo identificati ---
    if scheduled_df.empty:
        if radar_df.empty:
            return pd.DataFrame()
        radar_df = radar_df.copy()
        radar_df['is_scheduled'] = False
        radar_df['orario_schedulato'] = ''
        radar_df['destinazione_origine'] = ''
        radar_df['matched_score'] = 0
        # Escludi i non-cargo
        cargo_mask = radar_df['callsign'].apply(
            lambda x: is_cargo_flight(str(x))[0] if pd.notna(x) else False)
        radar_df = radar_df[cargo_mask]
        if radar_df.empty:
            return pd.DataFrame()
        radar_df['tipo_movimento'] = radar_df['callsign'].apply(
            lambda x: f'Cargo ({is_cargo_flight(str(x))[1]})' if pd.notna(x) else 'Cargo')
        return _enrich_final(radar_df)

    # --- Nessun radar: schedulati tutti Non rilevato ---
    if radar_df.empty:
        scheduled_df = scheduled_df.copy()
        scheduled_df['is_scheduled'] = True
        scheduled_df['timestamp'] = ''
        scheduled_df['pista'] = 'N/D'
        scheduled_df['fase_volo'] = 'Non rilevato'
        scheduled_df['direzione'] = 'N/D'
        scheduled_df['quota_ft'] = 0
        scheduled_df['rotta_deg'] = 0
        scheduled_df['distanza_km'] = 0
        scheduled_df['paese'] = 'N/D'
        scheduled_df['matched_score'] = 0
        scheduled_df['callsign'] = scheduled_df['callsign_volo']
        # tipo_movimento: 'Passeggeri (non rilevato)' per tutti
        scheduled_df['tipo_movimento'] = 'Passeggeri (non rilevato)'
        return _enrich_final(scheduled_df)

    # --- Match ---
    sched = scheduled_df.copy()
    radar = radar_df.copy()

    # Calcola minuti sessione per ogni record
    sched['_sched_min'] = sched.apply(
        lambda r: _scheduled_minutes_from_session(
            r.get('orario_schedulato'),
            session_date),
        axis=1)
    radar['_radar_min'] = radar['timestamp'].apply(
        lambda t: _timestamp_to_minutes_session(t, session_date))

    # Filtra radar con timestamp valido e fase utile
    radar = radar[radar['_radar_min'].notna()].copy()

    matched = []
    used_radar_idx = set()

    for _, s in sched.iterrows():
        sched_min = s['_sched_min']
        tipo_mov = s.get('tipo_movimento', '')
        if sched_min is None:
            # Non schedulato valido: passa avanti (sarà Non rilevato)
            combined = dict(s)
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
            combined['callsign'] = combined.get('callsign_volo', '')
            combined['tipo_movimento'] = 'Passeggeri (non rilevato)'
            matched.append(combined)
            continue

        # Finestra
        low = sched_min - MATCH_WINDOW_BEFORE_MIN
        high = sched_min + MATCH_WINDOW_AFTER_MIN

        best_idx = None
        best_delta = None

        for idx, r in radar.iterrows():
            if idx in used_radar_idx:
                continue
            r_min = r['_radar_min']
            if r_min is None or r_min < low or r_min > high:
                continue
            fase = str(r.get('fase_volo', '') or '')
            if not _is_phase_compatible(tipo_mov, fase):
                continue
            delta = abs(r_min - sched_min)
            if best_delta is None or delta < best_delta:
                best_delta = delta
                best_idx = idx

        if best_idx is not None:
            used_radar_idx.add(best_idx)
            r = radar.loc[best_idx]
            combined = {**s.to_dict(), **r.to_dict()}
            combined['is_scheduled'] = True
            combined['matched_score'] = 100
            combined['tipo_movimento'] = 'Passeggeri (schedulato + radar)'
            matched.append(combined)
        else:
            combined = dict(s)
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
            combined['callsign'] = combined.get('callsign_volo', '')
            combined['tipo_movimento'] = 'Passeggeri (solo schedulato)'
            matched.append(combined)

    # --- Radar non matchati: tieni solo i cargo ---
    unmatched = radar[~radar.index.isin(used_radar_idx)].copy()
    for _, row in unmatched.iterrows():
        cs = str(row.get('callsign', '') or '')
        cargo, cargo_airline = is_cargo_flight(cs)
        if not cargo:
            # Sorvolo / transito / non identificato: escludi
            continue
        row_dict = row.to_dict()
        row_dict['is_scheduled'] = False
        row_dict['orario_schedulato'] = ''
        row_dict['destinazione_origine'] = ''
        row_dict['matched_score'] = 0
        row_dict['tipo_movimento'] = f'Cargo ({cargo_airline})'
        matched.append(row_dict)

    # Rimuovi colonne temporanee
    result = pd.DataFrame(matched)
    for col in ('_sched_min', '_radar_min'):
        if col in result.columns:
            result = result.drop(columns=[col])

    return _enrich_final(result)


# -----------------------------------------------------------------------------
# ARRICCHIMENTO
# -----------------------------------------------------------------------------

def _enrich_final(df):
    if df.empty:
        return df
    df = df.copy()

    # Se manca 'callsign', usa callsign_volo
    if 'callsign' not in df.columns:
        df['callsign'] = df.get('callsign_volo', 'N/D')
    else:
        df['callsign'] = df['callsign'].fillna(df.get('callsign_volo', 'N/D'))

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
    result_df = match_flights(scheduled_df, radar_df, date_norm)

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