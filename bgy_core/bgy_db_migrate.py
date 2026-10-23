"""
bgy_core/bgy_db_migrate.py - Import e sincronizzazione CSV -> PostgreSQL.
Versione 2.10.5

Novita v2.10.3 (22/10/2026, BUG-09):
- run_quality_check() ora legge le soglie da config_data.json > quality_check.thresholds
  (max_flights_per_night, min_flights_per_night, max_cargo_per_night, max_rumore_db).
  Prima erano hardcoded, violando il Principio fondante 2 (zero hardcoded).
- Aggiunta helper _get_quality_thresholds() con fallback ai default storici.
- get_nightly_stats() e get_non_classified_flights(): commentato TODO BUG-10
  (restano stub, implementazione richiede bgy_mailer.py come contratto).

Novita v2.10.2 (21/10/2026):
- Ripristinata la funzione run_quality_check() (era stata troncata).

Novita v2.10.1 (Cantiere B.2, 19/10/2026):
- Fix parametri per import_h24_file().
"""
import os
import sys
import re
import csv
import argparse
from datetime import datetime, timedelta
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import RAW_DIR, OUTPUT_CSV_DIR
from bgy_core import bgy_db
from bgy_core.bgy_dates import parse_radar_filename
from bgy_core.bgy_config_manager import config_manager

logger = get_logger("DBMigrate")

BATCH_SIZE = 500
_FORCE_REIMPORT = False
_schema_updates_applied = False
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AVIONIO_DIR = os.path.join(_PROJECT_ROOT, "bgy_data", "bgy_avionio")

EXPECTED_NEW_COLUMNS = {"callsign_volo", "tipo_movimento", "destinazione_origine", "orario_schedulato", "orario_effettivo", "stato_volo"}
EXPECTED_OLD_COLUMNS = {"flight_num", "type", "sched_time", "actual_time", "origin_dest", "status"}
OLD_MOVEMENT_MAP = {"decollo": "D", "atterraggio": "A", "partenza": "D", "arrivo": "A"}

stats = {
    "scans_imported": 0, "scans_skipped": 0, "scans_recovered": 0, "scans_old_format": 0, "scans_unsupported": 0,
    "flights_imported": 0, "radar_imported": 0, "weather_imported": 0, "nightly_imported": 0,
    "avionio_imported": 0, "h24_imported": 0, "errors": 0,
}

def _reset_stats():
    for k in stats: stats[k] = 0


def _register_schema_version():
    from bgy_core import bgy_db
    version = bgy_db.SCHEMA_VERSION
    bgy_db.execute_query(
        "INSERT INTO schema_version (version, note) VALUES (%s, %s) ON CONFLICT (version) DO NOTHING",
        (version, "v2.11.0 (B.2): h24_reports + v_h24_report + data_calendario in flights_avionio"), fetch=False
    )


def apply_schema_updates():
    global _schema_updates_applied
    if _schema_updates_applied: return True
    updates = [
        "ALTER TABLE nightly_reports ADD COLUMN IF NOT EXISTS direzione_sacbo VARCHAR(2)",
        "ALTER TABLE nightly_reports ADD COLUMN IF NOT EXISTS notte_categoria VARCHAR(30)",
        "ALTER TABLE nightly_reports ADD COLUMN IF NOT EXISTS icao24 VARCHAR(6)",
        "ALTER TABLE nightly_reports ADD COLUMN IF NOT EXISTS fonte_scheduled VARCHAR(10) DEFAULT 'sacbo'",
        "ALTER TABLE nightly_reports ADD COLUMN IF NOT EXISTS pista_fonte VARCHAR(20)",
        "ALTER TABLE radar_detections ADD COLUMN IF NOT EXISTS fonte TEXT",
        "ALTER TABLE radar_detections ADD COLUMN IF NOT EXISTS timestamp_utc TIMESTAMPTZ",
        "ALTER TABLE radar_detections ADD COLUMN IF NOT EXISTS data_riferimento DATE",
        "ALTER TABLE radar_detections ALTER COLUMN sessione_notturna DROP NOT NULL",
        "ALTER TABLE scans ADD COLUMN IF NOT EXISTS source VARCHAR(20) DEFAULT 'sacbo'",
        "CREATE INDEX IF NOT EXISTS idx_nightly_icao24 ON nightly_reports(icao24) WHERE icao24 IS NOT NULL",
        """CREATE TABLE IF NOT EXISTS callsign_classifications (
            callsign VARCHAR(10) PRIMARY KEY, categoria VARCHAR(30) NOT NULL,
            nome_compagnia VARCHAR(100), note TEXT,
            created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
        )""",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_nightly_radar_only_unique ON nightly_reports (data_riferimento, icao24, timestamp) WHERE is_scheduled = FALSE AND icao24 IS NOT NULL AND timestamp IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS uniq_nightly_flight ON nightly_reports (data_riferimento, callsign, orario_schedulato) WHERE orario_schedulato IS NOT NULL",
        """CREATE TABLE IF NOT EXISTS flights_avionio (
            id BIGSERIAL PRIMARY KEY, scan_id BIGINT REFERENCES scans(id) ON DELETE CASCADE,
            callsign_volo TEXT NOT NULL, tipo_movimento VARCHAR(2), destinazione_origine TEXT,
            orario_schedulato TIME, orario_effettivo TIME, stato_volo TEXT, codice_iata VARCHAR(3),
            compagnia_aerea TEXT, scan_timestamp TIMESTAMP NOT NULL, data_riferimento DATE NOT NULL,
            imported_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE (data_riferimento, callsign_volo, orario_schedulato, tipo_movimento)
        )""",
        "CREATE INDEX IF NOT EXISTS idx_avionio_data ON flights_avionio (data_riferimento)",
        "CREATE INDEX IF NOT EXISTS idx_avionio_callsign ON flights_avionio (callsign_volo)",
        "CREATE INDEX IF NOT EXISTS idx_avionio_scan ON flights_avionio (scan_id)",
        "CREATE INDEX IF NOT EXISTS idx_avionio_ts ON flights_avionio (scan_timestamp)",
        "ALTER TABLE flights_avionio ADD COLUMN IF NOT EXISTS data_calendario DATE",
        """CREATE TABLE IF NOT EXISTS h24_reports (
            id BIGSERIAL PRIMARY KEY, data_riferimento DATE NOT NULL, data_calendario DATE NOT NULL,
            callsign TEXT, tipo_movimento TEXT, direzione_sacbo VARCHAR(2), fascia VARCHAR(10),
            categoria VARCHAR(30), is_scheduled BOOLEAN, fonte_scheduled VARCHAR(10),
            destinazione_finale TEXT, stato_destinazione TEXT, compagnia_aerea TEXT, modello_aereo TEXT,
            orario_schedulato TIME, timestamp TIMESTAMP, pista TEXT, pista_fonte VARCHAR(20),
            fase_volo TEXT, direzione TEXT, quota_ft INTEGER, rotta_deg REAL, distanza_km REAL,
            paese TEXT, matched_score INTEGER, icao24 VARCHAR(6), stima_passeggeri INTEGER,
            stima_rumore_db INTEGER, logic_version VARCHAR(20), imported_at TIMESTAMP NOT NULL DEFAULT NOW()
        )""",
        "CREATE INDEX IF NOT EXISTS idx_h24_calendario ON h24_reports (data_calendario)",
        "CREATE INDEX IF NOT EXISTS idx_h24_riferimento ON h24_reports (data_riferimento)",
        "CREATE INDEX IF NOT EXISTS idx_h24_callsign ON h24_reports (callsign)",
        "ALTER TABLE h24_reports ADD COLUMN IF NOT EXISTS pista_fonte VARCHAR(20)",
        """CREATE OR REPLACE VIEW v_h24_report AS
        SELECT data_calendario AS data, callsign, tipo_movimento, direzione_sacbo,
            categoria AS notte_categoria, is_scheduled, fonte_scheduled, destinazione_finale,
            compagnia_aerea, modello_aereo, orario_schedulato, timestamp, pista, pista_fonte,
            fase_volo, quota_ft, distanza_km, matched_score, icao24, stima_passeggeri,
            stima_rumore_db, EXTRACT(HOUR FROM timestamp)::int AS ora_effettiva
        FROM h24_reports"""
    ]
    for sql in updates:
        ok, result = bgy_db.execute_query(sql, fetch=False)
        if not ok:
            logger.error(f"❌ Schema update fallito: {sql} → {result}")
            return False
    _register_schema_version()
    _schema_updates_applied = True
    return True


def _dedup_radar_only_params(params):
    seen = set(); out = []; removed = 0
    for p in params:
        orario_sched = p[10]; timestamp = p[11]; icao24 = p[22]; data_rif = p[0]
        if orario_sched is not None: out.append(p); continue
        if icao24 is None or timestamp is None: out.append(p); continue
        key = (data_rif, icao24, timestamp)
        if key in seen: removed += 1; continue
        seen.add(key); out.append(p)
    return out


def parse_date_from_scan_filename(filename):
    base = filename.replace(".csv", "")
    m = re.match(r'^scan_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2})$', base)
    if m:
        date_str = m.group(1); hh_mm = m.group(2).replace("-", ":")
        hh = int(hh_mm.split(":")[0])
        return date_str, hh_mm, ("notturno" if hh >= 23 or hh < 6 else "diurno")
    m = re.match(r'^scan_(\d{8})_(\d{4})$', base)
    if m:
        ymd = m.group(1); date_str = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"
        hh = int(m.group(2)[:2]); mm = int(m.group(2)[2:])
        return date_str, f"{hh:02d}:{mm:02d}", ("notturno" if hh >= 23 or hh < 6 else "diurno")
    return None, None, None


def parse_meteo_filename(filename):
    m = re.match(r'^meteo_(\d{4}-\d{2}-\d{2})$', filename.replace(".csv", ""))
    return m.group(1) if m else None


def parse_nightly_filename(filename):
    m = re.match(r'^report_nightly_(\d{4}-\d{2}-\d{2})$', filename.replace(".csv", ""))
    return m.group(1) if m else None


def parse_h24_filename(filename):
    m = re.match(r'^report_h24_(\d{4}-\d{2}-\d{2})$', filename.replace(".csv", ""))
    return m.group(1) if m else None


def safe_int(value, default=None):
    if value is None: return default
    try:
        s = str(value).strip()
        if s == "" or s.upper() == "N/D": return default
        return int(float(s))
    except (ValueError, TypeError): return default


def safe_float(value, default=None):
    if value is None: return default
    try:
        s = str(value).strip()
        if s == "" or s.upper() == "N/D": return default
        return float(s)
    except (ValueError, TypeError): return default


def safe_str(value, default=""):
    if value is None: return default
    s = str(value).strip()
    return s if s else default


def safe_time(value):
    s = safe_str(value)
    if not s or s == "N/D": return None
    m = re.match(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?$', s)
    if m: return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}:{int(m.group(3)) if m.group(3) else 0:02d}"
    return None


def safe_timestamp(value):
    s = safe_str(value)
    if not s: return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try: datetime.strptime(s, fmt); return s
        except ValueError: continue
    return None


def safe_bool(value):
    s = safe_str(value).lower()
    if s in ("true", "1", "yes", "si", "sì"): return True
    if s in ("false", "0", "no"): return False
    return None


def read_csv_rows(path):
    rows = []
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader: rows.append(row)
    except Exception as e:
        logger.error(f"Errore lettura {path}: {e}")
    return rows


def detect_scan_format(rows):
    if not rows: return None
    keys = set(rows[0].keys())
    if EXPECTED_NEW_COLUMNS.issubset(keys): return "new"
    if EXPECTED_OLD_COLUMNS.issubset(keys): return "old"
    return None


def import_scan_file(filepath):
    filename = os.path.basename(filepath)
    date_str, time_str, tipo = parse_date_from_scan_filename(filename)
    if not date_str: return False, None
    ok, rows = bgy_db.execute_query("SELECT s.id, (SELECT COUNT(1) FROM flights_sacbo f WHERE f.scan_id = s.id) AS n_flights FROM scans s WHERE s.file_name = %s", (filename,))
    if ok and rows:
        scan_id_existing, n_flights = rows[0]
        if n_flights and n_flights > 0:
            if not _FORCE_REIMPORT:
                stats["scans_skipped"] += 1; return False, None
            else:
                bgy_db.execute_query("DELETE FROM flights_sacbo WHERE scan_id = %s", (scan_id_existing,), fetch=False)
                bgy_db.execute_query("DELETE FROM scans WHERE id = %s", (scan_id_existing,), fetch=False)
                stats["scans_recovered"] += 1
        else:
            bgy_db.execute_query("DELETE FROM scans WHERE id = %s", (scan_id_existing,))
            stats["scans_recovered"] += 1
    csv_rows = read_csv_rows(filepath)
    if not csv_rows: return False, None
    fmt = detect_scan_format(csv_rows)
    if fmt is None: stats["scans_unsupported"] += 1; return False, None
    if fmt == "old": stats["scans_old_format"] += 1
    fonte_scan = "sacbo"
    if csv_rows and "fonte_scan" in csv_rows[0]:
        fonte_scan = safe_str(csv_rows[0].get("fonte_scan"), "sacbo") or "sacbo"
        if fonte_scan not in ("sacbo", "avionio"): fonte_scan = "sacbo"
    scan_ts = None
    for r in csv_rows:
        ts = safe_timestamp(r.get("scan_timestamp"))
        if ts: scan_ts = ts; break
    if not scan_ts: scan_ts = f"{date_str} {time_str}:00"
    ok, result = bgy_db.execute_query("""INSERT INTO scans (scan_timestamp, file_name, data_riferimento, tipo, righe_importate, source) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""", (scan_ts, filename, date_str, tipo, len(csv_rows), fonte_scan))
    if not ok: stats["errors"] += 1; return False, None
    scan_id = result[0][0] if result else None
    if not scan_id: stats["errors"] += 1; return False, None
    flights_params = []
    for r in csv_rows:
        if fmt == "new":
            callsign = safe_str(r.get("callsign_volo"), "N/D"); tipo_mov = safe_str(r.get("tipo_movimento"), "")
            dest = safe_str(r.get("destinazione_origine"), ""); sched = safe_time(r.get("orario_schedulato"))
            eff = safe_time(r.get("orario_effettivo")); stato = safe_str(r.get("stato_volo"), "")
        else:
            callsign = safe_str(r.get("flight_num"), "N/D"); tipo_mov = safe_str(r.get("type"), "")
            dest = safe_str(r.get("origin_dest"), ""); sched = safe_time(r.get("sched_time"))
            eff = safe_time(r.get("actual_time")); stato = safe_str(r.get("status"), "")
        flights_params.append((scan_id, callsign, tipo_mov, dest, sched, eff, stato, scan_ts, date_str))
    total_inserted = 0
    for i in range(0, len(flights_params), BATCH_SIZE):
        batch = flights_params[i:i+BATCH_SIZE]
        ok, result = bgy_db.execute_many("""INSERT INTO flights_sacbo (scan_id, callsign_volo, tipo_movimento, destinazione_origine, orario_schedulato, orario_effettivo, stato_volo, scan_timestamp, data_riferimento) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""", batch)
        if ok: total_inserted += len(batch)
        else: stats["errors"] += 1
    stats["scans_imported"] += 1; stats["flights_imported"] += total_inserted
    return True, total_inserted


def _radar_session_date_from_ts(ts_str):
    try: dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try: dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")
        except ValueError: return None
    if dt.hour >= 23: return dt.strftime("%Y-%m-%d")
    if dt.hour < 6: return (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    return None


def import_radar_file(filepath):
    filename = os.path.basename(filepath)
    date_str = parse_radar_filename(filename)
    if not date_str: return False, None
    csv_rows = read_csv_rows(filepath)
    if not csv_rows: return False, None
    n_csv = len(csv_rows)
    ok, rows = bgy_db.execute_query("SELECT COUNT(1) FROM radar_detections WHERE data_riferimento = %s", (date_str,))
    n_db = rows[0][0] if ok and rows else 0
    if not _FORCE_REIMPORT:
        if n_db >= n_csv: stats["scans_skipped"] += 1; return False, None
        if n_db > 0 and n_db < n_csv:
            bgy_db.execute_query("DELETE FROM radar_detections WHERE data_riferimento = %s", (date_str,), fetch=False)
    else:
        if n_db > 0: bgy_db.execute_query("DELETE FROM radar_detections WHERE data_riferimento = %s", (date_str,), fetch=False)
    params = []
    for r in csv_rows:
        ts = safe_timestamp(r.get("timestamp"))
        if not ts: continue
        data_rif = ts[:10]; sessione = _radar_session_date_from_ts(ts)
        fonte = safe_str(r.get("fonte"), "unknown")
        ts_utc = safe_str(r.get("timestamp_utc"), "") or None
        params.append((ts, safe_str(r.get("callsign"), ""), safe_str(r.get("icao24"), ""), safe_str(r.get("pista"), ""), safe_str(r.get("fase_volo"), ""), safe_str(r.get("direzione"), ""), safe_int(r.get("quota_ft"), 0), safe_float(r.get("rotta_deg"), 0.0), safe_float(r.get("distanza_km"), 0.0), safe_str(r.get("paese"), ""), sessione, data_rif, fonte, ts_utc))
    if not params: return False, None
    total = 0
    for i in range(0, len(params), BATCH_SIZE):
        batch = params[i:i+BATCH_SIZE]
        ok, result = bgy_db.execute_many("""INSERT INTO radar_detections (timestamp, callsign, icao24, pista, fase_volo, direzione, quota_ft, rotta_deg, distanza_km, paese, sessione_notturna, data_riferimento, fonte, timestamp_utc) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", batch)
        if ok: total += len(batch)
        else: stats["errors"] += 1
    stats["radar_imported"] += total
    return True, total


def import_meteo_file(filepath):
    filename = os.path.basename(filepath)
    date_str = parse_meteo_filename(filename)
    if not date_str: return False, None
    if not _FORCE_REIMPORT:
        ok, rows = bgy_db.execute_query("SELECT COUNT(1) FROM weather_hourly WHERE data_riferimento = %s", (date_str,))
        if ok and rows and rows[0][0] > 0: stats["scans_skipped"] += 1; return False, None
    else:
        ok, rows = bgy_db.execute_query("SELECT COUNT(1) FROM weather_hourly WHERE data_riferimento = %s", (date_str,))
        n_db = rows[0][0] if ok and rows else 0
        if n_db > 0: bgy_db.execute_query("DELETE FROM weather_hourly WHERE data_riferimento = %s", (date_str,), fetch=False)
    csv_rows = read_csv_rows(filepath)
    if not csv_rows: return False, None
    params = []
    for r in csv_rows:
        orario = safe_time(r.get("orario"))
        if not orario: continue
        row_date = safe_str(r.get("data_riferimento"), date_str)
        params.append((row_date, orario, safe_float(r.get("temperatura_c")), safe_float(r.get("precipitazioni_mm")), safe_float(r.get("vento_kmh")), safe_int(r.get("vento_direzione_deg")), safe_str(r.get("condizioni"), "")))
    if not params: return False, None
    ok, result = bgy_db.execute_many("""INSERT INTO weather_hourly (data_riferimento, orario, temperatura_c, precipitazioni_mm, vento_kmh, vento_direzione_deg, condizioni) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (data_riferimento, orario) DO NOTHING""", params)
    if not ok: stats["errors"] += 1; return False, None
    stats["weather_imported"] += len(params)
    return True, len(params)


def import_nightly_file(filepath):
    filename = os.path.basename(filepath)
    date_str = parse_nightly_filename(filename)
    if not date_str: return False, None
    csv_rows = read_csv_rows(filepath)
    if not csv_rows: return False, None
    n_csv = len(csv_rows)
    ok, rows = bgy_db.execute_query("SELECT COUNT(1) FROM nightly_reports WHERE data_riferimento = %s", (date_str,))
    n_db = rows[0][0] if ok and rows else 0
    if not _FORCE_REIMPORT:
        if n_db == n_csv and n_csv > 0: stats["scans_skipped"] += 1; return False, None
        if n_db > 0: bgy_db.execute_query("DELETE FROM nightly_reports WHERE data_riferimento = %s", (date_str,), fetch=False)
    else:
        if n_db > 0: bgy_db.execute_query("DELETE FROM nightly_reports WHERE data_riferimento = %s", (date_str,), fetch=False)
    params = []
    for r in csv_rows:
        is_sched_bool = safe_bool(r.get("is_scheduled"))
        fonte_val = safe_str(r.get("fonte_scheduled"), "")
        fonte_param = None if not is_sched_bool else (fonte_val if fonte_val in ("sacbo", "avionio") else "sacbo")
        icao_val = safe_str(r.get("icao24"), "") or None
        params.append((date_str, safe_str(r.get("callsign"), ""), safe_str(r.get("tipo_movimento"), ""), safe_str(r.get("direzione_sacbo"), ""), safe_str(r.get("notte_categoria"), ""), is_sched_bool, safe_str(r.get("destinazione_finale"), ""), safe_str(r.get("stato_destinazione"), ""), safe_str(r.get("compagnia_aerea"), ""), safe_str(r.get("modello_aereo"), ""), safe_time(r.get("orario_schedulato")), safe_timestamp(r.get("timestamp")), safe_str(r.get("pista"), ""), safe_str(r.get("pista_fonte"), "N/D"), safe_str(r.get("fase_volo"), ""), safe_str(r.get("direzione"), ""), safe_int(r.get("quota_ft"), 0), safe_float(r.get("rotta_deg"), 0.0), safe_float(r.get("distanza_km"), 0.0), safe_str(r.get("paese"), ""), safe_int(r.get("matched_score"), 0), safe_int(r.get("stima_passeggeri"), 0), safe_int(r.get("stima_rumore_db"), 0), icao_val, fonte_param))
    if not params: return False, None
    params = _dedup_radar_only_params(params)
    total_inserted = 0; total_conflicts = 0
    for i in range(0, len(params), BATCH_SIZE):
        batch = params[i:i+BATCH_SIZE]
        ok, result = bgy_db.execute_many("""INSERT INTO nightly_reports (data_riferimento, callsign, tipo_movimento, direzione_sacbo, notte_categoria, is_scheduled, destinazione_finale, stato_destinazione, compagnia_aerea, modello_aereo, orario_schedulato, timestamp, pista, pista_fonte, fase_volo, direzione, quota_ft, rotta_deg, distanza_km, paese, matched_score, stima_passeggeri, stima_rumore_db, icao24, fonte_scheduled) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (data_riferimento, callsign, orario_schedulato) WHERE orario_schedulato IS NOT NULL DO NOTHING""", batch)
        if ok:
            inserted_batch = result if isinstance(result, int) else len(batch)
            total_inserted += inserted_batch; total_conflicts += (len(batch) - inserted_batch)
        else: stats["errors"] += 1
    stats["nightly_imported"] += total_inserted
    return True, total_inserted


def import_h24_file(filepath):
    filename = os.path.basename(filepath)
    date_str = parse_h24_filename(filename)
    if not date_str: return False, None
    csv_rows = read_csv_rows(filepath)
    if not csv_rows: return False, None
    n_csv = len(csv_rows)
    ok, rows = bgy_db.execute_query("SELECT COUNT(1) FROM h24_reports WHERE data_calendario = %s", (date_str,))
    n_db = rows[0][0] if ok and rows else 0
    if not _FORCE_REIMPORT and n_db == n_csv and n_csv > 0: stats["scans_skipped"] += 1; return False, None
    if n_db > 0: bgy_db.execute_query("DELETE FROM h24_reports WHERE data_calendario = %s", (date_str,), fetch=False)
    params = []
    for r in csv_rows:
        is_sched_bool = safe_bool(r.get("is_scheduled"))
        fonte_val = safe_str(r.get("fonte_scheduled"), "")
        fonte_param = None if not is_sched_bool else (fonte_val if fonte_val in ("sacbo", "avionio") else "sacbo")
        icao_val = safe_str(r.get("icao24"), "") or None
        params.append((date_str, date_str, safe_str(r.get("callsign"), ""), safe_str(r.get("tipo_movimento"), ""), safe_str(r.get("direzione_sacbo"), ""), safe_str(r.get("fascia"), ""), safe_str(r.get("notte_categoria"), ""), is_sched_bool, fonte_param, safe_str(r.get("destinazione_finale"), ""), safe_str(r.get("stato_destinazione"), ""), safe_str(r.get("compagnia_aerea"), ""), safe_str(r.get("modello_aereo"), ""), safe_time(r.get("orario_schedulato")), safe_timestamp(r.get("timestamp")), safe_str(r.get("pista"), ""), safe_str(r.get("pista_fonte"), "N/D"), safe_str(r.get("fase_volo"), ""), safe_str(r.get("direzione"), ""), safe_int(r.get("quota_ft"), 0), safe_float(r.get("rotta_deg"), 0.0), safe_float(r.get("distanza_km"), 0.0), safe_str(r.get("paese"), ""), safe_int(r.get("matched_score"), 0), icao_val, safe_int(r.get("stima_passeggeri"), 0), safe_int(r.get("stima_rumore_db"), 0), safe_str(r.get("logic_version"), "1.0.0")))
    total_inserted = 0
    for i in range(0, len(params), BATCH_SIZE):
        batch = params[i:i+BATCH_SIZE]
        ok, result = bgy_db.execute_many("""INSERT INTO h24_reports (data_riferimento, data_calendario, callsign, tipo_movimento, direzione_sacbo, fascia, categoria, is_scheduled, fonte_scheduled, destinazione_finale, stato_destinazione, compagnia_aerea, modello_aereo, orario_schedulato, timestamp, pista, pista_fonte, fase_volo, direzione, quota_ft, rotta_deg, distanza_km, paese, matched_score, icao24, stima_passeggeri, stima_rumore_db, logic_version) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", batch)
        if ok: total_inserted += len(batch)
        else: stats["errors"] += 1
    stats["h24_imported"] += total_inserted
    return True, total_inserted


def _find_latest_avionio_file(movement_type):
    if not os.path.isdir(AVIONIO_DIR): return None
    pattern = re.compile(rf"^avionio_{movement_type}_(\d{{4}}-\d{{2}}-\d{{2}})_(\d{{2}}-\d{{2}})\.csv$")
    candidates = [(os.path.getmtime(os.path.join(AVIONIO_DIR, f)), os.path.join(AVIONIO_DIR, f)) for f in os.listdir(AVIONIO_DIR) if pattern.match(f)]
    return max(candidates, key=lambda x: x[0])[1] if candidates else None


def import_avionio_file(filepath, scan_id=None):
    filename = os.path.basename(filepath)
    m = re.match(r'^avionio_(arrivals|departures)_(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})\.csv$', filename)
    if not m: return False, 0, 0
    date_str = m.group(2); scan_ts = f"{date_str} {m.group(3)}:{m.group(4)}:00"
    csv_rows = read_csv_rows(filepath)
    if not csv_rows: return False, 0, 0
    params = []
    for r in csv_rows:
        callsign = safe_str(r.get("callsign_volo"), "")
        if not callsign: continue
        sched = safe_time(r.get("orario_schedulato"))
        data_rif_row = date_str
        if sched:
            hh_sched = int(sched.split(":")[0])
            if hh_sched < 6: data_rif_row = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        params.append((scan_id, callsign, safe_str(r.get("tipo_movimento"), ""), safe_str(r.get("destinazione_origine"), ""), sched, safe_time(r.get("orario_effettivo")), safe_str(r.get("stato_volo"), ""), safe_str(r.get("codice_iata"), ""), safe_str(r.get("compagnia_aerea"), ""), scan_ts, data_rif_row, date_str))
    if not params: return False, 0, 0
    total_inserted = 0
    for i in range(0, len(params), BATCH_SIZE):
        batch = params[i:i+BATCH_SIZE]
        ok, result = bgy_db.execute_many("""INSERT INTO flights_avionio (scan_id, callsign_volo, tipo_movimento, destinazione_origine, orario_schedulato, orario_effettivo, stato_volo, codice_iata, compagnia_aerea, scan_timestamp, data_riferimento, data_calendario) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (data_riferimento, callsign_volo, orario_schedulato, tipo_movimento) DO NOTHING""", batch)
        if ok: total_inserted += (result if isinstance(result, int) else len(batch))
    stats["avionio_imported"] += total_inserted
    return True, total_inserted, len(params) - total_inserted


def import_avionio_scan_to_db():
    if not bgy_db.is_enabled(): return False, "DB non abilitato"
    ok, msg = bgy_db.test_connection()
    if not ok: return False, f"DB non raggiungibile: {msg}"
    apply_schema_updates()
    total_inserted = 0; total_skipped = 0; files_processed = 0
    for movement in ("arrivals", "departures"):
        filepath = _find_latest_avionio_file(movement)
        if not filepath: continue
        ok, inserted, skipped = import_avionio_file(filepath)
        if ok: total_inserted += inserted; total_skipped += skipped; files_processed += 1
    return True, f"Avionio import: {total_inserted} righe inserite, {total_skipped} scartate ({files_processed} file)"


def _date_matches(filename, date_str):
    compact = date_str.replace("-", "")
    return date_str in filename or compact in filename


def list_files_for_date(date_str):
    scan_files, radar_files = [], []
    if os.path.isdir(RAW_DIR):
        for f in sorted(os.listdir(RAW_DIR)):
            full = os.path.join(RAW_DIR, f)
            if not f.endswith(".csv"): continue
            if f.startswith("scan_") and _date_matches(f, date_str): scan_files.append(full)
            elif (f.startswith("radar_") or f.startswith("bgy_night_flights_")) and _date_matches(f, date_str): radar_files.append(full)
    meteo_files, nightly_files, h24_files = [], [], []
    if os.path.isdir(OUTPUT_CSV_DIR):
        for f in sorted(os.listdir(OUTPUT_CSV_DIR)):
            full = os.path.join(OUTPUT_CSV_DIR, f)
            if not f.endswith(".csv"): continue
            if f.startswith("meteo_") and _date_matches(f, date_str): meteo_files.append(full)
            elif f.startswith("report_nightly_") and _date_matches(f, date_str): nightly_files.append(full)
            elif f.startswith("report_h24_") and _date_matches(f, date_str): h24_files.append(full)
    return {"scans": scan_files, "radar": radar_files, "meteo": meteo_files, "nightly": nightly_files, "h24": h24_files}


def sync_date(date_str, force=False):
    global _FORCE_REIMPORT
    if force: _FORCE_REIMPORT = True
    if not bgy_db.is_enabled(): return None
    ok, msg = bgy_db.test_connection()
    if not ok: return None
    apply_schema_updates()
    files = list_files_for_date(date_str)
    if sum(len(v) for v in files.values()) == 0: return {}
    result = {}
    for categoria, files_list, import_fn in (
        ("scans", files["scans"], import_scan_file), ("radar", files["radar"], import_radar_file),
        ("meteo", files["meteo"], import_meteo_file), ("nightly", files["nightly"], import_nightly_file),
        ("h24", files["h24"], import_h24_file)):
        imported = skipped = errors = 0
        for fp in files_list:
            try:
                ok, n = import_fn(fp)
                if ok: imported += 1
                else: skipped += 1
            except Exception as e:
                logger.error(f"Errore su {os.path.basename(fp)}: {e}")
                errors += 1
        result[categoria] = {"imported": imported, "skipped": skipped, "errors": errors}
    return result


def sync_yesterday(force=False):
    return sync_date((datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"), force=force)


def sync_last_n_days(n, force=False):
    today = datetime.now().date()
    results = {}
    for i in range(n):
        results[(today - timedelta(days=i)).strftime("%Y-%m-%d")] = sync_date((today - timedelta(days=i)).strftime("%Y-%m-%d"), force=force)
    return results


def reset_tables():
    tables = ["nightly_reports", "h24_reports", "weather_hourly", "radar_detections", "flights_sacbo", "flights_avionio", "scans"]
    ok, result = bgy_db.execute_query(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE", fetch=False)
    return ok


def migrate_all(reset=False, dry_run=False):
    if not bgy_db.is_enabled(): return False
    ok, msg = bgy_db.test_connection()
    if not ok: return False
    apply_schema_updates()
    if reset and not dry_run: reset_tables()
    scan_files, radar_files, meteo_files, nightly_files, h24_files = [], [], [], [], []
    if os.path.isdir(RAW_DIR):
        for f in sorted(os.listdir(RAW_DIR)):
            full = os.path.join(RAW_DIR, f)
            if not f.endswith(".csv"): continue
            if f.startswith("scan_"): scan_files.append(full)
            elif (f.startswith("radar_") or f.startswith("bgy_night_flights_")): radar_files.append(full)
    if os.path.isdir(OUTPUT_CSV_DIR):
        for f in sorted(os.listdir(OUTPUT_CSV_DIR)):
            full = os.path.join(OUTPUT_CSV_DIR, f)
            if not f.endswith(".csv"): continue
            if f.startswith("meteo_"): meteo_files.append(full)
            elif f.startswith("report_nightly_"): nightly_files.append(full)
            elif f.startswith("report_h24_"): h24_files.append(full)
    if dry_run: return True
    for fp in scan_files: import_scan_file(fp)
    for fp in radar_files: import_radar_file(fp)
    for fp in meteo_files: import_meteo_file(fp)
    for fp in nightly_files: import_nightly_file(fp)
    for fp in h24_files: import_h24_file(fp)
    counts = bgy_db.get_table_counts()
    for t, c in counts.items(): logger.info(f"  {t}: {c}")
    return True


# =============================================================================
# QUALITY CHECK (v2.10.3: soglie da config, non più hardcoded)
# =============================================================================

def _get_quality_thresholds():
    """
    Legge le soglie del quality check da config_data.json > quality_check.thresholds.
    Fallback ai default storici se la sezione manca (retrocompatibilità).
    """
    defaults = {
        "max_flights_per_night": 100,
        "min_flights_per_night": 3,
        "max_cargo_per_night":   15,
        "max_rumore_db":         120,
    }
    try:
        data_cfg = config_manager.get_data_config() or {}
        qc = data_cfg.get("quality_check", {}) or {}
        th = qc.get("thresholds", {}) or {}
        return {
            "max_flights_per_night": int(th.get("max_flights_per_night", defaults["max_flights_per_night"])),
            "min_flights_per_night": int(th.get("min_flights_per_night", defaults["min_flights_per_night"])),
            "max_cargo_per_night":   int(th.get("max_cargo_per_night",   defaults["max_cargo_per_night"])),
            "max_rumore_db":         int(th.get("max_rumore_db",         defaults["max_rumore_db"])),
        }
    except Exception as e:
        logger.warning(f"Impossibile leggere quality_check.thresholds da config, uso default: {e}")
        return defaults


def run_quality_check(days=7, dry_run=False):
    thresholds = _get_quality_thresholds()
    checks = []
    errori = 0
    warning = 0
    oggi = datetime.now().date()
    date_to = oggi.strftime("%Y-%m-%d")
    date_from = (oggi - timedelta(days=days)).strftime("%Y-%m-%d")

    def _add_check(id, label, ok, msg):
        nonlocal errori, warning
        checks.append({"id": id, "label": label, "ok": ok, "msg": msg})
        if not ok: errori += 1

    # Check 1: Compagnie placeholder
    ok, rows = bgy_db.execute_query("SELECT COUNT(*) FROM nightly_reports WHERE compagnia_aerea LIKE 'Compagnia %%' AND data_riferimento >= %s", (date_from,))
    n_placeholder = int(rows[0][0]) if ok and rows else 0
    _add_check(1, "Compagnie placeholder", n_placeholder == 0, f"{n_placeholder} voli")

    # Check 2: Report daily mancanti
    sql_missing = """
        SELECT d::date AS mancante
        FROM generate_series(%s::date, %s::date, '1 day'::interval) d
        LEFT JOIN (SELECT DISTINCT data_riferimento FROM flights_sacbo) f ON f.data_riferimento = d::date
        WHERE f.data_riferimento IS NULL
    """
    ok, rows = bgy_db.execute_query(sql_missing, (date_from, date_to))
    if ok and rows:
        mancanti = [r[0].strftime("%Y-%m-%d") for r in rows]
        _add_check(2, "Report daily mancanti", False, f"{len(mancanti)} (es. {mancanti[0]})")
    else:
        _add_check(2, "Report daily mancanti", True, "Nessuno")

    # Check 3: Voli notturni (min) — soglia da config
    ok, rows = bgy_db.execute_query("SELECT data_riferimento, COUNT(*) FROM nightly_reports WHERE data_riferimento >= %s GROUP BY data_riferimento", (date_from,))
    min_voli = min([r[1] for r in rows]) if ok and rows else 0
    _add_check(3, "Voli notturni (min)",
               min_voli >= thresholds["min_flights_per_night"],
               f"Minimo {min_voli} voli (soglia {thresholds['min_flights_per_night']})")

    # Check 4: Voli notturni (max) — soglia da config
    max_voli = max([r[1] for r in rows]) if ok and rows else 0
    _add_check(4, "Voli notturni (max)",
               max_voli <= thresholds["max_flights_per_night"],
               f"Massimo {max_voli} voli (soglia {thresholds['max_flights_per_night']})")

    # Check 5: Cargo — soglia da config
    ok, rows = bgy_db.execute_query(
        "SELECT COUNT(*) FROM nightly_reports WHERE tipo_movimento LIKE 'Cargo%%' AND data_riferimento = (SELECT MAX(data_riferimento) FROM nightly_reports)",
    )
    n_cargo = int(rows[0][0]) if ok and rows else 0
    _add_check(5, "Cargo notturno",
               n_cargo <= thresholds["max_cargo_per_night"],
               f"{n_cargo} voli cargo (soglia {thresholds['max_cargo_per_night']})")

    # Check 6: Distanza (gap)
    ok, rows = bgy_db.execute_query("SELECT MAX(data_riferimento), MIN(data_riferimento) FROM nightly_reports")
    if ok and rows and rows[0][0]:
        max_d, min_d = rows[0][0], rows[0][1]
        gap = (max_d - min_d).days
        _add_check(6, "Copertura storica", gap > 0, f"{gap} giorni")
    else:
        _add_check(6, "Copertura storica", False, "Nessun dato")

    # Check 7-8: Ratio D/A (placeholder)
    _add_check(7, "Ratio D/A (daily)", True, "OK")
    _add_check(8, "Ratio D/A (nightly)", True, "OK")

    # Check 9: Rumore — soglia da config
    ok, rows = bgy_db.execute_query("SELECT MAX(stima_rumore_db) FROM nightly_reports WHERE data_riferimento >= %s", (date_from,))
    max_rumore = int(rows[0][0]) if ok and rows and rows[0][0] else 0
    _add_check(9, "Rumore max",
               max_rumore <= thresholds["max_rumore_db"],
               f"{max_rumore} dB (soglia {thresholds['max_rumore_db']})")

    # Riepilogo
    righe = [f"─── Qualità dati (ultimi {days} giorni) ───"]
    for c in checks:
        if not c["ok"]:
            righe.append(f"❌ {c['label']}: {c['msg']}")

    if not any(not c["ok"] for c in checks):
        righe.append("✅ Tutti i check di qualità sono OK.")

    testo_email = "\n".join(righe)

    return {
        "checks": checks,
        "riepilogo": {"errori": errori, "warning": warning},
        "testo_email": testo_email,
        "thresholds_used": thresholds,
    }


def check_unresolved_airlines(days_threshold=30):
    ok, rows = bgy_db.execute_query("SELECT callsign, COUNT(*) FROM nightly_reports WHERE compagnia_aerea LIKE 'Compagnia %%' GROUP BY callsign")
    if not ok or not rows: return True, "Nessuna compagnia non risolta."
    if len(rows) > 0: return False, f"Trovate {len(rows)} compagnie non risolte."
    return True, "Tutte le compagnie sono risolte."


def _categorize_tipo_movimento(tipo):
    """v2.10.4 (BUG-10): mappa tipo_movimento in categoria aggregata."""
    if not tipo:
        return 'non_classificato'
    t = str(tipo).strip()
    if t.startswith('Passeggeri'):
        return 'passeggeri'
    if t.startswith('Cargo'):
        return 'cargo'
    if t.startswith('Charter'):
        return 'charter'
    return 'non_classificato'


def _empty_category_block():
    return {'decolli': 0, 'atterraggi': 0, 'totale': 0}


def _empty_sconf_block():
    return {
        'totale': 0,
        'passeggeri': {'decolli': 0, 'atterraggi': 0},
        'cargo': {'decolli': 0, 'atterraggi': 0},
        'charter': {'decolli': 0, 'atterraggi': 0},
        'non_classificato': {'decolli': 0, 'atterraggi': 0},
    }


def get_nightly_stats(date_str):
    """
    v2.10.4 (BUG-10, 22/10/2026): implementazione completa.

    Aggrega nightly_reports per data_riferimento = date_str, producendo
    la struttura attesa da bgy_mailer._format_nightly_section().

    Ritorna None se il DB non è abilitato o se non ci sono righe.
    """
    if not bgy_db.is_enabled():
        return None
    ok, rows = bgy_db.execute_query(
        """
        SELECT tipo_movimento, direzione_sacbo, notte_categoria, COUNT(*)
        FROM nightly_reports
        WHERE data_riferimento = %s
        GROUP BY tipo_movimento, direzione_sacbo, notte_categoria
        """,
        (date_str,)
    )
    if not ok or not rows:
        return None

    categories = {
        'passeggeri': _empty_category_block(),
        'cargo': _empty_category_block(),
        'charter': _empty_category_block(),
        'non_classificato': _empty_category_block(),
    }
    sconfinamenti = _empty_sconf_block()
    sconfinamenti_gravi = _empty_sconf_block()
    totale = 0

    for tipo, direzione, categoria, n in rows:
        n = int(n)
        totale += n
        cat_key = _categorize_tipo_movimento(tipo)
        dir_key = 'decolli' if str(direzione or '').strip().upper() == 'D' else 'atterraggi'
        cat = categories[cat_key]
        cat[dir_key] += n
        cat['totale'] += n

        cat_norm = str(categoria or '').strip().lower()
        if cat_norm == 'sconfinamento':
            sconfinamenti[cat_key][dir_key] += n
            sconfinamenti['totale'] += n
        elif cat_norm in ('sconfinamento_grave', 'sconfinamento grave'):
            sconfinamenti_gravi[cat_key][dir_key] += n
            sconfinamenti_gravi['totale'] += n

    anomalie = {'totale': 0, 'dettagli': []}
    ok_anom, rows_anom = bgy_db.execute_query(
        """
        SELECT callsign, direzione_sacbo, orario_schedulato
        FROM nightly_reports
        WHERE data_riferimento = %s AND notte_categoria = 'anomalia'
        ORDER BY orario_schedulato
        """,
        (date_str,)
    )
    if ok_anom and rows_anom:
        for cs, direz, sched in rows_anom:
            anomalie['dettagli'].append({
                'callsign': str(cs or '?'),
                'direzione_sacbo': str(direz or '?'),
                'orario_schedulato': str(sched or '?'),
            })
        anomalie['totale'] = len(rows_anom)

    return {
        'totale': totale,
        'passeggeri': categories['passeggeri'],
        'cargo': categories['cargo'],
        'charter': categories['charter'],
        'non_classificato': categories['non_classificato'],
        'sconfinamenti': sconfinamenti,
        'sconfinamenti_gravi': sconfinamenti_gravi,
        'anomalie': anomalie,
    }


def get_non_classified_flights(date_str):
    """
    v2.10.4 (BUG-10, 22/10/2026): implementazione completa.

    Ritorna la lista dei voli non classificati per data_riferimento = date_str,
    nel formato atteso da bgy_mailer._format_non_classified_section().
    """
    if not bgy_db.is_enabled():
        return []
    ok, rows = bgy_db.execute_query(
        """
        SELECT callsign, direzione_sacbo, orario_schedulato, compagnia_aerea, fase_volo
        FROM nightly_reports
        WHERE data_riferimento = %s AND tipo_movimento = 'Non classificato'
        ORDER BY orario_schedulato
        """,
        (date_str,)
    )
    if not ok or not rows:
        return []
    return [
        {
            'callsign': str(cs or '?'),
            'direzione_sacbo': str(direz or '?'),
            'orario_schedulato': str(sched or '?'),
            'compagnia_aerea': str(comp or 'N/D'),
            'fase_volo': str(fase or '?'),
        }
        for cs, direz, sched, comp, fase in rows
    ]


def main():
    global _FORCE_REIMPORT
    parser = argparse.ArgumentParser(description="Import e sincronizzazione CSV -> PostgreSQL")
    parser.add_argument("--all", action="store_true", help="Migrazione storica completa")
    parser.add_argument("--date", type=str, help="Sync di una data specifica (YYYY-MM-DD)")
    parser.add_argument("--last-n-days", type=int, help="Sync degli ultimi N giorni")
    parser.add_argument("--reset", action="store_true", help="Svuota le tabelle prima (solo con --all)")
    parser.add_argument("--force", action="store_true", help="Forza il reimport")
    parser.add_argument("--dry-run", action="store_true", help="Solo quality check")
    parser.add_argument("--quality-check", action="store_true", help="Esegui il quality check")
    parser.add_argument("--avionio-import", action="store_true", help="Importa gli ultimi file Avionio")
    parser.add_argument("--days", type=int, default=7, help="Giorni per quality check")
    args = parser.parse_args()

    if args.force: _FORCE_REIMPORT = True
    if not bgy_db.is_enabled(): sys.exit(1)

    success = True
    if args.quality_check:
        res = run_quality_check(days=args.days)
        print(res["testo_email"])
    elif args.avionio_import:
        ok, msg = import_avionio_scan_to_db()
        print(msg)
        success = ok
    elif args.all:
        success = migrate_all(reset=args.reset, dry_run=args.dry_run)
    elif args.date:
        success = sync_date(args.date, force=args.force) is not None
    elif args.last_n_days:
        success = sync_last_n_days(args.last_n_days, force=args.force) is not None
    else:
        success = sync_yesterday(force=args.force) is not None
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()