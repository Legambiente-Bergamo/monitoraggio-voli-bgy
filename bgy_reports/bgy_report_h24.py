"""
bgy_reports/bgy_report_h24.py - Report H24 integrato (SACBO + Avionio + radar).
Versione 1.0.15

Novita v1.0.15 (27/10/2026, BUG-18/DST):
- _scheduled_minutes_h24_utc: se il giorno attraversa DST, anche lo scheduled
  viene convertito in UTC per allinearlo al radar e evitare falsi anticipi.
- logic_version portata a 1.0.15.
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

from bgy_reports.bgy_report_common import (
    propagate_runway_in_session,
    fill_unknown_runways_geometric,
)

logger = get_logger("ReportH24")

BGY_LAT = 45.6739
BGY_LON = 9.7042

MATCH_WINDOW_BEFORE_MIN = 15
MATCH_WINDOW_BEFORE_MIN_AVIONIO = 60
MATCH_WINDOW_AFTER_MIN = 60
MATCH_WINDOW_WIDE_BEFORE_MIN = 60
RADAR_DEDUP_WINDOW_MIN = 15

ICAO24_DEDUP_NEAR_MIN = 15
ICAO24_DEDUP_SAMEDIR_MIN = 120

SCHED_DEDUP_TOLERANCE_MIN = 15
ICAO24_UNKNOWN_DEDUP_MIN = 5

SAME_DETECTION_MAX_SEC = 120

VALID_RUNWAYS = ('RWY 28', 'RWY 10')
BGY_PHASES = ('Atterraggio', 'Decollo', 'Avvicinamento', 'Incerto')

_callsign_patterns_cache = None
_inverted_patterns_cache = None
_DST_CACHE = {}


def _cfg():
    return config_manager.get_report_night_config()


def _load_callsign_patterns():
    global _callsign_patterns_cache
    if _callsign_patterns_cache is not None: return _callsign_patterns_cache
    try:
        ok, rows = bgy_db.execute_query("SELECT pattern, airline_iata FROM callsign_airline_patterns")
        if not ok: _callsign_patterns_cache = {}; return {}
        _callsign_patterns_cache = {str(r[0]).strip().upper(): str(r[1]).strip().upper() for r in (rows or [])}
        return _callsign_patterns_cache
    except Exception:
        _callsign_patterns_cache = {}; return {}


def _get_inverted_patterns():
    global _inverted_patterns_cache
    if _inverted_patterns_cache is not None: return _inverted_patterns_cache
    patterns = _load_callsign_patterns()
    inv = {}
    for pattern, iata in patterns.items():
        inv.setdefault(iata, []).append(pattern)
    _inverted_patterns_cache = inv
    return inv


def _safe_float(value, default=None):
    if value is None: return default
    try:
        if pd.isna(value): return default
        return float(value)
    except (ValueError, TypeError): return default


def _safe_int(value, default=0):
    if value is None: return default
    try:
        if pd.isna(value): return default
        return int(float(value))
    except (ValueError, TypeError): return default


def _distance_from_phase(fase):
    cfg = _cfg()
    distances = cfg.get("distance_by_phase_km", {})
    return distances.get(fase)


def _find_scan_file_for_date(date_norm):
    new_name = radar_filename(date_norm)
    old_name = f"bgy_night_flights_{date_norm}.csv"
    for name in (new_name, old_name):
        if not name: continue
        p = os.path.join(RAW_DIR, name)
        if os.path.exists(p): return p
    return None


def _time_to_minutes(hhmm):
    if not hhmm: return None
    try:
        s = str(hhmm).strip(); parts = s.split(":")
        if len(parts) < 2: return None
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, AttributeError): return None


def _scheduled_minutes_from_calendar(hhmm):
    return _time_to_minutes(hhmm)


def _day_crosses_dst(date_str):
    if date_str in _DST_CACHE:
        return _DST_CACHE[date_str]
    try:
        from zoneinfo import ZoneInfo
        _tz = ZoneInfo("Europe/Rome")
        _d1 = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=0, minute=0, tzinfo=_tz)
        _d2 = _d1 + timedelta(hours=24)
        result = _d1.utcoffset() != _d2.utcoffset()
    except Exception:
        result = False
    _DST_CACHE[date_str] = result
    return result


def _utc_base_h24(date_str):
    return pd.Timestamp(f"{date_str} 00:00:00", tz="Europe/Rome").tz_convert("UTC")


def _scheduled_minutes_h24_utc(hhmm, date_str):
    """BUG-18/DST: calcola i minuti dello scheduled in UTC se il giorno attraversa DST."""
    if not hhmm: return None
    try:
        parts = str(hhmm).strip().split(':')
        h, m = int(parts[0]), int(parts[1])
        # Costruisci il timestamp locale (Europe/Rome gestisce automaticamente CEST/CET)
        ts = pd.Timestamp(f"{date_str} {h:02d}:{m:02d}:00", tz="Europe/Rome")
        ts_utc = ts.tz_convert("UTC")
        base_utc = _utc_base_h24(date_str)
        return int((ts_utc - base_utc).total_seconds() / 60)
    except Exception:
        return _scheduled_minutes_from_calendar(hhmm)


def _timestamp_to_minutes_h24(ts, date_str, ts_utc=None):
    if _day_crosses_dst(date_str) and ts_utc:
        try:
            dt_utc = pd.to_datetime(ts_utc, utc=True, errors="coerce")
            if pd.notna(dt_utc):
                base_utc = _utc_base_h24(date_str)
                return int((dt_utc - base_utc).total_seconds() / 60)
        except Exception:
            pass
    if not ts: return None
    try: dt = pd.to_datetime(ts)
    except Exception: return None
    base = pd.to_datetime(f"{date_str} 00:00:00")
    return int((dt - base).total_seconds() / 60)


def _is_timestamp_in_h24(ts, date_str, ts_utc=None):
    if _day_crosses_dst(date_str) and ts_utc:
        try:
            dt_utc = pd.to_datetime(ts_utc, utc=True, errors="coerce")
            if pd.notna(dt_utc):
                base_utc = _utc_base_h24(date_str)
                end_utc = base_utc + pd.Timedelta(hours=25)
                return base_utc <= dt_utc < end_utc
        except Exception:
            pass
    if not ts: return False
    try: dt = pd.to_datetime(ts)
    except Exception: return False
    return dt.strftime("%Y-%m-%d") == date_str


def _extract_scan_time(filename):
    try:
        base = filename.replace(".csv", ""); parts = base.split("_")
        if len(parts) >= 3:
            scan_time = parts[2]
            if "-" in scan_time: return scan_time
            if len(scan_time) == 4: return f"{scan_time[:2]}-{scan_time[2:]}"
    except Exception: pass
    return None


def _scan_time_to_order_h24(scan_time):
    try:
        hh, mm = map(int, scan_time.split('-')); return hh * 60 + mm
    except Exception: return 9999


def _extract_callsign_digits(callsign):
    if not callsign: return ''
    return re.sub(r'\D', '', str(callsign))


def _normalize_callsign(callsign):
    if not callsign: return ''
    s = re.sub(r'[\s\u00A0\u200B\u200C\u200D\uFEFF]+', '', str(callsign))
    return s.strip().upper()


def _normalize_hhmm(hhmm):
    if not hhmm: return ''
    s = re.sub(r'[\s\u00A0\u200B\u200C\u200D\uFEFF]+', '', str(hhmm))
    return s.strip()


def _split_iata_callsign(callsign_norm):
    if not callsign_norm: return None, None
    for pref_len in (2, 3):
        if len(callsign_norm) <= pref_len: continue
        prefix = callsign_norm[:pref_len]; number = callsign_norm[pref_len:]
        if not any(c.isalpha() for c in prefix): continue
        if not number.isdigit(): continue
        return prefix, number
    return None, None


def _icao_prefix_from_sacbo(callsign_sacbo):
    if not callsign_sacbo: return None
    cs_norm = _normalize_callsign(callsign_sacbo)
    if not cs_norm: return None
    prefix_iata, number = _split_iata_callsign(cs_norm)
    if not prefix_iata: return None
    prefix_icao = iata_to_icao_prefix(prefix_iata)
    return prefix_icao.upper() if prefix_icao else None


def _icao_prefix_from_radar(callsign_radar):
    if not callsign_radar: return None
    cs = _normalize_callsign(callsign_radar)
    return cs[:3] if len(cs) >= 3 else None


def _extract_icao_number(callsign):
    cs = _normalize_callsign(callsign)
    if len(cs) < 4: return None, None
    m = re.search(r'(\d+)$', cs)
    return (cs[:3], m.group(1)) if m else (None, None)


def _extract_iata_number(callsign_sacbo):
    cs = _normalize_callsign(callsign_sacbo)
    if not cs: return None, None
    return _split_iata_callsign(cs)


def _tipo_movimento_from_callsign(callsign, source):
    categoria, nome = classify_callsign(callsign)
    if categoria == 'Cargo': return f'Cargo ({nome})' if nome else 'Cargo (N/D)'
    if categoria == 'Charter': return f'Charter ({nome})' if nome else 'Charter (N/D)'
    if categoria == 'Passeggeri': return 'Passeggeri'
    return 'Non classificato'


def normalize_scan_columns(df):
    col_map = {
        'flight_num': 'callsign_volo', 'numero_volo': 'callsign_volo',
        'type': 'tipo_movimento', 'sched_time': 'orario_schedulato',
        'actual_time': 'orario_effettivo', 'origin_dest': 'destinazione_origine',
        'stato_volo': 'stato_volo', 'status': 'stato_volo', 'stato': 'stato_volo'
    }
    df = df.rename(columns=col_map)
    for col in ['callsign_volo', 'tipo_movimento', 'orario_schedulato', 'destinazione_origine']:
        if col not in df.columns: df[col] = ''
    return df


def _is_phase_compatible(direzione_sacbo, fase_volo):
    if fase_volo == 'Incerto': return True
    if direzione_sacbo == 'D': return fase_volo == 'Decollo'
    if direzione_sacbo == 'A': return fase_volo in ('Atterraggio', 'Avvicinamento')
    return False


def _phase_priority(fase_volo):
    priorities = {'Atterraggio': 5, 'Decollo': 4, 'Avvicinamento': 3, 'Incerto': 2, 'Non rilevato': 1, 'N/D': 0, '': 0}
    return priorities.get(str(fase_volo).strip(), 1)


def _is_unknown_callsign(cs):
    if cs is None: return True
    try:
        if pd.isna(cs): return True
    except (TypeError, ValueError): pass
    return str(cs).strip().upper() in ('', 'UNKNOWN', 'NAN', 'NONE', 'N/D', 'NA', 'N.A.')


def _filter_excluded_callsigns(df):
    if df.empty or 'callsign' not in df.columns: return df, 0
    def _is_excluded(cs):
        if cs is None: return False
        try:
            if pd.isna(cs): return False
        except (TypeError, ValueError): pass
        s = str(cs).strip()
        if not s: return False
        try: categoria, _ = classify_callsign(s)
        except Exception: return False
        return 'escluso' in str(categoria).lower()
    mask = df['callsign'].apply(_is_excluded)
    n_excluded = int(mask.sum())
    return (df[~mask].reset_index(drop=True), n_excluded) if n_excluded > 0 else (df, 0)


def _dedup_scheduled_same_icao24(df):
    if df.empty or 'icao24' not in df.columns:
        return df, 0

    df = df.copy()
    df['_icao_norm'] = df['icao24'].apply(lambda x: str(x).strip().lower() if pd.notna(x) and str(x).strip() != '' else '')
    sched_mask = (df['is_scheduled'] == True) & (df['_icao_norm'] != '')

    if not sched_mask.any():
        return df.drop(columns=['_icao_norm']), 0

    to_drop = []

    for (icao, dir_), group in df[sched_mask].groupby(['_icao_norm', 'direzione_sacbo']):
        if len(group) <= 1:
            continue

        group = group.copy()
        group['_fonte_priority'] = group['fonte_scheduled'].fillna('').astype(str).str.lower().apply(lambda x: 1 if x == 'sacbo' else 0)
        group = group.sort_values(by=['_fonte_priority', 'timestamp'], ascending=[False, True])

        kept_idx = []
        for idx, row in group.iterrows():
            if not kept_idx:
                kept_idx.append(idx)
                continue

            is_dup = False
            cs_r = _normalize_callsign(row.get('callsign', ''))
            ts_r = pd.to_datetime(row.get('timestamp'), errors='coerce')

            for k_idx in kept_idx:
                k_row = group.loc[k_idx]
                cs_k = _normalize_callsign(k_row.get('callsign', ''))
                ts_k = pd.to_datetime(k_row.get('timestamp'), errors='coerce')

                if cs_r and cs_k and cs_r != cs_k and not _is_unknown_callsign(cs_r) and not _is_unknown_callsign(cs_k):
                    if pd.notna(ts_r) and pd.notna(ts_k):
                        if abs((ts_r - ts_k).total_seconds()) > SAME_DETECTION_MAX_SEC:
                            continue
                    else:
                        continue

                if pd.notna(ts_r) and pd.notna(ts_k):
                    delta_min = abs((ts_r - ts_k).total_seconds()) / 60
                    if delta_min <= ICAO24_DEDUP_NEAR_MIN:
                        is_dup = True
                        break
                else:
                    s_r = str(row.get('orario_schedulato', '')).strip()
                    s_k = str(k_row.get('orario_schedulato', '')).strip()
                    if s_r and s_r == s_k:
                        is_dup = True
                        break

            if is_dup:
                to_drop.append(idx)
            else:
                kept_idx.append(idx)

    df = df.drop(columns=['_icao_norm'])
    if not to_drop:
        return df, 0

    df = df.drop(index=to_drop)
    return df.reset_index(drop=True), len(to_drop)


def _dedup_radar_by_icao24_window(radar_df, window_sec=SAME_DETECTION_MAX_SEC):
    if radar_df.empty or 'icao24' not in radar_df.columns or 'timestamp' not in radar_df.columns:
        return radar_df
    df = radar_df.copy()
    df['_icao_norm'] = df['icao24'].apply(
        lambda x: str(x).strip().lower() if pd.notna(x) and str(x).strip() not in ('', 'nan', 'none', 'n/d') else ''
    )
    df['_ts_dt'] = pd.to_datetime(df['timestamp'], errors='coerce')
    valid_mask = (df['_icao_norm'] != '') & df['_ts_dt'].notna()
    if not valid_mask.any():
        return radar_df.drop(columns=['_icao_norm', '_ts_dt'], errors='ignore').reset_index(drop=True)

    df_valid = df[valid_mask].copy()
    df_valid['_pista_valid'] = df_valid['pista'].apply(
        lambda x: 1 if str(x).strip() in VALID_RUNWAYS else 0
    )
    df_valid = df_valid.sort_values(['_icao_norm', '_pista_valid', '_ts_dt'], ascending=[True, False, True])

    keep_idx = []
    for icao, group in df_valid.groupby('_icao_norm'):
        last_kept_ts = None
        for idx, row in group.iterrows():
            ts = row['_ts_dt']
            if last_kept_ts is None or (ts - last_kept_ts).total_seconds() > window_sec:
                keep_idx.append(idx)
                last_kept_ts = ts

    keep_set = set(keep_idx) | set(df[~valid_mask].index)
    df_out = df.loc[sorted(keep_set)].drop(columns=['_icao_norm', '_ts_dt'], errors='ignore')
    return df_out.reset_index(drop=True)


def _dedup_unknown_via_icao24(radar_df, date_str=None):
    if radar_df.empty or 'icao24' not in radar_df.columns or 'callsign' not in radar_df.columns: return radar_df
    df = radar_df.copy()
    def _norm_icao(v):
        if v is None or (isinstance(v, float) and pd.isna(v)): return ''
        s = str(v).strip().lower()
        return '' if s in ('', 'nan', 'none', 'n/d') else s
    df['_icao_norm'] = df['icao24'].apply(_norm_icao)
    df['_cs_unknown'] = df['callsign'].apply(_is_unknown_callsign)
    def _norm_ts(v):
        if v is None or (isinstance(v, float) and pd.isna(v)): return None
        s = str(v).strip(); return None if s == '' else (pd.to_datetime(s) if s else None)
    use_utc = bool(date_str and _day_crosses_dst(date_str) and 'timestamp_utc' in df.columns)
    if use_utc:
        def _norm_ts_utc(v, fallback_naive):
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                s = str(v).strip()
                if s:
                    try: return pd.to_datetime(s, utc=True)
                    except Exception: pass
            dt = _norm_ts(fallback_naive)
            return dt.tz_localize('UTC') if dt is not None else None
        df['_ts_norm'] = df.apply(lambda r: _norm_ts_utc(r.get('timestamp_utc'), r.get('timestamp')), axis=1)
    else:
        df['_ts_norm'] = df['timestamp'].apply(_norm_ts)
    def _phase_to_dir(fase):
        f = str(fase).strip()
        return 'D' if f == 'Decollo' else ('A' if f in ('Atterraggio', 'Avvicinamento') else '')
    df['_dir'] = df['fase_volo'].apply(_phase_to_dir)
    drop_idx = set()
    for icao, group in df.groupby('_icao_norm'):
        if not icao or len(group) < 2: continue
        unknown_rows = group[group['_cs_unknown']]; known_rows = group[~group['_cs_unknown']]
        if unknown_rows.empty or known_rows.empty: continue
        for u_idx, u_row in unknown_rows.iterrows():
            if u_idx in drop_idx: continue
            u_ts = u_row['_ts_norm']; u_dir = u_row['_dir']
            if u_ts is None: continue
            for k_idx, k_row in known_rows.iterrows():
                if k_idx in drop_idx: continue
                k_ts = k_row['_ts_norm']; k_dir = k_row['_dir']
                if k_ts is None or (u_dir and k_dir and u_dir != k_dir): continue
                if abs((u_ts - k_ts).total_seconds()) / 60 <= ICAO24_UNKNOWN_DEDUP_MIN:
                    drop_idx.add(u_idx); break
    df = df.drop(columns=['_icao_norm', '_cs_unknown', '_ts_norm', '_dir'])
    return radar_df if not drop_idx else df.drop(index=list(drop_idx)).reset_index(drop=True)


def _dedup_scheduled_soft_cross_source(df):
    if df.empty or 'fonte_scheduled' not in df.columns or 'direzione_sacbo' not in df.columns or 'callsign' not in df.columns: return df
    df = df.copy()
    df['_cs_norm'] = df['callsign'].apply(_normalize_callsign)
    df['_sched_min'] = df['orario_schedulato'].apply(_time_to_minutes)
    df['_dir_norm'] = df['direzione_sacbo'].fillna('').astype(str).str.strip().str.upper()
    df['_fonte_norm'] = df['fonte_scheduled'].fillna('').astype(str).str.strip().str.lower()
    drop_idx = set()
    for (cs, dir_), group in df.groupby(['_cs_norm', '_dir_norm']):
        if not cs or dir_ not in ('D', 'A') or len(group) < 2: continue
        sacbo_rows = group[group['_fonte_norm'] == 'sacbo']; avionio_rows = group[group['_fonte_norm'] == 'avionio']
        if sacbo_rows.empty or avionio_rows.empty: continue
        for av_idx, av_row in avionio_rows.iterrows():
            if av_idx in drop_idx: continue
            av_min = av_row['_sched_min']
            if av_min is None: continue
            for s_idx, s_row in sacbo_rows.iterrows():
                s_min = s_row['_sched_min']
                if s_min is None: continue
                delta = abs(av_min - s_min)
                if delta > 12 * 60: delta = 24 * 60 - delta
                if delta <= SCHED_DEDUP_TOLERANCE_MIN: drop_idx.add(av_idx); break
    df = df.drop(columns=['_cs_norm', '_sched_min', '_dir_norm', '_fonte_norm'])
    return df if not drop_idx else df.drop(index=list(drop_idx)).reset_index(drop=True)


def _dedup_by_key(df):
    if df.empty: return df
    mask = df['orario_schedulato'].apply(lambda x: bool(str(x).strip()) if pd.notna(x) else False)
    with_sched = df[mask].copy(); without_sched = df[~mask].copy()
    if with_sched.empty: return df
    with_sched = _dedup_scheduled_soft_cross_source(with_sched)
    with_sched['_key_cs'] = with_sched['callsign'].apply(_normalize_callsign)
    with_sched['_key_sched'] = with_sched['orario_schedulato'].apply(_normalize_hhmm)
    with_sched['_is_sched_priority'] = with_sched['is_scheduled'].apply(lambda x: 1 if x is True or str(x).lower() == 'true' else 0)
    with_sched['_phase_priority'] = with_sched['fase_volo'].apply(_phase_priority)
    with_sched['_ts_priority'] = with_sched['timestamp'].apply(lambda t: str(t) if pd.notna(t) and str(t).strip() else '')
    with_sched = with_sched.sort_values(by=['_is_sched_priority', '_phase_priority', '_ts_priority'], ascending=[False, False, False])
    with_sched = with_sched.drop_duplicates(subset=['_key_cs', '_key_sched'], keep='first')
    with_sched = with_sched.drop(columns=['_key_cs', '_key_sched', '_is_sched_priority', '_phase_priority', '_ts_priority'])
    return pd.concat([with_sched, without_sched], ignore_index=True)


def _try_pattern_match_for_sched(sched_callsign, direzione_sacbo, sched_min, low, high, radar, used_radar_idx, inv_patterns):
    if not sched_callsign: return None, None
    iata_sched, num_sched = _extract_iata_number(sched_callsign)
    if not iata_sched or not num_sched: return None, None
    patterns_for_iata = inv_patterns.get(iata_sched.upper(), [])
    if not patterns_for_iata: return None, None
    best_idx = None; best_delta = None
    for idx, r in radar.iterrows():
        if idx in used_radar_idx: continue
        r_min = r['_radar_min']
        if r_min is None or r_min < low or r_min > high: continue
        fase = str(r.get('fase_volo', '') or '')
        if not _is_phase_compatible(direzione_sacbo, fase): continue
        prefix_radar, num_radar = _extract_icao_number(r.get('callsign', ''))
        if not prefix_radar or not num_radar: continue
        if prefix_radar.upper() not in [p.upper() for p in patterns_for_iata]: continue
        if num_radar != num_sched: continue
        delta = abs(r_min - sched_min)
        if best_delta is None or delta < best_delta: best_delta = delta; best_idx = idx
    return best_idx, best_delta


def _try_alternative_same_icao(radar, best_idx, direzione_sacbo, sched_min, low, high, used_radar_idx):
    if best_idx is None or 'icao24' not in radar.columns: return None, None
    r_best = radar.loc[best_idx]
    if str(r_best.get('pista', '') or '').strip() in VALID_RUNWAYS: return None, None
    icao_best = str(r_best.get('icao24', '') or '').strip().lower()
    if not icao_best or icao_best in ('', 'nan', 'none', 'n/d'): return None, None
    best_alt_idx = None; best_alt_delta = None
    for idx, r in radar.iterrows():
        if idx == best_idx or idx in used_radar_idx: continue
        if str(r.get('icao24', '') or '').strip().lower() != icao_best: continue
        fase = str(r.get('fase_volo', '') or '')
        if not _is_phase_compatible(direzione_sacbo, fase): continue
        if str(r.get('pista', '') or '').strip() not in VALID_RUNWAYS: continue
        r_min = r.get('_radar_min')
        if r_min is None or r_min < low or r_min > high: continue
        delta = abs(r_min - sched_min)
        if best_alt_delta is None or delta < best_alt_delta: best_alt_delta = delta; best_alt_idx = idx
    return best_alt_idx, best_alt_delta


def match_flights_h24(scheduled_df, radar_df, date_str):
    if scheduled_df.empty and radar_df.empty:
        return pd.DataFrame()

    if scheduled_df.empty:
        radar_df = radar_df.copy()
        radar_df['is_scheduled'] = False
        radar_df['orario_schedulato'] = ''
        radar_df['destinazione_origine'] = ''
        radar_df['direzione_sacbo'] = ''
        radar_df['notte_categoria'] = ''
        radar_df['matched_score'] = 0
        radar_df['fonte_scheduled'] = ''
        if 'pista_fonte' not in radar_df.columns:
            radar_df['pista_fonte'] = 'N/D'
        radar_df = radar_df[radar_df.apply(
            lambda r: _is_timestamp_in_h24(
                r['timestamp'], date_str,
                ts_utc=(r['timestamp_utc'] if 'timestamp_utc' in r.index else None)
            ), axis=1
        )].copy()
        radar_df = _dedup_radar_by_callsign(radar_df, date_str)
        classified = _classify_unmatched_radar(radar_df)
        return _enrich_final(classified, date_str) if not classified.empty else pd.DataFrame()

    if radar_df.empty:
        scheduled_df = scheduled_df.copy()
        scheduled_df['is_scheduled'] = True
        scheduled_df['timestamp'] = ''
        scheduled_df['pista'] = 'N/D'
        scheduled_df['pista_fonte'] = 'N/D'
        scheduled_df['fase_volo'] = 'Non rilevato'
        scheduled_df['direzione'] = 'N/D'
        scheduled_df['quota_ft'] = 0
        scheduled_df['rotta_deg'] = 0
        scheduled_df['distanza_km'] = 0
        scheduled_df['paese'] = 'N/D'
        scheduled_df['matched_score'] = 0
        scheduled_df['icao24'] = ''
        scheduled_df['callsign'] = scheduled_df['callsign_volo']
        if 'fonte_scheduled' not in scheduled_df.columns: scheduled_df['fonte_scheduled'] = 'sacbo'
        scheduled_df['tipo_movimento'] = scheduled_df.apply(lambda r: _tipo_movimento_from_callsign(r['callsign_volo'], source=r.get('fonte_scheduled', 'sacbo')), axis=1)
        return _enrich_final(scheduled_df, date_str)

    sched = scheduled_df.copy()
    radar = radar_df.copy()

    # BUG-18/DST: calcolo UTC per scheduled se il giorno attraversa DST
    if _day_crosses_dst(date_str):
        sched['_sched_min'] = sched.apply(lambda r: _scheduled_minutes_h24_utc(r.get('orario_schedulato'), date_str), axis=1)
    else:
        sched['_sched_min'] = sched.apply(lambda r: _scheduled_minutes_from_calendar(r.get('orario_schedulato')), axis=1)

    radar['_radar_min'] = radar.apply(
        lambda r: _timestamp_to_minutes_h24(
            r['timestamp'], date_str,
            ts_utc=(r['timestamp_utc'] if 'timestamp_utc' in r.index else None)
        ), axis=1
    )
    radar = radar[radar['_radar_min'].notna()].copy()

    radar = _dedup_radar_by_icao24_window(radar, window_sec=SAME_DETECTION_MAX_SEC)

    inv_patterns = _get_inverted_patterns()
    matched = []
    used_radar_idx = set()

    for _, s in sched.iterrows():
        sched_min = s['_sched_min']
        direzione = s.get('direzione_sacbo', '')
        categoria = s.get('notte_categoria', '')
        callsign_sched = s.get('callsign_volo', '')
        fonte_sched = s.get('fonte_scheduled', 'sacbo')
        cs_sacbo_norm = _normalize_callsign(callsign_sched)
        tipo_mov = _tipo_movimento_from_callsign(callsign_sched, source=fonte_sched)

        prefix_sacbo = _icao_prefix_from_sacbo(callsign_sched)
        _, num_sched = _extract_iata_number(callsign_sched)

        if sched_min is None:
            combined = dict(s)
            combined['is_scheduled'] = True
            combined['timestamp'] = ''
            combined['pista'] = 'N/D'
            combined['pista_fonte'] = 'N/D'
            combined['fase_volo'] = 'Non rilevato'
            combined['direzione'] = 'N/D'
            combined['quota_ft'] = 0
            combined['rotta_deg'] = 0
            combined['distanza_km'] = 0
            combined['paese'] = 'N/D'
            combined['matched_score'] = 0
            combined['icao24'] = ''
            combined['callsign'] = cs_sacbo_norm
            combined['tipo_movimento'] = tipo_mov
            combined['notte_categoria'] = categoria
            combined['fonte_scheduled'] = fonte_sched
            matched.append(combined)
            continue

        low = sched_min - (MATCH_WINDOW_BEFORE_MIN_AVIONIO if fonte_sched == 'avionio' else MATCH_WINDOW_BEFORE_MIN)
        high = sched_min + MATCH_WINDOW_AFTER_MIN

        best_idx = None; best_delta = None; best_num_idx = None; best_num_delta = None

        for idx, r in radar.iterrows():
            if idx in used_radar_idx: continue
            r_min = r['_radar_min']
            if r_min is None or r_min < low or r_min > high: continue
            fase = str(r.get('fase_volo', '') or '')
            if not _is_phase_compatible(direzione, fase): continue

            prefix_radar = _icao_prefix_from_radar(r.get('callsign', ''))
            if prefix_sacbo is None or prefix_radar is None or prefix_sacbo != prefix_radar: continue

            delta = abs(r_min - sched_min)
            _, num_radar = _extract_icao_number(r.get('callsign', ''))

            if num_sched is not None and num_radar is not None and num_sched == num_radar:
                if best_num_delta is None or delta < best_num_delta: best_num_delta = delta; best_num_idx = idx
            else:
                if best_delta is None or delta < best_delta: best_delta = delta; best_idx = idx

        if best_num_idx is not None: best_idx = best_num_idx; best_delta = best_num_delta

        if best_idx is None:
            pat_idx, pat_delta = _try_pattern_match_for_sched(callsign_sched, direzione, sched_min, low, high, radar, used_radar_idx, inv_patterns)
            if pat_idx is not None: best_idx = pat_idx; best_delta = pat_delta

        if best_idx is not None:
            alt_idx, alt_delta = _try_alternative_same_icao(radar, best_idx, direzione, sched_min, low, high, used_radar_idx)
            if alt_idx is not None: best_idx = alt_idx; best_delta = alt_delta

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
            combined['fonte_scheduled'] = fonte_sched
            matched.append(combined)
        else:
            combined = dict(s)
            combined['is_scheduled'] = True
            combined['timestamp'] = ''
            combined['pista'] = 'N/D'
            combined['pista_fonte'] = 'N/D'
            combined['fase_volo'] = 'Non rilevato'
            combined['direzione'] = 'N/D'
            combined['quota_ft'] = 0
            combined['rotta_deg'] = 0
            combined['distanza_km'] = 0
            combined['paese'] = 'N/D'
            combined['matched_score'] = 0
            combined['icao24'] = ''
            combined['callsign'] = cs_sacbo_norm
            combined['tipo_movimento'] = tipo_mov
            combined['notte_categoria'] = categoria
            combined['fonte_scheduled'] = fonte_sched
            matched.append(combined)

    unmatched = radar[~radar.index.isin(used_radar_idx)].copy()
    unmatched = unmatched[unmatched.apply(
        lambda r: _is_timestamp_in_h24(
            r['timestamp'], date_str,
            ts_utc=(r['timestamp_utc'] if 'timestamp_utc' in r.index else None)
        ), axis=1
    )].copy()
    unmatched = _dedup_radar_by_callsign(unmatched, date_str)
    classified = _classify_unmatched_radar(unmatched)

    for _, row in classified.iterrows(): matched.append(row.to_dict())

    result = pd.DataFrame(matched)
    for col in ('_sched_min', '_radar_min'):
        if col in result.columns: result = result.drop(columns=[col])

    return _enrich_final(result, date_str)


def _classify_unmatched_radar(radar_df):
    if radar_df.empty: return radar_df
    classified = []
    for _, row in radar_df.iterrows():
        cs = str(row.get('callsign', '') or '').strip()
        fase = str(row.get('fase_volo', '') or '').strip()
        if fase not in BGY_PHASES: continue
        row_dict = row.to_dict()
        row_dict['is_scheduled'] = False
        row_dict['orario_schedulato'] = ''
        row_dict['destinazione_origine'] = ''
        row_dict['matched_score'] = 0
        row_dict['fonte_scheduled'] = ''
        if not row_dict.get('notte_categoria'): row_dict['notte_categoria'] = ''
        if not row_dict.get('pista_fonte'): row_dict['pista_fonte'] = 'N/D'
        if not row_dict.get('direzione_sacbo'):
            row_dict['direzione_sacbo'] = 'D' if fase == 'Decollo' else ('A' if fase in ('Atterraggio', 'Avvicinamento') else '?')
        categoria, nome = classify_callsign(cs)
        if categoria == 'Cargo': row_dict['tipo_movimento'] = f'Cargo ({nome})' if nome else 'Cargo (N/D)'
        elif categoria == 'Charter': row_dict['tipo_movimento'] = f'Charter ({nome})' if nome else 'Charter (N/D)'
        elif categoria == 'Passeggeri': row_dict['tipo_movimento'] = 'Passeggeri (radar)'
        else: row_dict['tipo_movimento'] = 'Non classificato'
        classified.append(row_dict)
    return pd.DataFrame(classified) if classified else pd.DataFrame()


def _dedup_radar_by_callsign(radar_df, date_str=None):
    if radar_df.empty or 'callsign' not in radar_df.columns: return radar_df
    df = radar_df.copy()
    try:
        if date_str and _day_crosses_dst(date_str) and 'timestamp_utc' in df.columns:
            ts_utc = pd.to_datetime(df['timestamp_utc'], errors='coerce', utc=True)
            ts_min_naive = (pd.to_datetime(df['timestamp']).astype('int64') // 60_000_000_000)
            ts_min_utc = ts_utc.astype('int64') // 60_000_000_000
            ts_min = ts_min_utc.where(ts_utc.notna(), ts_min_naive)
        else:
            ts_min = (pd.to_datetime(df['timestamp']).astype('int64') // 60_000_000_000)
        df['_window'] = ts_min // RADAR_DEDUP_WINDOW_MIN
    except: return radar_df
    PHASE_RANK = {'Atterraggio': 5, 'Decollo': 4, 'Avvicinamento': 3, 'Incerto': 2, 'Sorvolo': 1, 'Transito': 0, 'N/D': 0, 'Non rilevato': 0, '': 0}
    df['_phase_rank'] = df['fase_volo'].apply(lambda f: PHASE_RANK.get(str(f).strip(), 0))
    df = df.sort_values(by=['_phase_rank', 'timestamp'], ascending=[False, False]).drop_duplicates(subset=['callsign', '_window'], keep='first')
    df = df.drop(columns=['_window', '_phase_rank'])
    return _dedup_unknown_via_icao24(df, date_str)


def _dedup_radar_only_via_icao24(result_df, date_str=None):
    if result_df.empty or 'icao24' not in result_df.columns: return result_df, 0
    df = result_df.copy()
    def _norm_icao(v):
        if v is None or (isinstance(v, float) and pd.isna(v)): return ''
        s = str(v).strip().lower()
        return '' if s in ('', 'nan', 'none', 'n/d') else s
    df['_icao_norm'] = df['icao24'].apply(_norm_icao)
    def _norm_ts(v):
        if v is None or (isinstance(v, float) and pd.isna(v)): return None
        s = str(v).strip(); return None if s == '' else (pd.to_datetime(s) if s else None)
    use_utc = bool(date_str and _day_crosses_dst(date_str) and 'timestamp_utc' in df.columns)
    if use_utc:
        def _norm_ts_utc(v, fallback_naive):
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                s = str(v).strip()
                if s:
                    try: return pd.to_datetime(s, utc=True)
                    except Exception: pass
            dt = _norm_ts(fallback_naive)
            return dt.tz_localize('UTC') if dt is not None else None
        df['_ts_norm'] = df.apply(lambda r: _norm_ts_utc(r.get('timestamp_utc'), r.get('timestamp')), axis=1)
    else:
        df['_ts_norm'] = df['timestamp'].apply(_norm_ts)
    sched_mask = ((df['is_scheduled'] == True) & (df['_icao_norm'] != '') & (df['_ts_norm'].notna()))
    sched_records = df[sched_mask][['_icao_norm', '_ts_norm', 'direzione_sacbo', 'callsign']].to_dict('records')
    sched_by_icao = defaultdict(list)
    for s in sched_records: sched_by_icao[s['_icao_norm']].append(s)
    dedupable_tipos_exact = ('Passeggeri (radar)', 'Non classificato')
    dedupable_prefixes = ('Cargo (', 'Charter (')
    tipo_series = df['tipo_movimento'].fillna('').astype(str)
    is_dedupable_tipo = (tipo_series.isin(dedupable_tipos_exact) | tipo_series.str.startswith(dedupable_prefixes, na=False))
    ro_mask = ((df['is_scheduled'] == False) & is_dedupable_tipo & (df['_icao_norm'] != '') & (df['_ts_norm'].notna()))
    to_drop = []
    for idx, r in df[ro_mask].iterrows():
        icao = r['_icao_norm']; ts_ro = r['_ts_norm']; dir_ro = str(r.get('direzione_sacbo', '') or '').strip().upper()
        for s in sched_by_icao.get(icao, []):
            delta_min = abs((ts_ro - s['_ts_norm']).total_seconds()) / 60
            if delta_min <= ICAO24_DEDUP_NEAR_MIN or (dir_ro == str(s.get('direzione_sacbo', '') or '').strip().upper() and delta_min <= ICAO24_DEDUP_SAMEDIR_MIN):
                to_drop.append(idx); break
    if not to_drop: return result_df, 0
    df = df.drop(index=to_drop)
    df = df.drop(columns=['_icao_norm', '_ts_norm'], errors='ignore')
    return df.reset_index(drop=True), len(to_drop)


def _enrich_final(df, date_str):
    if df.empty: return df
    df = df.copy()

    if 'callsign' not in df.columns: df['callsign'] = df.get('callsign_volo', 'N/D')
    else: df['callsign'] = df['callsign'].fillna(df.get('callsign_volo', 'N/D'))

    if 'direzione_sacbo' not in df.columns: df['direzione_sacbo'] = ''
    if 'notte_categoria' not in df.columns: df['notte_categoria'] = ''
    else: df['notte_categoria'] = df['notte_categoria'].fillna('')
    if 'fonte_scheduled' not in df.columns: df['fonte_scheduled'] = ''
    else: df['fonte_scheduled'] = df['fonte_scheduled'].fillna('')
    if 'icao24' not in df.columns: df['icao24'] = ''
    if 'pista_fonte' not in df.columns: df['pista_fonte'] = 'N/D'
    else: df['pista_fonte'] = df['pista_fonte'].fillna('N/D')

    mask_ts_empty = (df['timestamp'].isna() | (df['timestamp'].astype(str).str.strip() == ''))
    if 'orario_effettivo' in df.columns:
        mask_has_eff = (df['orario_effettivo'].notna() & (df['orario_effettivo'].astype(str).str.strip() != ''))
        combine_mask = mask_ts_empty & mask_has_eff
        if combine_mask.any():
            df.loc[combine_mask, 'timestamp'] = df.loc[combine_mask].apply(
                lambda row: f"{date_str} {row['orario_effettivo']}", axis=1
            )

    df['compagnia_aerea'] = df['callsign'].apply(lambda x: get_airline(x) if pd.notna(x) else 'N/D')
    df['modello_aereo'] = df['callsign'].apply(lambda x: get_aircraft_model(x) if pd.notna(x) else 'N/D')

    if 'destinazione_origine' in df.columns:
        df['destinazione_finale'] = df.apply(lambda row: row['destinazione_origine'] if pd.notna(row.get('destinazione_origine')) and row['destinazione_origine'] else row.get('paese', 'N/D'), axis=1)
    else: df['destinazione_finale'] = df.get('paese', 'N/D')

    def resolve_country(row):
        dest = row.get('destinazione_origine', '')
        if pd.notna(dest) and dest and dest != '': return get_country(dest)
        paese = row.get('paese', '')
        if pd.notna(paese) and paese: return get_country(paese)
        return 'N/D'
    df['stato_destinazione'] = df.apply(resolve_country, axis=1)

    def _pax(row):
        tipo = str(row.get('tipo_movimento', '') or '').strip()
        if not (tipo == 'Passeggeri' or tipo == 'Passeggeri (radar)' or tipo.startswith('Charter')): return 0
        modello = row.get('modello_aereo', 'N/D')
        if not modello or modello == 'N/D': return 0
        try:
            cs = str(row.get('callsign', '') or '').strip().upper()
            code = cs[:3] if len(cs) >= 3 else (cs[:2] if len(cs) >= 2 else '')
            pax, seats, lf = estimate_passengers(modello, code)
            return pax
        except: return 0
    df['stima_passeggeri'] = df.apply(_pax, axis=1)

    try:
        from bgy_utils.bgy_utils_noise import get_max_noise
        from bgy_core import get_noise_stations
        if not get_noise_stations(): load_rules()
        def _noise(row):
            timestamp = row.get('timestamp', '')
            if not timestamp or pd.isna(timestamp) or str(timestamp).strip() == '': return 0
            fase = row.get('fase_volo', '')
            if not fase or fase in ('Non rilevato', 'N/D', 'Incerto') or pd.isna(fase): return 0
            modello = row.get('modello_aereo', 'N/D')
            if not modello or modello == 'N/D': modello = None
            quota = _safe_int(row.get('quota_ft'), 0)
            dist = _safe_float(row.get('distanza_km'), None)
            if dist is None or dist <= 0: dist = _distance_from_phase(fase)
            if dist is None: return 0
            rotta = _safe_float(row.get('rotta_deg'), 0)
            try:
                dlat = (dist / 111.0) * math.cos(math.radians(rotta))
                dlon = (dist / (111.0 * math.cos(math.radians(BGY_LAT)))) * math.sin(math.radians(rotta))
                lat = BGY_LAT + dlat; lon = BGY_LON + dlon
            except: return 0
            try: return get_max_noise(modello, fase, lat, lon, quota)
            except: return 0
        df['stima_rumore_db'] = df.apply(_noise, axis=1)
    except: df['stima_rumore_db'] = 0

    return df


def _sort_report_chronologically(df, date_str):
    if df.empty: return df
    df = df.copy()
    sort_keys = []
    for _, row in df.iterrows():
        ts_str = str(row.get('timestamp', '')).strip()
        sched_str = str(row.get('orario_schedulato', '')).strip()
        sort_val = None
        if ts_str and ts_str != 'nan' and ts_str != '':
            try:
                dt = pd.to_datetime(ts_str)
                sort_val = dt
            except Exception:
                pass
        if sort_val is None and sched_str and sched_str != 'nan' and sched_str != '':
            try:
                base = pd.to_datetime(f"{date_str} 00:00:00")
                parts = sched_str.split(':')
                sched_dt = base.replace(hour=int(parts[0]), minute=int(parts[1]), second=0)
                sort_val = sched_dt
            except Exception:
                pass
        if sort_val is None:
            sort_val = pd.to_datetime(f"{date_str} 23:59:59") + pd.Timedelta(minutes=1)
        sort_keys.append(sort_val)
    df['_sort_key'] = sort_keys
    df = df.sort_values(by='_sort_key', ascending=True)
    df = df.drop(columns=['_sort_key']).reset_index(drop=True)
    return df


def load_scheduled_flights_h24(date_str, radar_df=None):
    date_norm = normalize_date(date_str)
    scan_files = [f for f in os.listdir(RAW_DIR) if f.startswith(f"scan_{date_norm}_") and f.endswith(".csv")] if os.path.isdir(RAW_DIR) else []
    scan_files.sort()
    flights = defaultdict(list)
    for f in scan_files:
        filepath = os.path.join(RAW_DIR, f)
        scan_time = _extract_scan_time(f)
        if not scan_time: continue
        try:
            df = pd.read_csv(filepath); df = normalize_scan_columns(df)
            for _, row in df.iterrows():
                sched_raw = row.get('orario_schedulato')
                if not sched_raw: continue
                cs_norm = _normalize_callsign(row.get('callsign_volo', '')); sched_norm = _normalize_hhmm(sched_raw)
                if not cs_norm or not sched_norm: continue
                flights[(cs_norm, sched_norm)].append({
                    'scan_time': scan_time, 'callsign_volo': cs_norm, 'orario_schedulato': sched_norm,
                    'orario_effettivo': row.get('orario_effettivo'), 'stato_volo': row.get('stato_volo'),
                    'tipo_movimento': row.get('tipo_movimento'), 'destinazione_origine': row.get('destinazione_origine'),
                })
        except: pass
    for key in flights: flights[key].sort(key=lambda r: _scan_time_to_order_h24(r['scan_time']))
    scheduled = []
    for key, records in flights.items():
        row_dict = records[-1].copy(); row_dict.pop('scan_time', None)
        row_dict['direzione_sacbo'] = str(row_dict.get('tipo_movimento', '')).strip().upper()[:1]
        row_dict['notte_categoria'] = ''; row_dict.pop('tipo_movimento', None); row_dict['fonte_scheduled'] = 'sacbo'
        scheduled.append(row_dict)
    return pd.DataFrame(scheduled) if scheduled else pd.DataFrame()


def load_avionio_scheduled_h24(date_str):
    date_norm = normalize_date(date_str)
    ok, rows = bgy_db.execute_query("""
        SELECT callsign_volo, tipo_movimento, orario_schedulato, orario_effettivo,
               stato_volo, destinazione_origine, codice_iata, compagnia_aerea
        FROM flights_avionio
        WHERE (data_riferimento = %s AND orario_schedulato >= '06:00')
           OR (data_riferimento = %s::date - 1 AND orario_schedulato < '06:00')
           OR (data_riferimento = %s AND orario_schedulato IS NULL)
    """, (date_norm, date_norm, date_norm))
    if not ok: return pd.DataFrame()
    filtered = []
    for r in rows:
        cs_norm = _normalize_callsign(r[0]); sched_norm = _normalize_hhmm(r[2])
        if not cs_norm or not sched_norm: continue
        direzione = str(r[1] or '').strip().upper()[:1]
        if direzione not in ('A', 'D'): continue
        filtered.append({
            'callsign_volo': cs_norm, 'orario_schedulato': sched_norm, 'orario_effettivo': r[3] or '',
            'stato_volo': r[4] or '', 'destinazione_origine': r[5] or '', 'direzione_sacbo': direzione,
            'notte_categoria': '', 'fonte_scheduled': 'avionio', 'codice_iata': r[6] or '', 'compagnia_aerea': r[7] or '',
        })
    return pd.DataFrame(filtered)


def merge_scheduled_sources(sacbo_df, avionio_df):
    if sacbo_df is None: sacbo_df = pd.DataFrame()
    if avionio_df is None: avionio_df = pd.DataFrame()
    if sacbo_df.empty and avionio_df.empty: return pd.DataFrame()
    if sacbo_df.empty: return avionio_df.copy()
    if avionio_df.empty:
        sacbo = sacbo_df.copy(); sacbo['fonte_scheduled'] = 'sacbo'; return sacbo
    sacbo = sacbo_df.copy(); sacbo['fonte_scheduled'] = 'sacbo'
    sacbo_keys = set((_normalize_callsign(r.get('callsign_volo', '')), _normalize_hhmm(r.get('orario_schedulato', ''))) for _, r in sacbo.iterrows() if _normalize_callsign(r.get('callsign_volo', '')) and _normalize_hhmm(r.get('orario_schedulato', '')))
    avionio_extra_rows = [r.to_dict() for _, r in avionio_df.iterrows() if _normalize_callsign(r.get('callsign_volo', '')) and _normalize_hhmm(r.get('orario_schedulato', '')) and (_normalize_callsign(r.get('callsign_volo', '')), _normalize_hhmm(r.get('orario_schedulato', ''))) not in sacbo_keys]
    return pd.concat([sacbo, pd.DataFrame(avionio_extra_rows)], ignore_index=True) if avionio_extra_rows else sacbo


def load_radar_data_h24(date_str):
    date_norm = normalize_date(date_str)
    dt = datetime.strptime(date_norm, "%Y-%m-%d")
    prev_date = (dt - timedelta(days=1)).strftime("%Y-%m-%d"); next_date = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
    dfs = []
    filepath = _find_scan_file_for_date(prev_date)
    if filepath:
        df = pd.read_csv(filepath); df['ts'] = pd.to_datetime(df['timestamp'])
        dfs.append(df[df['ts'].dt.hour >= 20].drop(columns=['ts']))
    filepath = _find_scan_file_for_date(date_norm)
    if filepath: dfs.append(pd.read_csv(filepath))
    filepath = _find_scan_file_for_date(next_date)
    if filepath:
        df = pd.read_csv(filepath); df['ts'] = pd.to_datetime(df['timestamp'])
        dfs.append(df[df['ts'].dt.hour < 6].drop(columns=['ts']))
    if not dfs: return pd.DataFrame()
    combined = pd.concat(dfs, ignore_index=True)
    return fill_unknown_runways_geometric(propagate_runway_in_session(combined))


def generate_h24_report(date_str=None):
    load_rules()
    date_norm = normalize_date(date_str) if date_str else datetime.now().strftime("%Y-%m-%d")
    logger.info(f"🌞 Avvio report h24 per {date_norm}")
    radar_df = load_radar_data_h24(date_norm)
    sacbo_df = load_scheduled_flights_h24(date_norm, radar_df=radar_df)
    avionio_df = load_avionio_scheduled_h24(date_norm)
    scheduled_df = merge_scheduled_sources(sacbo_df, avionio_df)
    logger.info(f"📋 Scheduled totali: {len(scheduled_df)} (SACBO {len(sacbo_df)}, Avionio {len(avionio_df)})")

    result_df = match_flights_h24(scheduled_df, radar_df, date_norm)
    result_df, n_esclusi = _filter_excluded_callsigns(result_df)
    if result_df.empty: return None, f"Nessun dato per {date_norm}"

    result_df, n_dedup_sched = _dedup_scheduled_same_icao24(result_df)
    result_df, n_dedup_icao24 = _dedup_radar_only_via_icao24(result_df, date_norm)
    result_df = _dedup_by_key(result_df)

    result_df = _sort_report_chronologically(result_df, date_norm)

    os.makedirs(OUTPUT_CSV_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_CSV_DIR, f"report_h24_{date_norm}.csv")

    result_df['data_calendario'] = date_norm
    result_df['logic_version'] = "1.0.15"

    final_columns = [
        'data_calendario', 'callsign', 'tipo_movimento', 'direzione_sacbo',
        'fonte_scheduled', 'destinazione_finale', 'stato_destinazione',
        'compagnia_aerea', 'modello_aereo', 'orario_schedulato', 'timestamp',
        'pista', 'pista_fonte', 'fase_volo', 'direzione', 'quota_ft', 'rotta_deg',
        'distanza_km', 'paese', 'matched_score', 'icao24',
        'stima_passeggeri', 'stima_rumore_db', 'is_scheduled', 'logic_version'
    ]
    for col in final_columns:
        if col not in result_df.columns: result_df[col] = ''
    result_df[final_columns].to_csv(out_path, index=False, encoding='utf-8-sig')
    msg = f"✅ Report H24: {len(result_df)} voli (esclusi {n_esclusi}, dedup sched {n_dedup_sched}, dedup icao {n_dedup_icao24})"
    logger.info(msg)
    return out_path, msg


if __name__ == "__main__":
    path, msg = generate_h24_report()
    print(msg)
    if path: print(f"📁 File: {path}")