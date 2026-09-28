"""
bgy_reports/bgy_report_night.py - Report notturno integrato (SACBO + OpenSky).
Versione 2.8.8

Modello logico:
- Il TABELLONE SACBO è la fonte primaria per i voli PASSEGGERI.
- Il RADAR arricchisce i passeggeri + identifica Cargo e Charter.

Categorie finali:
  1. Passeggeri        — dal tabellone (con o senza match radar)
  2. Cargo (Nome)      — radar + _cargo_airlines
  3. Charter (Nome)    — radar + _charter_airlines
  4. Passeggeri (radar) — radar + compagnia di linea fuori tabellone
  5. Non identificato  — radar + callsign ignoto

Visibilità:
  - Visibili di default: Passeggeri, Cargo, Charter
  - Opt-in (checkbox GUI): Passeggeri (radar), Non identificato

Novità v2.8.8 (sconfinamenti, logica baseline 23:00):
- Nuova logica di classificazione dei voli sconfinamento basata sulla
  scansione delle 23:00 come baseline:
    1. Se orario_schedulato in fascia 23:00-05:59 → 'regolare'
    2. Altrimenti, guarda la STIMA nella scansione 23:00:
       a. Fuori fascia → escludi (non è sconfinamento)
       b. In fascia 23:01-05:59 → candidato
    3. Verifica le scansioni successive (00:00, 02:00, 05:00):
       - Se compare 'CANCELLATO' → escludi
       - Se riappare con STIMA fuori fascia (ritardo rientrato) → escludi
       - Altrimenti → 'sconfinamento' confermato
- Fix del bug FR 3530 (STIMA 01:40 solo a mezzanotte, baseline 07:55).
- Il CSV finale ha una colonna notte_categoria ('regolare' | 'sconfinamento').

Novità v2.8.7 (sconfinamenti, prima iterazione):
- Aggiunta colonna notte_categoria.
- Filtro iniziale con check su orario_effettivo.

Novità v2.8.6:
- Caricamento scansioni SACBO del giorno successivo (00:00-05:59).
- Reintrodotto import timedelta.

Novità v2.8.5:
- Aggiunta colonna direzione_sacbo (D/A).

Novità v2.8.3:
- PAX e rumore calcolati solo sui Visibili.
"""
import os
import math
from collections import defaultdict
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

NIGHT_START_HOUR = 23
NIGHT_END_HOUR = 6
SCONFINAMENTO_START_MIN = 23 * 60 + 1
SCONFINAMENTO_END_MIN = 6 * 60

# Scansioni della sessione notturna, in ordine cronologico.
# Le scansioni di mezzanotte (00:00, 00:01) sono escluse dalla logica di
# classificazione perché possono contenere STIME transitorie errate.
SESSION_SCAN_TIMES = ['23-00', '00-00', '00-01', '02-00', '05-00', '06-00']
MEZZANOTTE_SCANS = {'00-00', '00-01'}


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
    """Estrae 'HH-MM' dal nome file scan_YYYY-MM-DD_HH-MM.csv."""
    try:
        base = filename.replace(".csv", "")
        parts = base.split("_")
        if len(parts) >= 3:
            scan_time = parts[2]
            if "-" in scan_time:
                return scan_time
            # Formato vecchio: HHMM senza trattino
            if len(scan_time) == 4:
                return f"{scan_time[:2]}-{scan_time[2:]}"
    except Exception:
        pass
    return None


def _scan_time_to_order(scan_time):
    """
    Converte 'HH-MM' in un intero per ordinamento cronologico della sessione
    notturna (che inizia alle 23:00 del giorno X).
      23:00 → 0
      00:00 → 60
      00:01 → 61
      02:00 → 180
      05:00 → 360
      06:00 → 420
    """
    try:
        hh, mm = map(int, scan_time.split('-'))
        if hh >= 23:
            return hh * 60 + mm - 23 * 60
        else:
            return (hh + 24) * 60 + mm - 23 * 60
    except Exception:
        return 9999


def _classify_volo(records):
    """
    Classifica un volo in base ai suoi record (uno per scansione),
    ordinati cronologicamente dal più vecchio al più recente.

    Ritorna:
      - 'regolare'      : orario_schedulato in fascia 23:00-05:59
      - 'sconfinamento' : orario_schedulato fuori fascia, ma baseline 23:00
                          con STIMA in fascia 23:01-05:59, non cancellato,
                          e non rientrato in orario
      - None            : escluso

    Logica (v2.8.8, baseline 23:00):
      1. Se sched in fascia → 'regolare'
      2. Trova il record baseline (prima scansione non di mezzanotte;
         se non esiste, il primo record in assoluto).
      3. Se la STIMA del baseline è fuori fascia → escludi.
      4. Se compare 'CANCELLATO' in una qualsiasi scansione → escludi.
      5. Se il volo riappare dopo il baseline con STIMA fuori fascia
         (escluse le scansioni di mezzanotte) → escludi (ritardo rientrato).
      6. Altrimenti → 'sconfinamento'.
    """
    if not records:
        return None

    sched = records[0]['orario_schedulato']

    # 1. Sched in fascia → regolare
    if _is_in_night_schedule(sched):
        return 'regolare'

    # 2. Baseline: prima scansione non di mezzanotte
    ref = None
    ref_index = None
    for i, r in enumerate(records):
        if r['scan_time'] in MEZZANOTTE_SCANS:
            continue
        ref = r
        ref_index = i
        break

    # Fallback: se il volo compare solo a mezzanotte, usa il primo record
    if ref is None:
        ref = records[0]
        ref_index = 0

    # 3. STIMA del baseline fuori fascia → escludi
    stima_ref = ref.get('orario_effettivo')
    if not stima_ref or not _is_in_sconfinamento_effective(stima_ref):
        return None

    # 4. CANCELLATO in qualsiasi scansione → escludi
    for r in records:
        stato = str(r.get('stato_volo', '')).upper()
        if 'CANCELLAT' in stato or 'CANCEL' in stato:
            return None

    # 5. Rientro ritardo: riappare dopo il baseline con STIMA fuori fascia
    for r in records[ref_index + 1:]:
        if r['scan_time'] in MEZZANOTTE_SCANS:
            continue
        stima = r.get('orario_effettivo')
        if stima and not _is_in_sconfinamento_effective(stima):
            return None

    # 6. Sconfinamento confermato
    return 'sconfinamento'


# -----------------------------------------------------------------------------
# CARICAMENTO DATI
# -----------------------------------------------------------------------------

def load_scheduled_flights(date_str):
    """
    Carica i voli schedulati notturni dalle scansioni della sessione
    (23:00 del giorno X + 00:00-05:59 del giorno X+1).

    Per ogni (callsign, orario_schedulato) raccoglie TUTTI i record
    dalle varie scansioni, poi li classifica con _classify_volo().

    Aggiunge la colonna notte_categoria ('regolare' | 'sconfinamento').
    """
    date_norm = normalize_date(date_str)
    next_date = (datetime.strptime(date_norm, "%Y-%m-%d")
                 + timedelta(days=1)).strftime("%Y-%m-%d")
    date_clean = date_norm.replace("-", "")
    next_clean = next_date.replace("-", "")

    # Raccogli solo le scansioni della sessione notturna
    scan_files = []
    if os.path.isdir(RAW_DIR):
        for f in os.listdir(RAW_DIR):
            if not f.startswith("scan_") or not f.endswith(".csv"):
                continue

            scan_time = _extract_scan_time(f)
            if not scan_time or scan_time not in SESSION_SCAN_TIMES:
                continue

            # Scansioni del giorno X con orario >= 23:00
            if f.startswith(f"scan_{date_norm}_") or f.startswith(f"scan_{date_clean}_"):
                try:
                    hh = int(scan_time.split("-")[0])
                    if hh >= 23:
                        scan_files.append(f)
                except Exception:
                    pass
            # Scansioni del giorno X+1 con orario < 06:00
            elif f.startswith(f"scan_{next_date}_") or f.startswith(f"scan_{next_clean}_"):
                try:
                    hh = int(scan_time.split("-")[0])
                    if hh < 6:
                        scan_files.append(f)
                except Exception:
                    pass

    scan_files.sort()
    logger.info(f"🔎 Scansioni notturne trovate: {len(scan_files)}")

    # Raggruppa per (callsign, orario_schedulato)
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
                sched = row.get('orario_schedulato')
                if not sched:
                    continue
                cs = str(row.get('callsign_volo', '')).strip()
                key = (cs, str(sched).strip())
                flights[key].append({
                    'scan_time': scan_time,
                    'callsign_volo': cs,
                    'orario_schedulato': str(sched).strip(),
                    'orario_effettivo': row.get('orario_effettivo'),
                    'stato_volo': row.get('stato_volo'),
                    'tipo_movimento': row.get('tipo_movimento'),
                    'destinazione_origine': row.get('destinazione_origine'),
                })
        except Exception as e:
            logger.warning(f"Errore lettura {f}: {e}")

    # Ordina i record di ogni volo cronologicamente
    for key in flights:
        flights[key].sort(key=lambda r: _scan_time_to_order(r['scan_time']))

    # Classifica
    scheduled = []
    n_regolare = 0
    n_sconfinamento = 0
    n_esclusi = 0

    for key, records in flights.items():
        categoria = _classify_volo(records)
        if categoria is None:
            n_esclusi += 1
            continue

        # Scegli il record rappresentativo:
        # il più recente con STIMA in fascia notturna, altrimenti l'ultimo.
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
        else:
            n_sconfinamento += 1

    if scheduled:
        df_sched = pd.DataFrame(scheduled)
        logger.info(
            f"📋 Caricati {len(df_sched)} voli schedulati notturni "
            f"(regolari {n_regolare}, sconfinamenti {n_sconfinamento}, "
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

def _is_phase_compatible(direzione_sacbo, fase_volo):
    if direzione_sacbo == 'D':
        return fase_volo == 'Decollo'
    if direzione_sacbo == 'A':
        return fase_volo in ('Atterraggio', 'Avvicinamento')
    return False


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
        scheduled_df['tipo_movimento'] = 'Passeggeri'
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

    matched = []
    used_radar_idx = set()

    for _, s in sched.iterrows():
        sched_min = s['_sched_min']
        direzione = s.get('direzione_sacbo', '')
        categoria = s.get('notte_categoria', '')

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
            combined['notte_categoria'] = categoria
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
            if not _is_phase_compatible(direzione, fase):
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
            combined['notte_categoria'] = categoria
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
            combined['notte_categoria'] = categoria
            matched.append(combined)

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
        if 'notte_categoria' not in row_dict or not row_dict.get('notte_categoria'):
            row_dict['notte_categoria'] = ''
        if 'direzione_sacbo' not in row_dict or not row_dict.get('direzione_sacbo'):
            if fase == 'Decollo':
                row_dict['direzione_sacbo'] = 'D'
            elif fase in ('Atterraggio', 'Avvicinamento'):
                row_dict['direzione_sacbo'] = 'A'
            else:
                row_dict['direzione_sacbo'] = '?'

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
    pax = len(result_df[result_df['tipo_movimento'] == 'Passeggeri']) if 'tipo_movimento' in result_df.columns else 0
    cargo = len(result_df[result_df['tipo_movimento'].str.startswith('Cargo', na=False)]) if 'tipo_movimento' in result_df.columns else 0
    charter = len(result_df[result_df['tipo_movimento'].str.startswith('Charter', na=False)]) if 'tipo_movimento' in result_df.columns else 0
    pax_radar = len(result_df[result_df['tipo_movimento'] == 'Passeggeri (radar)']) if 'tipo_movimento' in result_df.columns else 0
    non_id = len(result_df[result_df['tipo_movimento'] == 'Non identificato']) if 'tipo_movimento' in result_df.columns else 0

    n_sconfinamenti = 0
    if 'notte_categoria' in result_df.columns:
        n_sconfinamenti = int(
            ((result_df['notte_categoria'] == 'sconfinamento')
             & (result_df['tipo_movimento'] == 'Passeggeri')).sum()
        )

    visibili = pax + cargo + charter

    visibili_mask = result_df['tipo_movimento'].apply(
        lambda x: isinstance(x, str) and (
            x == 'Passeggeri'
            or x.startswith('Cargo')
            or x.startswith('Charter')
        )
    ) if 'tipo_movimento' in result_df.columns else pd.Series(False, index=result_df.index)
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

    sconfinamenti_msg = (
        f", sconfinamenti {n_sconfinamenti}" if n_sconfinamenti > 0 else ""
    )

    msg = (f"✅ Report notturno: {total} voli "
           f"(Visibili: {visibili} = Passeggeri {pax} + Cargo {cargo} "
           f"+ Charter {charter}{sconfinamenti_msg} | "
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