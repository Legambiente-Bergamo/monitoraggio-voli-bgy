"""
bgy_reports/bgy_report_night.py - Report notturno integrato (SACBO + OpenSky).
Versione 2.8.3

Modello logico:
- TABELLONE SACBO: fonte primaria per i voli PASSEGGERI (arrivi + partenze).
- RADAR: arricchisce i passeggeri + identifica Cargo e Charter.

Categorie finali:
  1. Passeggeri        — dal tabellone (con o senza match radar)
  2. Cargo (Nome)      — radar + _cargo_airlines
  3. Charter (Nome)    — radar + _charter_airlines
  4. Passeggeri (radar) — radar + compagnia di linea fuori tabellone
  5. Non identificato  — radar + callsign ignoto

Visibilità:
  - Visibili di default: Passeggeri, Cargo, Charter
  - Opt-in (checkbox GUI): Passeggeri (radar), Non identificato

Novità v2.8.3:
- PAX stimati e rumore calcolati SOLO sui voli Visibili
  (Passeggeri + Cargo + Charter). I voli opt-in (Passeggeri radar,
  Non identificato) restano nel CSV/DB ma non contribuiscono alle
  statistiche principali del report.

Novità v2.8.2:
- Categoria "Passeggeri" unificata.
- Aggiunte "Charter (Nome)" e "Passeggeri (radar)".
- Rimosso match callsign-based (non affidabile).
- SRR (Star Air) spostata in _cargo_airlines.
"""
import os
import math
import pandas as pd
from datetime import datetime, timedelta

from bgy_core import (
    get_airline, get_country, get_aircraft_model,
    is_cargo_flight, is_charter_flight, load_rules, get_logger,
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

MATCH_WINDOW_BEFORE_MIN = 30
MATCH_WINDOW_AFTER_MIN = 180
RADAR_DEDUP_WINDOW_MIN = 15

BGY_PHASES = ('Atterraggio', 'Decollo', 'Avvicinamento')

PLACEHOLDER_PREFIX = 'Compagnia '
PLACEHOLDER_VALUES = {'N/D', 'Non identificato', ''}


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
    if not ts:
        return None
    try:
        dt = pd.to_datetime(ts)
    except Exception:
        return None
    base = pd.to_datetime(f"{session_date} 23:00:00")
    diff = (dt - base).total_seconds() / 60
    if diff < -30:
        return None
    return int(diff)


def _scheduled_minutes_from_session(hhmm, session_date):
    mins = _time_to_minutes(hhmm)
    if mins is None:
        return None
    if mins >= 23 * 60:
        return mins - 23 * 60
    if mins < 6 * 60:
        return mins + 60
    return None


def _is_valid_airline_name(name):
    if not name:
        return False
    if not isinstance(name, str):
        return False
    if name in PLACEHOLDER_VALUES:
        return False
    if name.startswith(PLACEHOLDER_PREFIX):
        return False
    return True


def _is_visible_row(tipo_movimento):
    """Ritorna True se la riga è visibile di default nei report."""
    if not isinstance(tipo_movimento, str):
        return False
    if tipo_movimento == 'Passeggeri':
        return True
    if tipo_movimento.startswith('Cargo'):
        return True
    if tipo_movimento.startswith('Charter'):
        return True
    return False


# -----------------------------------------------------------------------------
# CARICAMENTO DATI
# -----------------------------------------------------------------------------

def load_scheduled_flights(date_str):
    date_norm = normalize_date(date_str)
    date_clean = date_norm.replace("-", "")
    scheduled = []
    seen = set()

    scan_files = []
    if os.path.isdir(RAW_DIR):
        for f in os.listdir(RAW_DIR):
            if not f.startswith("scan_") or not f.endswith(".csv"):
                continue
            if f.startswith(f"scan_{date_norm}_"):
                scan_files.append(f)
            elif f.startswith(f"scan_{date_clean}_"):
                scan_files.append(f)

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
# MATCHING
# -----------------------------------------------------------------------------

def _is_phase_compatible(tipo_movimento, fase_volo):
    if tipo_movimento == 'D':
        return fase_volo == 'Decollo'
    if tipo_movimento == 'A':
        return fase_volo in ('Atterraggio', 'Avvicinamento')
    return False


def match_flights(scheduled_df, radar_df, session_date):
    """Matching tra voli schedulati e radar."""
    if scheduled_df.empty and radar_df.empty:
        return pd.DataFrame()

    # --- Nessun schedulato: solo radar ---
    if scheduled_df.empty:
        if radar_df.empty:
            return pd.DataFrame()
        radar_df = radar_df.copy()
        radar_df['is_scheduled'] = False
        radar_df['orario_schedulato'] = ''
        radar_df['destinazione_origine'] = ''
        radar_df['matched_score'] = 0
        radar_df = _dedup_radar_by_callsign(radar_df)
        classified = _classify_unmatched_radar(radar_df)
        if classified.empty:
            return pd.DataFrame()
        return _enrich_final(classified)

    # --- Nessun radar: tutti Passeggeri ---
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
        scheduled_df['tipo_movimento'] = 'Passeggeri'
        return _enrich_final(scheduled_df)

    # --- Match ---
    sched = scheduled_df.copy()
    radar = radar_df.copy()

    sched['_sched_min'] = sched.apply(
        lambda r: _scheduled_minutes_from_session(
            r.get('orario_schedulato'), session_date),
        axis=1)
    radar['_radar_min'] = radar['timestamp'].apply(
        lambda t: _timestamp_to_minutes_session(t, session_date))

    radar = radar[radar['_radar_min'].notna()].copy()

    matched = []
    used_radar_idx = set()

    for _, s in sched.iterrows():
        sched_min = s['_sched_min']
        tipo_mov = s.get('tipo_movimento', '')

        if sched_min is None:
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
            combined['tipo_movimento'] = 'Passeggeri'
            matched.append(combined)
            continue

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
            combined['tipo_movimento'] = 'Passeggeri'
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
            combined['tipo_movimento'] = 'Passeggeri'
            matched.append(combined)

    # --- Radar non matchati ---
    unmatched = radar[~radar.index.isin(used_radar_idx)].copy()
    unmatched = _dedup_radar_by_callsign(unmatched)
    classified = _classify_unmatched_radar(unmatched)

    for _, row in classified.iterrows():
        matched.append(row.to_dict())

    result = pd.DataFrame(matched)
    for col in ('_sched_min', '_radar_min'):
        if col in result.columns:
            result = result.drop(columns=[col])

    return _enrich_final(result)


def _classify_unmatched_radar(radar_df):
    """Classifica radar non matchati in Cargo / Charter / Passeggeri radar / Non id."""
    if radar_df.empty:
        return radar_df

    classified = []
    skipped_phase = 0
    counts = {'cargo': 0, 'charter': 0, 'pax_radar': 0, 'non_id': 0}

    for _, row in radar_df.iterrows():
        cs = str(row.get('callsign', '') or '').strip()
        fase = str(row.get('fase_volo', '') or '').strip()

        if fase not in BGY_PHASES:
            skipped_phase += 1
            continue

        row_dict = row.to_dict()
        row_dict['is_scheduled'] = False
        row_dict['orario_schedulato'] = ''
        row_dict['destinazione_origine'] = ''
        row_dict['matched_score'] = 0

        cargo, cargo_airline = is_cargo_flight(cs)
        if cargo:
            row_dict['tipo_movimento'] = f'Cargo ({cargo_airline})'
            counts['cargo'] += 1
            classified.append(row_dict)
            continue

        charter, charter_airline = is_charter_flight(cs)
        if charter:
            row_dict['tipo_movimento'] = f'Charter ({charter_airline})'
            counts['charter'] += 1
            classified.append(row_dict)
            continue

        airline_name = get_airline(cs) if cs else 'N/D'
        if _is_valid_airline_name(airline_name):
            row_dict['tipo_movimento'] = 'Passeggeri (radar)'
            counts['pax_radar'] += 1
        else:
            row_dict['tipo_movimento'] = 'Non identificato'
            counts['non_id'] += 1

        classified.append(row_dict)

    if skipped_phase > 0:
        logger.info(f"⏭️  Esclusi {skipped_phase} radar non-BGY (sorvolo/transito)")
    if any(counts.values()):
        logger.info(
            f"📊 Radar non matchati: Cargo={counts['cargo']}, "
            f"Charter={counts['charter']}, "
            f"Passeggeri radar={counts['pax_radar']}, "
            f"Non id={counts['non_id']}"
        )

    if not classified:
        return pd.DataFrame()
    return pd.DataFrame(classified)


def _dedup_radar_by_callsign(radar_df):
    if radar_df.empty or 'callsign' not in radar_df.columns:
        return radar_df

    before = len(radar_df)
    df = radar_df.copy()

    try:
        ts_series = pd.to_datetime(df['timestamp'])
        ts_min = (ts_series.astype('int64') // 60_000_000_000)
        df['_window'] = ts_min // RADAR_DEDUP_WINDOW_MIN
    except Exception as e:
        logger.warning(f"Deduplica radar: impossibile calcolare la finestra: {e}")
        return radar_df

    df = df.sort_values('timestamp').drop_duplicates(
        subset=['callsign', '_window'], keep='first'
    )
    df = df.drop(columns=['_window'])

    after = len(df)
    if before != after:
        logger.info(
            f"🧹 Radar non matchati deduplicati: {before} → {after} "
            f"({before - after} rilevazioni ripetute scartate)"
        )
    return df


# -----------------------------------------------------------------------------
# ARRICCHIMENTO
# -----------------------------------------------------------------------------

def _enrich_final(df):
    if df.empty:
        return df
    df = df.copy()

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

    # --- Conteggi per categoria ---
    total = len(result_df)
    pax = len(result_df[result_df['tipo_movimento'] == 'Passeggeri']) if 'tipo_movimento' in result_df.columns else 0
    cargo = len(result_df[result_df['tipo_movimento'].str.startswith('Cargo', na=False)]) if 'tipo_movimento' in result_df.columns else 0
    charter = len(result_df[result_df['tipo_movimento'].str.startswith('Charter', na=False)]) if 'tipo_movimento' in result_df.columns else 0
    pax_radar = len(result_df[result_df['tipo_movimento'] == 'Passeggeri (radar)']) if 'tipo_movimento' in result_df.columns else 0
    non_id = len(result_df[result_df['tipo_movimento'] == 'Non identificato']) if 'tipo_movimento' in result_df.columns else 0

    visibili = pax + cargo + charter

    # --- Statistiche SOLO sui Visibili (v2.8.3) ---
    visibili_mask = result_df['tipo_movimento'].apply(_is_visible_row) if 'tipo_movimento' in result_df.columns else pd.Series(False, index=result_df.index)
    visibili_df = result_df[visibili_mask]

    pax_tot = int(visibili_df['stima_passeggeri'].sum()) if 'stima_passeggeri' in visibili_df.columns else 0

    if 'stima_rumore_db' in visibili_df.columns:
        rumore_df = visibili_df[visibili_df['stima_rumore_db'] > 0]
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
           f"(Visibili: {visibili} = Passeggeri {pax} + Cargo {cargo} "
           f"+ Charter {charter} | "
           f"Opt-in: {pax_radar + non_id} = Passeggeri radar {pax_radar} "
           f"+ Non id {non_id} | "
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