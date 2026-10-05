"""
bgy_reports/bgy_report_night.py - Report notturno integrato (SACBO + radar).
Versione 2.9.14

Novità v2.9.14 (04/10/2026):
- _split_borderline_flights(): separa i voli schedulati in fascia notturna
  (>= 23:00 o < 06:00) ma operati fuori dalla finestra 23:01-05:59.
  Questi "movimenti borderline" NON sono movimenti notturni e vanno esclusi
  dal report principale (niente rumore, niente KPI).
- Vengono scritti in un CSV dedicato (giornaliero + cumulativo mensile):
    bgy_data/bgy_output/bgy_csv/borderline_YYYY-MM-DD.csv
    bgy_data/bgy_output/bgy_csv/borderline_YYYY-MM.csv
- _categorize_borderline(): assegna categoria ('decollo anticipato',
  'decollo posticipato', 'atterraggio anticipato', 'atterraggio posticipato').

Principio documentato:
- Il rumore conta solo se prodotto tra le 23:01 e le 05:59.
- Un volo schedulato in fascia ma operato fuori è un "borderline" e va
  tracciato separatamente.

Novità v2.9.13: fix out-of-window (post match_flights).
Novità v2.9.12: prima versione del fix (deprecata).
Novità v2.9.11: fix _propagate_runway_in_session (pd.isna).
Novità v2.9.10: raggruppa per solo callsign.
Novità v2.9.9: prima versione del fix propagazione pista.
Novità v2.9.8: esclusione voli pomeridiani da anomalie.
Novità v2.9.7: pattern callsign + priorità numero commerciale.
"""
import os
import re
import math
import csv
from collections import defaultdict
import pandas as pd
from datetime import datetime, timedelta

from bgy_core import (
    get_airline, get_country, get_aircraft_model,
    is_cargo_flight, is_charter_flight, load_rules, get_logger,
    estimate_passengers,
)
from bgy_core.bgy_update_rules import (
    classify_callsign, iata_to_icao_prefix, get_iata_to_icao_map,
)
from bgy_core.bgy_paths import RAW_DIR, OUTPUT_CSV_DIR
from bgy_core.bgy_dates import (
    normalize_date, radar_filename, report_nightly_filename,
    night_session_date,
)
from bgy_core.bgy_config_manager import config_manager
from bgy_core import bgy_db
from bgy_utils.bgy_utils_meteo import save_night_weather

logger = get_logger("ReportNight")

BGY_LAT = 45.6739
BGY_LON = 9.7042

MATCH_WINDOW_BEFORE_MIN = 30
MATCH_WINDOW_AFTER_MIN = 180
MATCH_WINDOW_WIDE_BEFORE_MIN = 180
RADAR_DEDUP_WINDOW_MIN = 15

BGY_PHASES = ('Atterraggio', 'Decollo', 'Avvicinamento')

NIGHT_START_HOUR = 23
NIGHT_END_HOUR = 6
SCONFINAMENTO_START_MIN = 23 * 60 + 1
SCONFINAMENTO_END_MIN = 6 * 60

SCONFINAMENTO_GRAVE_MIN = 60

DAY_START_HOUR = 6
DAY_END_HOUR = 23

SESSION_SCAN_TIMES = ['23-00', '00-00', '00-01', '02-00', '05-00', '06-00']
MEZZANOTTE_SCANS = {'00-00', '00-01'}
SCANSIONE_ANOMALIA = {'02-00', '05-00'}

STATI_A_TERRA = ('IMBARCO', 'IN RITARDO')
STATI_OPERATI = ('DECOLLATO', 'ATTERRATO', 'ARRIVATO', 'IN VOLO', 'PARTITO')

VISIBLE_CATEGORIES = ('Passeggeri', 'Cargo', 'Charter', 'Non classificato')
PAX_CATEGORIES = ('Passeggeri', 'Charter')

_callsign_patterns_cache = None
_inverted_patterns_cache = None


def _cfg():
    return config_manager.get_report_night_config()


# -----------------------------------------------------------------------------
# PATTERNS
# -----------------------------------------------------------------------------

def _load_callsign_patterns():
    global _callsign_patterns_cache
    if _callsign_patterns_cache is not None:
        return _callsign_patterns_cache
    try:
        ok, rows = bgy_db.execute_query(
            "SELECT pattern, airline_iata FROM callsign_airline_patterns")
        if not ok:
            logger.warning(f"Errore caricamento callsign_airline_patterns: {rows}")
            _callsign_patterns_cache = {}
            return {}
        _callsign_patterns_cache = {
            str(r[0]).strip().upper(): str(r[1]).strip().upper()
            for r in (rows or [])
        }
        if _callsign_patterns_cache:
            logger.info(f"📚 Patterns callsign caricati: "
                        f"{len(_callsign_patterns_cache)} voci "
                        f"({', '.join(_callsign_patterns_cache.keys())})")
        else:
            logger.info("📚 Nessun pattern callsign in DB")
        return _callsign_patterns_cache
    except Exception as e:
        logger.warning(f"Errore lettura callsign_airline_patterns: {e}")
        _callsign_patterns_cache = {}
        return {}


def _get_inverted_patterns():
    global _inverted_patterns_cache
    if _inverted_patterns_cache is not None:
        return _inverted_patterns_cache
    patterns = _load_callsign_patterns()
    inv = {}
    for pattern, iata in patterns.items():
        inv.setdefault(iata, []).append(pattern)
    _inverted_patterns_cache = inv
    return inv


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


def _minutes_since_sched(sched, effective):
    sched_min = _time_to_minutes(sched)
    eff_min = _time_to_minutes(effective)
    if sched_min is None or eff_min is None:
        return None
    if eff_min < sched_min:
        eff_min += 24 * 60
    return eff_min - sched_min


def _timestamp_to_minutes_session(ts, session_date):
    if not ts:
        return None
    try:
        dt = pd.to_datetime(ts)
    except Exception:
        return None
    base = pd.to_datetime(f"{session_date} 23:00:00")
    diff = (dt - base).total_seconds() / 60
    if diff < -MATCH_WINDOW_BEFORE_MIN:
        return None
    return int(diff)


def _timestamp_to_minutes_session_wide(ts, session_date):
    if not ts:
        return None
    try:
        dt = pd.to_datetime(ts)
    except Exception:
        return None
    base = pd.to_datetime(f"{session_date} 23:00:00")
    diff = (dt - base).total_seconds() / 60
    if diff < -MATCH_WINDOW_WIDE_BEFORE_MIN:
        return None
    return int(diff)


def _is_timestamp_in_night(ts, session_date):
    if not ts:
        return False
    try:
        dt = pd.to_datetime(ts)
    except Exception:
        return False
    base = pd.to_datetime(f"{session_date} 23:00:00")
    end = base + pd.Timedelta(hours=7)
    return base <= dt < end


def _scheduled_minutes_from_session(hhmm, session_date):
    mins = _time_to_minutes(hhmm)
    if mins is None:
        return None
    if mins >= 23 * 60:
        return mins - 23 * 60
    if mins < 6 * 60:
        return mins + 60
    if mins >= 18 * 60:
        return mins - 23 * 60
    return None


def _is_in_night_schedule(hhmm):
    mins = _time_to_minutes(hhmm)
    if mins is None:
        return False
    return mins >= NIGHT_START_HOUR * 60 or mins < NIGHT_END_HOUR * 60


def _is_in_sconfinamento_effective(hhmm):
    mins = _time_to_minutes(hhmm)
    if mins is None:
        return False
    return mins >= SCONFINAMENTO_START_MIN or mins < SCONFINAMENTO_END_MIN


def _extract_scan_time(filename):
    try:
        base = filename.replace(".csv", "")
        parts = base.split("_")
        if len(parts) >= 3:
            scan_time = parts[2]
            if "-" in scan_time:
                return scan_time
            if len(scan_time) == 4:
                return f"{scan_time[:2]}-{scan_time[2:]}"
    except Exception:
        pass
    return None


def _scan_time_to_order(scan_time):
    try:
        hh, mm = map(int, scan_time.split('-'))
        if hh >= 23:
            return hh * 60 + mm - 23 * 60
        else:
            return (hh + 24) * 60 + mm - 23 * 60
    except Exception:
        return 9999


def _extract_callsign_digits(callsign):
    if not callsign:
        return ''
    return re.sub(r'\D', '', str(callsign))


def _normalize_callsign(callsign):
    if not callsign:
        return ''
    s = str(callsign)
    s = re.sub(r'[\s\u00A0\u200B\u200C\u200D\uFEFF]+', '', s)
    return s.strip().upper()


def _normalize_hhmm(hhmm):
    if not hhmm:
        return ''
    s = str(hhmm)
    s = re.sub(r'[\s\u00A0\u200B\u200C\u200D\uFEFF]+', '', s)
    return s.strip()


# -----------------------------------------------------------------------------
# CONVERSIONE CALLSIGN
# -----------------------------------------------------------------------------

def _split_iata_callsign(callsign_norm):
    if not callsign_norm:
        return None, None
    for pref_len in (2, 3):
        if len(callsign_norm) <= pref_len:
            continue
        prefix = callsign_norm[:pref_len]
        number = callsign_norm[pref_len:]
        if not any(c.isalpha() for c in prefix):
            continue
        if not number.isdigit():
            continue
        return prefix, number
    return None, None


def _icao_prefix_from_sacbo(callsign_sacbo):
    if not callsign_sacbo:
        return None
    cs_norm = _normalize_callsign(callsign_sacbo)
    if not cs_norm:
        return None
    prefix_iata, number = _split_iata_callsign(cs_norm)
    if not prefix_iata:
        return None
    prefix_icao = iata_to_icao_prefix(prefix_iata)
    if not prefix_icao:
        return None
    return prefix_icao.upper()


def _icao_prefix_from_radar(callsign_radar):
    if not callsign_radar:
        return None
    cs = _normalize_callsign(callsign_radar)
    if len(cs) < 3:
        return None
    return cs[:3]


def _extract_icao_number(callsign):
    cs = _normalize_callsign(callsign)
    if len(cs) < 4:
        return None, None
    prefix = cs[:3]
    m = re.search(r'(\d+)$', cs)
    if not m:
        return None, None
    return prefix, m.group(1)


def _extract_iata_number(callsign_sacbo):
    cs = _normalize_callsign(callsign_sacbo)
    if not cs:
        return None, None
    prefix, number = _split_iata_callsign(cs)
    return prefix, number


# -----------------------------------------------------------------------------
# MATCH RADAR PER CLASSIFICAZIONE
# -----------------------------------------------------------------------------

def _find_radar_match_ts(callsign_sacbo, direzione_sacbo, sched, radar_df,
                          session_date):
    if radar_df is None or radar_df.empty:
        return None
    prefix_sacbo = _icao_prefix_from_sacbo(callsign_sacbo)
    if not prefix_sacbo:
        return None
    sched_min = _scheduled_minutes_from_session(sched, session_date)
    if sched_min is None:
        return None
    low = sched_min - MATCH_WINDOW_WIDE_BEFORE_MIN
    high = sched_min + MATCH_WINDOW_AFTER_MIN

    best_ts = None
    best_delta = None

    for _, r in radar_df.iterrows():
        prefix_radar = _icao_prefix_from_radar(r.get('callsign', ''))
        if prefix_radar != prefix_sacbo:
            continue
        fase = str(r.get('fase_volo', '') or '')
        if not _is_phase_compatible(direzione_sacbo, fase):
            continue
        r_min = _timestamp_to_minutes_session_wide(r.get('timestamp'), session_date)
        if r_min is None or r_min < low or r_min > high:
            continue
        delta = abs(r_min - sched_min)
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_ts = r.get('timestamp')

    return best_ts


# -----------------------------------------------------------------------------
# CLASSIFICAZIONE VOLO
# -----------------------------------------------------------------------------

def _tipo_movimento_from_callsign(callsign, source):
    categoria, nome = classify_callsign(callsign)
    if categoria == 'Cargo':
        return f'Cargo ({nome})' if nome else 'Cargo (N/D)'
    if categoria == 'Charter':
        return f'Charter ({nome})' if nome else 'Charter (N/D)'
    if categoria == 'Passeggeri':
        return 'Passeggeri' if source == 'sacbo' else 'Passeggeri (radar)'
    return 'Non classificato'


def _radar_confirms_flight(callsign, radar_df):
    if radar_df is None or radar_df.empty:
        return False, None
    callsign_digits = _extract_callsign_digits(callsign)
    if not callsign_digits:
        return False, None
    try:
        for _, row in radar_df.iterrows():
            radar_cs = str(row.get('callsign', '')).strip()
            if not radar_cs:
                continue
            radar_digits = _extract_callsign_digits(radar_cs)
            if radar_digits == callsign_digits:
                return True, str(row.get('timestamp', ''))
    except Exception as e:
        logger.debug(f"Errore radar confirm per {callsign}: {e}")
    return False, None


def _classify_volo(records, radar_df=None, session_date=None):
    if not records:
        return None

    sched = records[0]['orario_schedulato']
    callsign = records[0].get('callsign_volo', '')
    direzione_sacbo = str(records[0].get('tipo_movimento', '')).strip().upper()[:1]

    sched_min_check = _time_to_minutes(sched)
    if sched_min_check is not None:
        if 6 * 60 <= sched_min_check < 17 * 60:
            logger.debug(
                f"⏭️  {callsign}: schedulato {sched} (pieno giorno), "
                f"fuori scope sessione notturna"
            )
            return None

    if _is_in_night_schedule(sched):
        return 'regolare'

    ref = None
    ref_index = None
    for i, r in enumerate(records):
        if r['scan_time'] in MEZZANOTTE_SCANS:
            continue
        ref = r
        ref_index = i
        break

    if ref is None:
        ref = records[0]
        ref_index = 0

    stato_ref = str(ref.get('stato_volo', '')).upper()
    is_operato = any(s in stato_ref for s in STATI_OPERATI)
    is_a_terra = any(s in stato_ref for s in STATI_A_TERRA)

    if is_operato:
        return None

    for r in records:
        stato = str(r.get('stato_volo', '')).upper()
        if 'CANCELLAT' in stato or 'CANCEL' in stato:
            return None

    scansioni_succ = [
        r['scan_time'] for r in records[ref_index + 1:]
        if r['scan_time'] not in MEZZANOTTE_SCANS
    ]

    radar_ts = None
    if radar_df is not None and callsign and session_date:
        radar_ts = _find_radar_match_ts(
            callsign, direzione_sacbo, sched, radar_df, session_date
        )

    if radar_ts:
        try:
            radar_dt = pd.to_datetime(radar_ts)
            radar_hour = radar_dt.hour
            if DAY_START_HOUR <= radar_hour < DAY_END_HOUR:
                logger.info(
                    f"⏭️  {callsign}: radar conferma operatività alle "
                    f"{radar_dt.strftime('%H:%M')} (< 23:00), "
                    f"non è sconfinamento"
                )
                return None
        except Exception as e:
            logger.debug(f"Errore parsing timestamp radar per {callsign}: {e}")

    stima_ref = ref.get('orario_effettivo')
    if stima_ref and _is_in_sconfinamento_effective(stima_ref):
        for r in records[ref_index + 1:]:
            if r['scan_time'] in MEZZANOTTE_SCANS:
                continue
            stima = r.get('orario_effettivo')
            if stima and not _is_in_sconfinamento_effective(stima):
                return None
        delay = _minutes_since_sched(sched, stima_ref)
        if delay is not None and delay >= SCONFINAMENTO_GRAVE_MIN:
            return 'sconfinamento_grave'
        return 'sconfinamento'

    if not is_a_terra:
        return None

    if any(t in SCANSIONE_ANOMALIA for t in scansioni_succ):
        return 'anomalia'

    delay = None

    if radar_ts:
        try:
            radar_dt = pd.to_datetime(radar_ts)
            radar_hhmm = radar_dt.strftime('%H:%M')
            delay = _minutes_since_sched(sched, radar_hhmm)
            logger.info(f"✅ Sconfinamento {callsign} confermato da radar "
                        f"({radar_ts}, delay {delay} min)")
        except Exception as e:
            logger.debug(f"Errore parsing timestamp radar per {callsign}: {e}")

    if delay is None:
        delay = _minutes_since_sched(sched, '23:00')
        if radar_df is not None and callsign:
            logger.info(f"⚠️  Sconfinamento {callsign} NON confermato da radar "
                        f"(sched={sched}, delay min {delay} min, "
                        f"stato={stato_ref[:30]})")

    if delay is not None and delay >= SCONFINAMENTO_GRAVE_MIN:
        return 'sconfinamento_grave'
    return 'sconfinamento'


# -----------------------------------------------------------------------------
# CARICAMENTO DATI
# -----------------------------------------------------------------------------

def load_scheduled_flights(date_str, radar_df=None):
    date_norm = normalize_date(date_str)
    next_date = (datetime.strptime(date_norm, "%Y-%m-%d")
                 + timedelta(days=1)).strftime("%Y-%m-%d")
    date_clean = date_norm.replace("-", "")
    next_clean = next_date.replace("-", "")

    scan_files = []
    if os.path.isdir(RAW_DIR):
        for f in os.listdir(RAW_DIR):
            if not f.startswith("scan_") or not f.endswith(".csv"):
                continue
            scan_time = _extract_scan_time(f)
            if not scan_time or scan_time not in SESSION_SCAN_TIMES:
                continue
            if f.startswith(f"scan_{date_norm}_") or f.startswith(f"scan_{date_clean}_"):
                try:
                    hh = int(scan_time.split("-")[0])
                    if hh >= 23:
                        scan_files.append(f)
                except Exception:
                    pass
            elif f.startswith(f"scan_{next_date}_") or f.startswith(f"scan_{next_clean}_"):
                try:
                    hh = int(scan_time.split("-")[0])
                    if hh < 6:
                        scan_files.append(f)
                except Exception:
                    pass

    scan_files.sort()
    logger.info(f"🔎 Scansioni notturne trovate: {len(scan_files)}")

    flights = defaultdict(list)

    for f in scan_files:
        filepath = os.path.join(RAW_DIR, f)
        scan_time = _extract_scan_time(f)
        if not scan_time:
            continue
        try:
            df = pd.read_csv(filepath)
            df = normalize_scan_columns(df)
            for _, row in df.iterrows():
                sched_raw = row.get('orario_schedulato')
                if not sched_raw:
                    continue
                cs_raw = row.get('callsign_volo', '')
                cs_norm = _normalize_callsign(cs_raw)
                sched_norm = _normalize_hhmm(sched_raw)
                if not cs_norm or not sched_norm:
                    continue
                key = (cs_norm, sched_norm)
                flights[key].append({
                    'scan_time': scan_time,
                    'callsign_volo': cs_norm,
                    'orario_schedulato': sched_norm,
                    'orario_effettivo': row.get('orario_effettivo'),
                    'stato_volo': row.get('stato_volo'),
                    'tipo_movimento': row.get('tipo_movimento'),
                    'destinazione_origine': row.get('destinazione_origine'),
                })
        except Exception as e:
            logger.warning(f"Errore lettura {f}: {e}")

    for key in flights:
        flights[key].sort(key=lambda r: _scan_time_to_order(r['scan_time']))

    scheduled = []
    n_regolare = 0
    n_sconfinamento = 0
    n_sconfinamento_grave = 0
    n_anomalia = 0
    n_esclusi = 0

    for key, records in flights.items():
        categoria = _classify_volo(
            records, radar_df=radar_df, session_date=date_norm
        )
        if categoria is None:
            n_esclusi += 1
            continue
        row_dict = None
        for r in reversed(records):
            stima = r.get('orario_effettivo')
            if stima and _is_in_sconfinamento_effective(stima):
                row_dict = r.copy()
                break
        if row_dict is None:
            row_dict = records[-1].copy()
        row_dict.pop('scan_time', None)
        direzione = str(row_dict.get('tipo_movimento', '')).strip().upper()[:1]
        row_dict['direzione_sacbo'] = direzione
        row_dict['notte_categoria'] = categoria
        row_dict.pop('tipo_movimento', None)
        scheduled.append(row_dict)

        if categoria == 'regolare':
            n_regolare += 1
        elif categoria == 'sconfinamento':
            n_sconfinamento += 1
        elif categoria == 'sconfinamento_grave':
            n_sconfinamento_grave += 1
        elif categoria == 'anomalia':
            n_anomalia += 1

    if scheduled:
        df_sched = pd.DataFrame(scheduled)
        logger.info(
            f"📋 Caricati {len(df_sched)} voli schedulati notturni "
            f"(regolari {n_regolare}, sconfinamenti {n_sconfinamento}, "
            f"gravi {n_sconfinamento_grave}, anomalie {n_anomalia}, "
            f"esclusi {n_esclusi})"
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


def _propagate_runway_in_session(radar_df):
    if radar_df.empty or 'callsign' not in radar_df.columns:
        return radar_df
    if 'pista' not in radar_df.columns:
        return radar_df

    df = radar_df.copy()

    def _clean_pista(p):
        if p is None:
            return ""
        try:
            if pd.isna(p):
                return ""
        except (TypeError, ValueError):
            pass
        s = str(p).strip()
        if s in ("", "N/D", "nan", "None", "NaN"):
            return ""
        return s

    df['_pista_clean'] = df['pista'].apply(_clean_pista)

    pista_map = {}
    for _, row in df.iterrows():
        cs = str(row.get('callsign', '') or '').strip().upper()
        if not cs:
            continue
        if cs in pista_map:
            continue
        p = row['_pista_clean']
        if p in ('RWY 28', 'RWY 10'):
            pista_map[cs] = p

    n_filled = 0
    for idx, row in df.iterrows():
        if row['_pista_clean']:
            continue
        cs = str(row.get('callsign', '') or '').strip().upper()
        if not cs:
            continue
        p = pista_map.get(cs)
        if p:
            df.at[idx, 'pista'] = p
            n_filled += 1

    df = df.drop(columns=['_pista_clean'])

    if n_filled > 0:
        logger.info(f"📡 Propagazione pista: {n_filled} rilevamenti N/D "
                    f"hanno ereditato la pista dal callsign")
    else:
        logger.info("📡 Propagazione pista: nessun rilevamento da propagare")

    return df


def load_radar_data(date_str):
    date_norm = normalize_date(date_str)
    next_date = (datetime.strptime(date_norm, "%Y-%m-%d")
                 + timedelta(days=1)).strftime("%Y-%m-%d")

    files_to_load = [
        (date_norm, _find_scan_file_for_date(date_norm)),
        (next_date, _find_scan_file_for_date(next_date)),
    ]

    dfs = []
    for label, filepath in files_to_load:
        if filepath:
            try:
                df = pd.read_csv(filepath)
                logger.info(f"📡 Caricati {len(df)} dati radar da "
                            f"{os.path.basename(filepath)} ({label})")
                dfs.append(df)
            except Exception as e:
                logger.warning(f"Errore lettura radar {filepath}: {e}")
        else:
            logger.info(f"📡 Nessun file radar per {label}")

    if not dfs:
        logger.info(f"📡 Nessun dato radar disponibile per la sessione {date_norm}")
        return pd.DataFrame()

    combined = pd.concat(dfs, ignore_index=True)
    logger.info(f"📡 Totale radar sessione: {len(combined)} rilevamenti "
                f"({len(dfs)} file)")

    combined = _propagate_runway_in_session(combined)

    return combined


# -----------------------------------------------------------------------------
# MATCHING
# -----------------------------------------------------------------------------

def _is_phase_compatible(direzione_sacbo, fase_volo):
    if direzione_sacbo == 'D':
        return fase_volo == 'Decollo'
    if direzione_sacbo == 'A':
        return fase_volo in ('Atterraggio', 'Avvicinamento')
    return False


def _phase_priority(fase_volo):
    priorities = {
        'Atterraggio': 4,
        'Decollo': 3,
        'Avvicinamento': 2,
        'Non rilevato': 1,
        'N/D': 0,
        '': 0,
    }
    return priorities.get(str(fase_volo).strip(), 1)


def _dedup_by_key(df):
    if df.empty:
        return df
    has_sched_mask = df['orario_schedulato'].apply(
        lambda x: bool(str(x).strip()) if pd.notna(x) else False
    )
    with_sched = df[has_sched_mask].copy()
    without_sched = df[~has_sched_mask].copy()
    if with_sched.empty:
        return df
    with_sched['_key_cs'] = with_sched['callsign'].apply(_normalize_callsign)
    with_sched['_key_sched'] = with_sched['orario_schedulato'].apply(_normalize_hhmm)
    with_sched['_is_sched_priority'] = with_sched['is_scheduled'].apply(
        lambda x: 1 if x is True or str(x).lower() == 'true' else 0
    )
    with_sched['_phase_priority'] = with_sched['fase_volo'].apply(_phase_priority)
    with_sched['_ts_priority'] = with_sched['timestamp'].apply(
        lambda t: str(t) if pd.notna(t) and str(t).strip() else ''
    )
    with_sched = with_sched.sort_values(
        by=['_is_sched_priority', '_phase_priority', '_ts_priority'],
        ascending=[False, False, False]
    )
    before = len(with_sched)
    with_sched = with_sched.drop_duplicates(
        subset=['_key_cs', '_key_sched'], keep='first'
    )
    after = len(with_sched)
    removed = before - after
    if removed > 0:
        logger.info(f"🧹 Deduplicati {removed} voli con chiave duplicata "
                    f"(callsign, orario_schedulato)")
    with_sched = with_sched.drop(columns=[
        '_key_cs', '_key_sched', '_is_sched_priority',
        '_phase_priority', '_ts_priority'
    ])
    result = pd.concat([with_sched, without_sched], ignore_index=True)
    return result


def _try_pattern_match_for_sched(sched_callsign, direzione_sacbo,
                                  sched_min, low, high, radar,
                                  used_radar_idx, inv_patterns):
    if not sched_callsign:
        return None, None
    iata_sched, num_sched = _extract_iata_number(sched_callsign)
    if not iata_sched or not num_sched:
        return None, None
    patterns_for_iata = inv_patterns.get(iata_sched.upper(), [])
    if not patterns_for_iata:
        return None, None

    best_idx = None
    best_delta = None

    for idx, r in radar.iterrows():
        if idx in used_radar_idx:
            continue
        r_min = r['_radar_min']
        if r_min is None or r_min < low or r_min > high:
            continue
        fase = str(r.get('fase_volo', '') or '')
        if not _is_phase_compatible(direzione_sacbo, fase):
            continue

        prefix_radar, num_radar = _extract_icao_number(r.get('callsign', ''))
        if not prefix_radar or not num_radar:
            continue
        if prefix_radar.upper() not in [p.upper() for p in patterns_for_iata]:
            continue
        if num_radar != num_sched:
            continue

        delta = abs(r_min - sched_min)
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_idx = idx

    return best_idx, best_delta


def match_flights(scheduled_df, radar_df, session_date):
    if scheduled_df.empty and radar_df.empty:
        return pd.DataFrame()

    if scheduled_df.empty:
        if radar_df.empty:
            return pd.DataFrame()
        radar_df = radar_df.copy()
        radar_df['is_scheduled'] = False
        radar_df['orario_schedulato'] = ''
        radar_df['destinazione_origine'] = ''
        radar_df['direzione_sacbo'] = ''
        radar_df['notte_categoria'] = ''
        radar_df['matched_score'] = 0
        radar_df = radar_df[
            radar_df['timestamp'].apply(
                lambda t: _is_timestamp_in_night(t, session_date))
        ].copy()
        radar_df = _dedup_radar_by_callsign(radar_df)
        classified = _classify_unmatched_radar(radar_df)
        if classified.empty:
            return pd.DataFrame()
        return _enrich_final(classified)

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
        scheduled_df['tipo_movimento'] = scheduled_df['callsign_volo'].apply(
            lambda cs: _tipo_movimento_from_callsign(cs, source='sacbo')
        )
        return _enrich_final(scheduled_df)

    sched = scheduled_df.copy()
    radar = radar_df.copy()

    sched['_sched_min'] = sched.apply(
        lambda r: _scheduled_minutes_from_session(
            r.get('orario_schedulato'), session_date),
        axis=1)
    radar['_radar_min'] = radar['timestamp'].apply(
        lambda t: _timestamp_to_minutes_session(t, session_date))

    radar = radar[radar['_radar_min'].notna()].copy()

    patterns = _load_callsign_patterns()
    inv_patterns = _get_inverted_patterns()

    matched = []
    used_radar_idx = set()
    n_match_ok = 0
    n_match_num = 0
    n_match_pattern = 0
    n_match_rejected_prefix = 0
    n_match_prefix_unknown = 0

    for _, s in sched.iterrows():
        sched_min = s['_sched_min']
        direzione = s.get('direzione_sacbo', '')
        categoria = s.get('notte_categoria', '')
        callsign_sched = s.get('callsign_volo', '')
        cs_sacbo_norm = _normalize_callsign(callsign_sched)
        tipo_mov = _tipo_movimento_from_callsign(callsign_sched, source='sacbo')

        prefix_sacbo = _icao_prefix_from_sacbo(callsign_sched)
        _, num_sched = _extract_iata_number(callsign_sched)

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
            combined['callsign'] = cs_sacbo_norm
            combined['tipo_movimento'] = tipo_mov
            combined['notte_categoria'] = categoria
            matched.append(combined)
            continue

        low = sched_min - MATCH_WINDOW_BEFORE_MIN
        high = sched_min + MATCH_WINDOW_AFTER_MIN

        best_idx = None
        best_delta = None
        best_num_idx = None
        best_num_delta = None

        for idx, r in radar.iterrows():
            if idx in used_radar_idx:
                continue
            r_min = r['_radar_min']
            if r_min is None or r_min < low or r_min > high:
                continue
            fase = str(r.get('fase_volo', '') or '')
            if not _is_phase_compatible(direzione, fase):
                continue

            prefix_radar = _icao_prefix_from_radar(r.get('callsign', ''))
            if prefix_sacbo is None:
                n_match_prefix_unknown += 1
                continue
            if prefix_radar is None or prefix_sacbo != prefix_radar:
                n_match_rejected_prefix += 1
                continue

            delta = abs(r_min - sched_min)

            _, num_radar = _extract_icao_number(r.get('callsign', ''))
            is_num_match = (
                num_sched is not None
                and num_radar is not None
                and num_sched == num_radar
            )

            if is_num_match:
                if best_num_delta is None or delta < best_num_delta:
                    best_num_delta = delta
                    best_num_idx = idx
            else:
                if best_delta is None or delta < best_delta:
                    best_delta = delta
                    best_idx = idx

        used_num_match = False
        if best_num_idx is not None:
            best_idx = best_num_idx
            best_delta = best_num_delta
            used_num_match = True

        used_pattern_match = False
        if best_idx is None:
            pat_idx, pat_delta = _try_pattern_match_for_sched(
                callsign_sched, direzione, sched_min, low, high,
                radar, used_radar_idx, inv_patterns
            )
            if pat_idx is not None:
                best_idx = pat_idx
                best_delta = pat_delta
                used_pattern_match = True

        if best_idx is not None:
            used_radar_idx.add(best_idx)
            r = radar.loc[best_idx]
            combined = {**s.to_dict(), **r.to_dict()}
            combined['is_scheduled'] = True
            combined['matched_score'] = 100
            combined['tipo_movimento'] = tipo_mov
            combined['notte_categoria'] = categoria
            combined['callsign_radar'] = r.get('callsign', '')
            combined['callsign'] = cs_sacbo_norm
            matched.append(combined)
            n_match_ok += 1
            if used_num_match:
                n_match_num += 1
            if used_pattern_match:
                n_match_pattern += 1
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
            combined['callsign'] = cs_sacbo_norm
            combined['tipo_movimento'] = tipo_mov
            combined['notte_categoria'] = categoria
            matched.append(combined)

    logger.info(f"🔗 Match radar: {n_match_ok} confermati "
                f"(di cui {n_match_num} per numero, "
                f"{n_match_pattern} per pattern), "
                f"{n_match_rejected_prefix} rifiutati per prefisso, "
                f"{n_match_prefix_unknown} senza prefisso ICAO")

    unmatched = radar[~radar.index.isin(used_radar_idx)].copy()
    before_night_filter = len(unmatched)
    unmatched = unmatched[
        unmatched['timestamp'].apply(
            lambda t: _is_timestamp_in_night(t, session_date))
    ].copy()
    after_night_filter = len(unmatched)
    if before_night_filter != after_night_filter:
        logger.info(f"⏭️  Esclusi {before_night_filter - after_night_filter} "
                    f"radar unmatched fuori fascia notturna")

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
    if radar_df.empty:
        return radar_df
    classified = []
    skipped_phase = 0
    counts = {'cargo': 0, 'charter': 0, 'pax_radar': 0, 'non_class': 0}

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
        if 'notte_categoria' not in row_dict or not row_dict.get('notte_categoria'):
            row_dict['notte_categoria'] = ''
        if 'direzione_sacbo' not in row_dict or not row_dict.get('direzione_sacbo'):
            if fase == 'Decollo':
                row_dict['direzione_sacbo'] = 'D'
            elif fase in ('Atterraggio', 'Avvicinamento'):
                row_dict['direzione_sacbo'] = 'A'
            else:
                row_dict['direzione_sacbo'] = '?'
        categoria, nome = classify_callsign(cs)
        if categoria == 'Cargo':
            row_dict['tipo_movimento'] = f'Cargo ({nome})' if nome else 'Cargo (N/D)'
            counts['cargo'] += 1
        elif categoria == 'Charter':
            row_dict['tipo_movimento'] = f'Charter ({nome})' if nome else 'Charter (N/D)'
            counts['charter'] += 1
        elif categoria == 'Passeggeri':
            row_dict['tipo_movimento'] = 'Passeggeri (radar)'
            counts['pax_radar'] += 1
        else:
            row_dict['tipo_movimento'] = 'Non classificato'
            counts['non_class'] += 1
        classified.append(row_dict)

    if skipped_phase > 0:
        logger.info(f"⏭️  Esclusi {skipped_phase} radar non-BGY (sorvolo/transito)")
    if any(counts.values()):
        logger.info(
            f"📊 Radar non matchati: Cargo={counts['cargo']}, "
            f"Charter={counts['charter']}, "
            f"Passeggeri radar={counts['pax_radar']}, "
            f"Non classificato={counts['non_class']}"
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

    if 'direzione_sacbo' not in df.columns:
        df['direzione_sacbo'] = ''
    if 'notte_categoria' not in df.columns:
        df['notte_categoria'] = ''
    else:
        df['notte_categoria'] = df['notte_categoria'].fillna('')

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
        tipo = str(row.get('tipo_movimento', '') or '').strip()
        is_pax_category = (
            tipo == 'Passeggeri'
            or tipo == 'Passeggeri (radar)'
            or tipo.startswith('Charter')
        )
        if not is_pax_category:
            return 0
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
# BORDERLINE (v2.9.14)
# -----------------------------------------------------------------------------

def _split_borderline_flights(result_df):
    """
    v2.9.14: separa i voli schedulati in fascia notturna (>= 23:00 o < 06:00)
    ma operati fuori dalla finestra 23:01-05:59.

    Questi "borderline" NON sono movimenti notturni: il rumore da loro
    prodotto non è rumore notturno, e non devono apparire nei KPI.

    Ritorna (df_ok, df_borderline, n_esclusi).
    """
    if result_df.empty:
        return result_df, result_df.iloc[0:0], 0

    if 'orario_schedulato' not in result_df.columns:
        return result_df, result_df.iloc[0:0], 0
    if 'timestamp' not in result_df.columns:
        return result_df, result_df.iloc[0:0], 0

    def _is_borderline(row):
        sched = row.get('orario_schedulato')
        ts = row.get('timestamp')
        if not sched or pd.isna(sched):
            return False
        if not ts or pd.isna(ts) or str(ts).strip() == '':
            return False

        sched_min = _time_to_minutes(sched)
        if sched_min is None:
            return False
        # Solo voli schedulati in fascia notturna
        if not (sched_min >= 23 * 60 or sched_min < 6 * 60):
            return False

        try:
            ts_dt = pd.to_datetime(ts)
        except Exception:
            return False

        # Finestra "vera" del rumore notturno: 23:01 - 05:59
        h = ts_dt.hour
        m = ts_dt.minute
        minutes = h * 60 + m

        # In finestra: 23:01 <= minuti < 06:00 → 1381 <= m < 360 (ciclo)
        # Uso: notturno = (m >= 1381) or (m < 360)
        in_window = (minutes >= 1381) or (minutes < 360)
        return not in_window

    mask = result_df.apply(_is_borderline, axis=1)
    n_excluded = int(mask.sum())
    df_borderline = result_df[mask].copy()
    df_ok = result_df[~mask].reset_index(drop=True)

    return df_ok, df_borderline, n_excluded


def _categorize_borderline(row):
    """
    Ritorna una stringa che descrive il tipo di borderline.
    Categorie:
    - 'decollo posticipato' (sched in fascia, decollo dopo 06:00)
    - 'decollo anticipato'  (sched in fascia, decollo prima di 23:01)
    - 'atterraggio posticipato'
    - 'atterraggio anticipato'
    - 'borderline altro'
    """
    sched = row.get('orario_schedulato')
    ts = row.get('timestamp')
    direzione = str(row.get('direzione_sacbo', '') or '').upper()

    if not sched or not ts:
        return 'borderline altro'

    sched_min = _time_to_minutes(sched)
    try:
        ts_dt = pd.to_datetime(ts)
    except Exception:
        return 'borderline altro'

    ts_min = ts_dt.hour * 60 + ts_dt.minute

    # Anticipato se operato < 23:01 (cioè tra 00:00 e 23:00 di oggi)
    # Posticipato se operato >= 06:00 (e < 23:00)
    anticipato = (ts_min < 1381) and (ts_min >= 360)  # 06:00-22:59
    posticipato = (ts_min < 1381) and (ts_min >= 360)  # stessa condizione

    # In realtà la distinzione anticipato/posticipato dipende dal momento
    # della schedulazione:
    # - sched >= 23:00 (sera) e operato < 23:00 → anticipato
    # - sched < 06:00 (mattina) e operato >= 06:00 → posticipato
    if sched_min >= 23 * 60:
        tipo = 'anticipato' if (ts_min >= 360 and ts_min < 1381) else 'altro'
    elif sched_min < 6 * 60:
        tipo = 'posticipato' if (ts_min >= 360 and ts_min < 1381) else 'altro'
    else:
        tipo = 'altro'

    if direzione == 'D':
        return f'decollo {tipo}'.strip()
    if direzione == 'A':
        return f'atterraggio {tipo}'.strip()
    return f'movimento {tipo}'.strip()


def _write_borderline_files(date_norm, df_borderline):
    """
    Scrive i borderline in:
    - bgy_data/bgy_output/bgy_csv/borderline_YYYY-MM-DD.csv
    - bgy_data/bgy_output/bgy_csv/borderline_YYYY-MM.csv (cumulativo)
    """
    if df_borderline.empty:
        logger.info("📋 Nessun borderline da registrare")
        return None

    os.makedirs(OUTPUT_CSV_DIR, exist_ok=True)

    # Colonne ordinate
    cols = [
        'data_riferimento', 'callsign', 'compagnia_aerea', 'tipo_movimento',
        'direzione_sacbo', 'orario_schedulato', 'timestamp',
        'fase_volo', 'pista', 'categoria_borderline',
    ]
    df_out = df_borderline.copy()
    df_out['data_riferimento'] = date_norm
    df_out['categoria_borderline'] = df_out.apply(_categorize_borderline, axis=1)

    for c in cols:
        if c not in df_out.columns:
            df_out[c] = ''

    df_out = df_out[cols].copy()

    # File giornaliero
    daily_path = os.path.join(OUTPUT_CSV_DIR, f"borderline_{date_norm}.csv")
    df_out.to_csv(daily_path, index=False, encoding='utf-8-sig')
    logger.info(f"📋 Borderline registrati: {daily_path} ({len(df_out)} casi)")

    # File cumulativo mensile
    ym = date_norm[:7]
    monthly_path = os.path.join(OUTPUT_CSV_DIR, f"borderline_{ym}.csv")

    # Se esiste, carica e rimuovi eventuali righe della stessa data (reimport)
    if os.path.exists(monthly_path):
        try:
            old = pd.read_csv(monthly_path)
            old = old[old['data_riferimento'] != date_norm]
            df_all = pd.concat([old, df_out], ignore_index=True)
        except Exception as e:
            logger.warning(f"Errore lettura {monthly_path}: {e}. Ricreo.")
            df_all = df_out
    else:
        df_all = df_out

    df_all.to_csv(monthly_path, index=False, encoding='utf-8-sig')
    logger.info(f"📋 Borderline cumulativo mensile: {monthly_path}")

    return daily_path


# -----------------------------------------------------------------------------
# GENERAZIONE
# -----------------------------------------------------------------------------

def generate_nightly_report(date_str=None):
    load_rules()
    date_norm = normalize_date(date_str) if date_str else night_session_date()
    logger.info(f"🌙 Avvio report notturno per {date_norm} (23:00-05:59)")

    radar_df = load_radar_data(date_norm)
    scheduled_df = load_scheduled_flights(date_norm, radar_df=radar_df)
    result_df = match_flights(scheduled_df, radar_df, date_norm)

    if result_df.empty:
        logger.warning(f"⚠️ Nessun dato per {date_norm}")
        return None, f"Nessun dato per {date_norm}"

    # v2.9.14: separa i borderline (schedulati in fascia, operati fuori)
    result_df, df_borderline, n_borderline = _split_borderline_flights(result_df)

    # Log dettagliato dei borderline
    for _, row in df_borderline.iterrows():
        cs = row.get('callsign', '?')
        sched = row.get('orario_schedulato', '?')
        ts = row.get('timestamp', '?')
        cat = _categorize_borderline(row)
        logger.info(
            f"⚠️  BORDERLINE {cs}: sched {sched} → operato {ts} ({cat})"
        )

    # Scrivi i file borderline
    _write_borderline_files(date_norm, df_borderline)

    before_dedup = len(result_df)
    result_df = _dedup_by_key(result_df)
    after_dedup = len(result_df)
    if before_dedup != after_dedup:
        logger.info(f"🧹 Deduplica finale: {before_dedup} → {after_dedup} righe "
                    f"({before_dedup - after_dedup} rimosse)")

    os.makedirs(OUTPUT_CSV_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_CSV_DIR, report_nightly_filename(date_norm))

    final_columns = [
        'callsign', 'tipo_movimento', 'direzione_sacbo', 'notte_categoria',
        'is_scheduled',
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
    tm = result_df['tipo_movimento'].fillna('') if 'tipo_movimento' in result_df.columns else pd.Series([''] * total)

    pax = int((tm == 'Passeggeri').sum())
    cargo = int(tm.str.startswith('Cargo', na=False).sum())
    charter = int(tm.str.startswith('Charter', na=False).sum())
    non_class = int((tm == 'Non classificato').sum())
    pax_radar = int((tm == 'Passeggeri (radar)').sum())

    visibili = pax + cargo + charter + non_class
    optin = pax_radar

    n_sconfinamenti = 0
    n_sconfinamenti_gravi = 0
    n_anomalie = 0
    if 'notte_categoria' in result_df.columns:
        visibili_mask = tm.apply(
            lambda x: isinstance(x, str) and (
                x == 'Passeggeri'
                or x == 'Non classificato'
                or x.startswith('Cargo')
                or x.startswith('Charter')
            )
        )
        n_sconfinamenti = int(
            ((result_df['notte_categoria'] == 'sconfinamento') & visibili_mask).sum()
        )
        n_sconfinamenti_gravi = int(
            ((result_df['notte_categoria'] == 'sconfinamento_grave') & visibili_mask).sum()
        )
        n_anomalie = int(
            ((result_df['notte_categoria'] == 'anomalia') & visibili_mask).sum()
        )

    visibili_pax_mask = tm.apply(
        lambda x: isinstance(x, str) and (
            x == 'Passeggeri'
            or x.startswith('Charter')
        )
    )
    visibili_pax_df = result_df[visibili_pax_mask]
    pax_tot = int(visibili_pax_df['stima_passeggeri'].sum()) if 'stima_passeggeri' in visibili_pax_df.columns else 0

    visibili_all_mask = tm.apply(
        lambda x: isinstance(x, str) and (
            x == 'Passeggeri'
            or x == 'Non classificato'
            or x.startswith('Cargo')
            or x.startswith('Charter')
        )
    )
    rumore_df = result_df[visibili_all_mask]
    if 'stima_rumore_db' in rumore_df.columns:
        rumore_df = rumore_df[rumore_df['stima_rumore_db'] > 0]
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

    sconf_tot = n_sconfinamenti + n_sconfinamenti_gravi
    sconf_msg = ""
    if sconf_tot > 0:
        if n_sconfinamenti_gravi > 0:
            sconf_msg = f", sconfinamenti {sconf_tot} (di cui {n_sconfinamenti_gravi} gravi)"
        else:
            sconf_msg = f", sconfinamenti {sconf_tot}"
    anomalie_msg = f", anomalie {n_anomalie}" if n_anomalie > 0 else ""
    borderline_msg = (f", borderline {n_borderline}" if n_borderline > 0 else "")

    msg = (f"✅ Report notturno: {total} voli "
           f"(Visibili: {visibili} = Passeggeri {pax} + Cargo {cargo} "
           f"+ Charter {charter} + Non classificato {non_class}{sconf_msg}{anomalie_msg}{borderline_msg} | "
           f"Opt-in: {optin} = Passeggeri radar {pax_radar} | "
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