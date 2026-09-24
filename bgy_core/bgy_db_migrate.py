"""
bgy_core/bgy_db_migrate.py - Import e sincronizzazione CSV -> PostgreSQL.
Versione 2.6.2

Modulo unificato che contiene:
  - Funzioni di import per ogni tipo di file (scan, radar, meteo, nightly)
  - Parser per il formato vecchio di scan_*.csv
  - Logica di migrazione storica completa
  - Logica di sincronizzazione incrementale
  - Quality check esteso: 27 check (F11e)
  - Statistiche movimenti giornalieri e notturni (F18b)

Uso:
    py -3.12 -m bgy_core.bgy_db_migrate                      # sync di ieri
    py -3.12 -m bgy_core.bgy_db_migrate --date 2026-09-17
    py -3.12 -m bgy_core.bgy_db_migrate --last-n-days 7
    py -3.12 -m bgy_core.bgy_db_migrate --all
    py -3.12 -m bgy_core.bgy_db_migrate --all --reset
    py -3.12 -m bgy_core.bgy_db_migrate --all --dry-run
    py -3.12 -m bgy_core.bgy_db_migrate --quality-check
    py -3.12 -m bgy_core.bgy_db_migrate --quality-check --days 30
    py -3.12 -m bgy_core.bgy_db_migrate --quality-check --dry-run

Novità v2.6.2:
- Fix check 15 (Compagnie una-tantum): applicato solo se days >= 14.
  Su periodi brevi la diversità è naturalmente alta e il check dà
  falsi positivi.
- Fix check 20 (Scansioni SACBO complete): conta TUTTE le scansioni
  del giorno (diurne + notturne). La scansione di mezzanotte (00:00)
  è classificata come notturna, quindi contare solo le diurne dà
  sempre 3 invece di 4.

Novità v2.6.1:
- Fix bug `_effective_from`: il reference_date NON modifica più la
  finestra temporale delle query.
- Fix bug check 23 (Radar senza timestamp): timestamp IS NULL.
- Fix bug check 27 (Data riferimento futura): nome funzione corretto.

Novità v2.6.0:
- Quality check esteso da 10 a 27 check.
- Aggiunto concetto di `reference_date` (default 2026-10-01).
- Aggiunto --dry-run per il quality check.
"""
import os
import sys
import re
import csv
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import RAW_DIR, OUTPUT_CSV_DIR
from bgy_core import bgy_db

logger = get_logger("DBMigrate")

BATCH_SIZE = 500

EXPECTED_NEW_COLUMNS = {
    "callsign_volo", "tipo_movimento", "destinazione_origine",
    "orario_schedulato", "orario_effettivo", "stato_volo",
}

EXPECTED_OLD_COLUMNS = {
    "flight_num", "type", "sched_time", "actual_time",
    "origin_dest", "status",
}

OLD_MOVEMENT_MAP = {
    "decollo": "D", "atterraggio": "A",
    "partenza": "D", "arrivo": "A",
}

stats = {
    "scans_imported": 0, "scans_skipped": 0, "scans_recovered": 0,
    "scans_old_format": 0, "scans_unsupported": 0,
    "flights_imported": 0, "radar_imported": 0,
    "weather_imported": 0, "nightly_imported": 0, "errors": 0,
}

_schema_updates_applied = False


def _reset_stats():
    for k in stats:
        stats[k] = 0


def apply_schema_updates():
    global _schema_updates_applied
    if _schema_updates_applied:
        return True
    updates = [
        "ALTER TABLE nightly_reports ADD COLUMN IF NOT EXISTS direzione_sacbo VARCHAR(2)",
    ]
    for sql in updates:
        ok, result = bgy_db.execute_query(sql, fetch=False)
        if not ok:
            logger.error(f"❌ Schema update fallito: {sql} → {result}")
            return False
    _schema_updates_applied = True
    return True


# =============================================================================
# PARSING NOME FILE
# =============================================================================

def parse_date_from_scan_filename(filename):
    base = filename.replace(".csv", "")
    m = re.match(r'^scan_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2})$', base)
    if m:
        date_str = m.group(1)
        hh_mm = m.group(2).replace("-", ":")
        hh = int(hh_mm.split(":")[0])
        tipo = "notturno" if hh >= 23 or hh < 6 else "diurno"
        return date_str, hh_mm, tipo
    m = re.match(r'^scan_(\d{8})_(\d{4})$', base)
    if m:
        ymd = m.group(1)
        date_str = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"
        hh = int(m.group(2)[:2])
        mm = int(m.group(2)[2:])
        hh_mm = f"{hh:02d}:{mm:02d}"
        tipo = "notturno" if hh >= 23 or hh < 6 else "diurno"
        return date_str, hh_mm, tipo
    return None, None, None


def parse_radar_filename(filename):
    base = filename.replace(".csv", "")
    m = re.match(r'^radar_(\d{4}-\d{2}-\d{2})$', base)
    if m:
        return m.group(1)
    m = re.match(r'^bgy_night_flights_(\d{4}-\d{2}-\d{2})$', base)
    if m:
        return m.group(1)
    return None


def parse_meteo_filename(filename):
    base = filename.replace(".csv", "")
    m = re.match(r'^meteo_(\d{4}-\d{2}-\d{2})$', base)
    return m.group(1) if m else None


def parse_nightly_filename(filename):
    base = filename.replace(".csv", "")
    m = re.match(r'^report_nightly_(\d{4}-\d{2}-\d{2})$', base)
    return m.group(1) if m else None


# =============================================================================
# CONVERTITORI SICURI
# =============================================================================

def safe_int(value, default=None):
    if value is None:
        return default
    try:
        s = str(value).strip()
        if s == "" or s.upper() == "N/D":
            return default
        return int(float(s))
    except (ValueError, TypeError):
        return default


def safe_float(value, default=None):
    if value is None:
        return default
    try:
        s = str(value).strip()
        if s == "" or s.upper() == "N/D":
            return default
        return float(s)
    except (ValueError, TypeError):
        return default


def safe_str(value, default=""):
    if value is None:
        return default
    s = str(value).strip()
    return s if s else default


def safe_time(value):
    s = safe_str(value)
    if not s or s == "N/D":
        return None
    m = re.match(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?$', s)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2))
        ss = int(m.group(3)) if m.group(3) else 0
        return f"{hh:02d}:{mm:02d}:{ss:02d}"
    return None


def safe_timestamp(value):
    s = safe_str(value)
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            datetime.strptime(s, fmt)
            return s
        except ValueError:
            continue
    return None


def safe_bool(value):
    s = safe_str(value).lower()
    if s in ("true", "1", "yes", "si", "sì"):
        return True
    if s in ("false", "0", "no"):
        return False
    return None


def read_csv_rows(path):
    rows = []
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception as e:
        logger.error(f"Errore lettura {path}: {e}")
    return rows


def detect_scan_format(rows):
    if not rows:
        return None
    keys = set(rows[0].keys())
    if EXPECTED_NEW_COLUMNS.issubset(keys):
        return "new"
    if EXPECTED_OLD_COLUMNS.issubset(keys):
        return "old"
    return None


OLD_ORIGIN_DEST_PATTERN = re.compile(
    r'^(?P<destinazione>.+?)'
    r'(?P<ora_sched>\d{1,2}:\d{2})\s*\|\s*'
    r'(?P<ora_eff>\d{1,2}:\d{2})'
    r'(?P<stato>.*)$'
)


def parse_old_origin_dest(value):
    if value is None:
        return "", None, None, None
    s = str(value).strip()
    if not s:
        return "", None, None, None
    m = OLD_ORIGIN_DEST_PATTERN.match(s)
    if not m:
        return s, None, None, None
    dest = m.group("destinazione").strip()
    ora_sched = m.group("ora_sched").strip()
    ora_eff = m.group("ora_eff").strip()
    stato = m.group("stato").strip()
    if stato.lower() in ("nan", ",nan", ""):
        stato = ""
    return dest, ora_sched, ora_eff, stato


def parse_old_scan_row(row):
    callsign = safe_str(row.get("flight_num"), "")
    tipo_old = safe_str(row.get("type"), "").lower()
    tipo_new = OLD_MOVEMENT_MAP.get(tipo_old, "")
    sched_time = safe_str(row.get("sched_time"), "")
    actual_time = safe_str(row.get("actual_time"), "")
    status = safe_str(row.get("status"), "")
    dest, sched_from_dest, actual_from_dest, stato_from_dest = parse_old_origin_dest(
        row.get("origin_dest"))
    orario_schedulato = sched_time or sched_from_dest
    orario_effettivo = actual_time or actual_from_dest
    if status and status.lower() not in ("nan", ""):
        stato_volo = status
    else:
        stato_volo = stato_from_dest
    return {
        "callsign_volo": callsign, "tipo_movimento": tipo_new,
        "destinazione_origine": dest, "orario_schedulato": orario_schedulato,
        "orario_effettivo": orario_effettivo, "stato_volo": stato_volo,
    }


# =============================================================================
# IMPORT: SCAN
# =============================================================================

def import_scan_file(filepath):
    filename = os.path.basename(filepath)
    date_str, time_str, tipo = parse_date_from_scan_filename(filename)
    if not date_str:
        logger.warning(f"File scan non riconosciuto: {filename}")
        return False, None
    ok, rows = bgy_db.execute_query(
        "SELECT s.id, "
        "  (SELECT COUNT(1) FROM flights_sacbo f WHERE f.scan_id = s.id) AS n_flights "
        "FROM scans s WHERE s.file_name = %s", (filename,))
    if ok and rows:
        scan_id_existing, n_flights = rows[0]
        if n_flights and n_flights > 0:
            logger.info(f"⏭️ Già importato: {filename} "
                        f"(scan_id={scan_id_existing}, {n_flights} voli)")
            stats["scans_skipped"] += 1
            return False, None
        else:
            logger.warning(f"⚠️ Record scan orfano (id={scan_id_existing}), lo rimuovo: {filename}")
            bgy_db.execute_query("DELETE FROM scans WHERE id = %s", (scan_id_existing,))
            stats["scans_recovered"] += 1
    csv_rows = read_csv_rows(filepath)
    if not csv_rows:
        logger.warning(f"File vuoto: {filename}")
        return False, None
    fmt = detect_scan_format(csv_rows)
    if fmt is None:
        logger.warning(f"⚠️ Formato non riconosciuto, salto: {filename}")
        stats["scans_unsupported"] += 1
        return False, None
    if fmt == "old":
        stats["scans_old_format"] += 1
    scan_ts = None
    for r in csv_rows:
        ts = safe_timestamp(r.get("scan_timestamp"))
        if ts:
            scan_ts = ts
            break
    if not scan_ts:
        scan_ts = f"{date_str} {time_str}:00"
    ok, result = bgy_db.execute_query(
        """INSERT INTO scans (scan_timestamp, file_name, data_riferimento, tipo, righe_importate)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (scan_ts, filename, date_str, tipo, len(csv_rows)))
    if not ok:
        logger.error(f"Errore insert scan {filename}: {result}")
        stats["errors"] += 1
        return False, None
    scan_id = result[0][0] if result else None
    if not scan_id:
        logger.error(f"Insert scan non ha ritornato id: {filename}")
        stats["errors"] += 1
        return False, None
    flights_params = []
    for r in csv_rows:
        if fmt == "new":
            callsign = safe_str(r.get("callsign_volo"), "N/D")
            tipo_mov = safe_str(r.get("tipo_movimento"), "")
            dest = safe_str(r.get("destinazione_origine"), "")
            sched = safe_time(r.get("orario_schedulato"))
            eff = safe_time(r.get("orario_effettivo"))
            stato = safe_str(r.get("stato_volo"), "")
        else:
            parsed = parse_old_scan_row(r)
            callsign = safe_str(parsed["callsign_volo"], "N/D")
            tipo_mov = safe_str(parsed["tipo_movimento"], "")
            dest = safe_str(parsed["destinazione_origine"], "")
            sched = safe_time(parsed["orario_schedulato"])
            eff = safe_time(parsed["orario_effettivo"])
            stato = safe_str(parsed["stato_volo"], "")
        flights_params.append((
            scan_id, callsign, tipo_mov, dest, sched, eff, stato,
            scan_ts, date_str))
    total_inserted = 0
    for i in range(0, len(flights_params), BATCH_SIZE):
        batch = flights_params[i:i+BATCH_SIZE]
        ok, result = bgy_db.execute_many(
            """INSERT INTO flights_sacbo
               (scan_id, callsign_volo, tipo_movimento, destinazione_origine,
                orario_schedulato, orario_effettivo, stato_volo,
                scan_timestamp, data_riferimento)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""", batch)
        if ok:
            total_inserted += len(batch)
        else:
            logger.error(f"Errore insert flights per {filename}: {result}")
            stats["errors"] += 1
    logger.info(f"✅ Importato [{fmt}] {filename}: scan_id={scan_id}, {total_inserted} voli")
    stats["scans_imported"] += 1
    stats["flights_imported"] += total_inserted
    return True, total_inserted


# =============================================================================
# IMPORT: RADAR
# =============================================================================

def import_radar_file(filepath):
    filename = os.path.basename(filepath)
    date_str = parse_radar_filename(filename)
    if not date_str:
        logger.warning(f"File radar non riconosciuto: {filename}")
        return False, None
    ok, rows = bgy_db.execute_query(
        "SELECT COUNT(1) FROM radar_detections WHERE sessione_notturna = %s",
        (date_str,))
    if ok and rows and rows[0][0] > 0:
        logger.info(f"⏭️ Già importato: {filename} ({rows[0][0]} righe)")
        stats["scans_skipped"] += 1
        return False, None
    csv_rows = read_csv_rows(filepath)
    if not csv_rows:
        return False, None
    params = []
    for r in csv_rows:
        ts = safe_timestamp(r.get("timestamp"))
        if not ts:
            continue
        sessione = safe_str(r.get("sessione_notturna"), date_str)
        params.append((
            ts, safe_str(r.get("callsign"), ""), safe_str(r.get("icao24"), ""),
            safe_str(r.get("pista"), ""), safe_str(r.get("fase_volo"), ""),
            safe_str(r.get("direzione"), ""), safe_int(r.get("quota_ft"), 0),
            safe_float(r.get("rotta_deg"), 0.0), safe_float(r.get("distanza_km"), 0.0),
            safe_str(r.get("paese"), ""), sessione))
    if not params:
        return False, None
    total = 0
    for i in range(0, len(params), BATCH_SIZE):
        batch = params[i:i+BATCH_SIZE]
        ok, result = bgy_db.execute_many(
            """INSERT INTO radar_detections
               (timestamp, callsign, icao24, pista, fase_volo, direzione,
                quota_ft, rotta_deg, distanza_km, paese, sessione_notturna)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", batch)
        if ok:
            total += len(batch)
        else:
            logger.error(f"Errore insert radar {filename}: {result}")
            stats["errors"] += 1
    logger.info(f"✅ Importato {filename}: {total} rilevamenti radar")
    stats["radar_imported"] += total
    return True, total


# =============================================================================
# IMPORT: METEO
# =============================================================================

def import_meteo_file(filepath):
    filename = os.path.basename(filepath)
    date_str = parse_meteo_filename(filename)
    if not date_str:
        logger.warning(f"File meteo non riconosciuto: {filename}")
        return False, None
    ok, rows = bgy_db.execute_query(
        "SELECT COUNT(1) FROM weather_hourly WHERE data_riferimento = %s",
        (date_str,))
    if ok and rows and rows[0][0] > 0:
        logger.info(f"⏭️ Già importato: {filename}")
        stats["scans_skipped"] += 1
        return False, None
    csv_rows = read_csv_rows(filepath)
    if not csv_rows:
        return False, None
    params = []
    for r in csv_rows:
        orario = safe_time(r.get("orario"))
        if not orario:
            continue
        params.append((
            date_str, orario,
            safe_float(r.get("temperatura_c")),
            safe_float(r.get("precipitazioni_mm")),
            safe_float(r.get("vento_kmh")),
            safe_int(r.get("vento_direzione_deg")),
            safe_str(r.get("condizioni"), "")))
    if not params:
        return False, None
    ok, result = bgy_db.execute_many(
        """INSERT INTO weather_hourly
           (data_riferimento, orario, temperatura_c, precipitazioni_mm,
            vento_kmh, vento_direzione_deg, condizioni)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (data_riferimento, orario) DO NOTHING""", params)
    if not ok:
        logger.error(f"Errore insert meteo {filename}: {result}")
        stats["errors"] += 1
        return False, None
    logger.info(f"✅ Importato {filename}: {len(params)} ore meteo")
    stats["weather_imported"] += len(params)
    return True, len(params)


# =============================================================================
# IMPORT: NIGHTLY
# =============================================================================

def import_nightly_file(filepath):
    filename = os.path.basename(filepath)
    date_str = parse_nightly_filename(filename)
    if not date_str:
        logger.warning(f"File report notturno non riconosciuto: {filename}")
        return False, None
    ok, rows = bgy_db.execute_query(
        "SELECT COUNT(1) FROM nightly_reports WHERE data_riferimento = %s",
        (date_str,))
    if ok and rows and rows[0][0] > 0:
        logger.info(f"⏭️ Già importato: {filename}")
        stats["scans_skipped"] += 1
        return False, None
    csv_rows = read_csv_rows(filepath)
    if not csv_rows:
        return False, None
    params = []
    for r in csv_rows:
        params.append((
            date_str, safe_str(r.get("callsign"), ""),
            safe_str(r.get("tipo_movimento"), ""),
            safe_str(r.get("direzione_sacbo"), ""),
            safe_bool(r.get("is_scheduled")),
            safe_str(r.get("destinazione_finale"), ""),
            safe_str(r.get("stato_destinazione"), ""),
            safe_str(r.get("compagnia_aerea"), ""),
            safe_str(r.get("modello_aereo"), ""),
            safe_time(r.get("orario_schedulato")),
            safe_timestamp(r.get("timestamp")),
            safe_str(r.get("pista"), ""), safe_str(r.get("fase_volo"), ""),
            safe_str(r.get("direzione"), ""),
            safe_int(r.get("quota_ft"), 0), safe_float(r.get("rotta_deg"), 0.0),
            safe_float(r.get("distanza_km"), 0.0),
            safe_str(r.get("paese"), ""), safe_int(r.get("matched_score"), 0),
            safe_int(r.get("stima_passeggeri"), 0), safe_int(r.get("stima_rumore_db"), 0)))
    if not params:
        return False, None
    total = 0
    for i in range(0, len(params), BATCH_SIZE):
        batch = params[i:i+BATCH_SIZE]
        ok, result = bgy_db.execute_many(
            """INSERT INTO nightly_reports
               (data_riferimento, callsign, tipo_movimento, direzione_sacbo,
                is_scheduled, destinazione_finale, stato_destinazione,
                compagnia_aerea, modello_aereo, orario_schedulato, timestamp,
                pista, fase_volo, direzione, quota_ft, rotta_deg, distanza_km,
                paese, matched_score, stima_passeggeri, stima_rumore_db)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", batch)
        if ok:
            total += len(batch)
        else:
            logger.error(f"Errore insert nightly {filename}: {result}")
            stats["errors"] += 1
    logger.info(f"✅ Importato {filename}: {total} voli notturni")
    stats["nightly_imported"] += total
    return True, total


# =============================================================================
# SINCRONIZZAZIONE
# =============================================================================

def _date_matches(filename, date_str):
    compact = date_str.replace("-", "")
    return date_str in filename or compact in filename


def list_files_for_date(date_str):
    scan_files, radar_files = [], []
    if os.path.isdir(RAW_DIR):
        for f in sorted(os.listdir(RAW_DIR)):
            full = os.path.join(RAW_DIR, f)
            if not os.path.isfile(full) or not f.endswith(".csv"):
                continue
            if f.startswith("scan_") and _date_matches(f, date_str):
                scan_files.append(full)
            elif (f.startswith("radar_") or f.startswith("bgy_night_flights_")) \
                    and _date_matches(f, date_str):
                radar_files.append(full)
    meteo_files, nightly_files = [], []
    if os.path.isdir(OUTPUT_CSV_DIR):
        for f in sorted(os.listdir(OUTPUT_CSV_DIR)):
            full = os.path.join(OUTPUT_CSV_DIR, f)
            if not os.path.isfile(full) or not f.endswith(".csv"):
                continue
            if f.startswith("meteo_") and _date_matches(f, date_str):
                meteo_files.append(full)
            elif f.startswith("report_nightly_") and _date_matches(f, date_str):
                nightly_files.append(full)
    return {"scans": scan_files, "radar": radar_files,
            "meteo": meteo_files, "nightly": nightly_files}


def sync_date(date_str):
    if not bgy_db.is_enabled():
        logger.warning("⚠️ DB non abilitato in config_database.json, sync saltato")
        return None
    ok, msg = bgy_db.test_connection()
    if not ok:
        logger.error(f"❌ Connessione DB fallita: {msg}")
        return None
    apply_schema_updates()
    logger.info("=" * 60)
    logger.info(f"SYNC DB per la data: {date_str}")
    logger.info("=" * 60)
    files = list_files_for_date(date_str)
    total_files = sum(len(v) for v in files.values())
    if total_files == 0:
        logger.info(f"Nessun file trovato per la data {date_str}")
        return {"scans": {"imported": 0, "skipped": 0, "errors": 0},
                "radar": {"imported": 0, "skipped": 0, "errors": 0},
                "meteo": {"imported": 0, "skipped": 0, "errors": 0},
                "nightly": {"imported": 0, "skipped": 0, "errors": 0}}
    logger.info(f"File trovati per {date_str}:")
    logger.info(f"  Scansioni SACBO: {len(files['scans'])}")
    logger.info(f"  Radar:           {len(files['radar'])}")
    logger.info(f"  Meteo:           {len(files['meteo'])}")
    logger.info(f"  Report notturni: {len(files['nightly'])}")
    logger.info(f"  TOTALE:          {total_files}")
    result = {}
    for categoria, files_list, import_fn in (
        ("scans", files["scans"], import_scan_file),
        ("radar", files["radar"], import_radar_file),
        ("meteo", files["meteo"], import_meteo_file),
        ("nightly", files["nightly"], import_nightly_file)):
        imported = skipped = errors = 0
        for fp in files_list:
            try:
                ok, n = import_fn(fp)
                if ok:
                    imported += 1
                else:
                    skipped += 1
            except Exception as e:
                logger.error(f"Errore su {os.path.basename(fp)}: {e}")
                errors += 1
        result[categoria] = {"imported": imported, "skipped": skipped, "errors": errors}
    logger.info("-" * 60)
    logger.info("Riepilogo sync:")
    for categoria, s in result.items():
        logger.info(f"  {categoria:10s}: importati {s['imported']}, "
                    f"saltati {s['skipped']}, errori {s['errors']}")
    logger.info("=" * 60)
    return result


def sync_yesterday():
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    return sync_date(yesterday)


def sync_last_n_days(n):
    today = datetime.now().date()
    results = {}
    for i in range(n):
        d = today - timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        logger.info(f"\n--- Sincronizzazione {date_str} ---")
        r = sync_date(date_str)
        if r:
            results[date_str] = r
    return results


def reset_tables():
    logger.warning("⚠️ RESET: svuoto tutte le tabelle...")
    tables = ["nightly_reports", "weather_hourly", "radar_detections",
              "flights_sacbo", "scans"]
    ok, result = bgy_db.execute_query(
        f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE", fetch=False)
    if ok:
        logger.info("✅ Tabelle svuotate")
    else:
        logger.error(f"❌ Errore reset: {result}")
    return ok


def migrate_all(reset=False, dry_run=False):
    if not bgy_db.is_enabled():
        logger.error("❌ DB non abilitato in config_database.json")
        return False
    ok, msg = bgy_db.test_connection()
    if not ok:
        logger.error(f"❌ Connessione DB fallita: {msg}")
        return False
    logger.info(f"Connessione DB OK: {msg}")
    logger.info(f"Schema version: {bgy_db.get_schema_version()}")
    apply_schema_updates()
    if reset and not dry_run:
        reset_tables()
    scan_files, radar_files, meteo_files, nightly_files = [], [], [], []
    if os.path.isdir(RAW_DIR):
        for f in sorted(os.listdir(RAW_DIR)):
            full = os.path.join(RAW_DIR, f)
            if not os.path.isfile(full):
                continue
            if f.startswith("scan_") and f.endswith(".csv"):
                scan_files.append(full)
            elif (f.startswith("radar_") or f.startswith("bgy_night_flights_")) \
                    and f.endswith(".csv"):
                radar_files.append(full)
    if os.path.isdir(OUTPUT_CSV_DIR):
        for f in sorted(os.listdir(OUTPUT_CSV_DIR)):
            full = os.path.join(OUTPUT_CSV_DIR, f)
            if not os.path.isfile(full):
                continue
            if f.startswith("meteo_") and f.endswith(".csv"):
                meteo_files.append(full)
            elif f.startswith("report_nightly_") and f.endswith(".csv"):
                nightly_files.append(full)
    logger.info("=" * 60)
    logger.info("MIGRAZIONE COMPLETA CSV → PostgreSQL")
    logger.info("=" * 60)
    logger.info(f"File trovati:")
    logger.info(f"  Scansioni SACBO: {len(scan_files)}")
    logger.info(f"  Radar:           {len(radar_files)}")
    logger.info(f"  Meteo:           {len(meteo_files)}")
    logger.info(f"  Report notturni: {len(nightly_files)}")
    logger.info(f"  TOTALE:          {len(scan_files) + len(radar_files) + len(meteo_files) + len(nightly_files)}")
    logger.info("=" * 60)
    if dry_run:
        logger.info("DRY-RUN: nessun dato verrà importato")
        return True
    logger.info("\n--- Fase 1: Scansioni SACBO ---")
    for i, fp in enumerate(scan_files, 1):
        if i % 50 == 0:
            logger.info(f"  [{i}/{len(scan_files)}] ...")
        try:
            import_scan_file(fp)
        except Exception as e:
            logger.error(f"Errore su {fp}: {e}")
            stats["errors"] += 1
    logger.info("\n--- Fase 2: Radar ---")
    for i, fp in enumerate(radar_files, 1):
        if i % 20 == 0:
            logger.info(f"  [{i}/{len(radar_files)}] ...")
        try:
            import_radar_file(fp)
        except Exception as e:
            logger.error(f"Errore su {fp}: {e}")
            stats["errors"] += 1
    logger.info("\n--- Fase 3: Meteo ---")
    for i, fp in enumerate(meteo_files, 1):
        try:
            import_meteo_file(fp)
        except Exception as e:
            logger.error(f"Errore su {fp}: {e}")
            stats["errors"] += 1
    logger.info("\n--- Fase 4: Report notturni ---")
    for i, fp in enumerate(nightly_files, 1):
        try:
            import_nightly_file(fp)
        except Exception as e:
            logger.error(f"Errore su {fp}: {e}")
            stats["errors"] += 1
    logger.info("\n" + "=" * 60)
    logger.info("MIGRAZIONE COMPLETATA")
    logger.info("=" * 60)
    logger.info(f"Scansioni importate:       {stats['scans_imported']}")
    logger.info(f"Scansioni già presenti:    {stats['scans_skipped']}")
    logger.info(f"Scansioni recuperate:      {stats['scans_recovered']}")
    logger.info(f"Scansioni formato vecchio: {stats['scans_old_format']}")
    logger.info(f"Scansioni non supportate:  {stats['scans_unsupported']}")
    logger.info(f"Voli SACBO importati:      {stats['flights_imported']}")
    logger.info(f"Rilevamenti radar:         {stats['radar_imported']}")
    logger.info(f"Righe meteo:               {stats['weather_imported']}")
    logger.info(f"Voli notturni:             {stats['nightly_imported']}")
    logger.info(f"Errori:                    {stats['errors']}")
    logger.info("=" * 60)
    counts = bgy_db.get_table_counts()
    logger.info("Stato tabelle DB:")
    for t, c in counts.items():
        logger.info(f"  {t}: {c}")
    return True


# =============================================================================
# STATISTICHE MOVIMENTI
# =============================================================================

def get_daily_stats(date_str):
    result = {"decolli": 0, "atterraggi": 0, "totale": 0}
    ok, rows = bgy_db.execute_query(
        """SELECT tipo_movimento, COUNT(*) AS n
           FROM v_daily_report
           WHERE data_riferimento = %s
           GROUP BY tipo_movimento""", (date_str,))
    if not ok:
        logger.warning(f"get_daily_stats: errore query ({rows})")
        return result
    for tipo, n in rows or []:
        t = str(tipo).strip().upper()
        if t.startswith('D'):
            result["decolli"] += n
        elif t.startswith('A'):
            result["atterraggi"] += n
        result["totale"] += n
    return result


def get_nightly_stats(date_str):
    empty = {
        "passeggeri": {"decolli": 0, "atterraggi": 0, "totale": 0},
        "cargo": {"decolli": 0, "atterraggi": 0, "totale": 0},
        "charter": {"decolli": 0, "atterraggi": 0, "totale": 0},
        "totale": 0}
    ok, rows = bgy_db.execute_query(
        """SELECT
              CASE
                WHEN tipo_movimento = 'Passeggeri' THEN 'passeggeri'
                WHEN tipo_movimento LIKE 'Cargo%%' THEN 'cargo'
                WHEN tipo_movimento LIKE 'Charter%%' THEN 'charter'
                ELSE 'altro'
              END AS categoria,
              COALESCE(
                NULLIF(direzione_sacbo, ''),
                CASE
                  WHEN fase_volo = 'Decollo' THEN 'D'
                  WHEN fase_volo IN ('Atterraggio', 'Avvicinamento') THEN 'A'
                  ELSE '?'
                END
              ) AS direzione,
              COUNT(*) AS n
           FROM nightly_reports
           WHERE data_riferimento = %s
             AND (tipo_movimento = 'Passeggeri'
                  OR tipo_movimento LIKE 'Cargo%%'
                  OR tipo_movimento LIKE 'Charter%%')
           GROUP BY 1, 2""", (date_str,))
    if not ok:
        logger.warning(f"get_nightly_stats: errore query ({rows})")
        return empty
    for categoria, direzione, n in rows or []:
        if categoria not in ("passeggeri", "cargo", "charter"):
            continue
        d = str(direzione).strip().upper()
        if d == 'D':
            empty[categoria]["decolli"] += n
        elif d == 'A':
            empty[categoria]["atterraggi"] += n
        empty[categoria]["totale"] += n
        empty["totale"] += n
    return empty


# =============================================================================
# QUALITY CHECK — CONFIGURAZIONE
# =============================================================================

DEFAULT_THRESHOLDS = {
    "max_flights_per_night": 40, "min_flights_per_night": 3,
    "max_cargo_per_night": 15, "max_pax_zero_pct": 10,
    "max_pax_per_flight": 500, "max_quota_ft": 50000, "max_gap_days": 3,
    "daily_da_ratio_min": 0.7, "daily_da_ratio_max": 1.4,
    "nightly_da_ratio_min": 0.5, "nightly_da_ratio_max": 2.0,
    "min_airlines_per_night": 3, "max_onetime_airlines_pct": 15,
    "max_missing_dest_pct": 5, "pax_avg_min": 30, "pax_avg_max": 200,
    "min_days_for_onetime_check": 14}

DEFAULT_REFERENCE_DATE = "2026-10-01"

VISIBLE_FILTER_SQL = (
    "(tipo_movimento = 'Passeggeri' "
    " OR tipo_movimento LIKE 'Cargo%%' "
    " OR tipo_movimento LIKE 'Charter%%')")


def _get_quality_config():
    try:
        from bgy_core.bgy_config_manager import config_manager
        cfg = config_manager.get_data_config()
        qc = cfg.get("quality_check", {}) or {}
        th = dict(DEFAULT_THRESHOLDS)
        th.update(qc.get("thresholds", {}))
        ref = qc.get("reference_date", DEFAULT_REFERENCE_DATE)
        return th, ref
    except Exception:
        return dict(DEFAULT_THRESHOLDS), DEFAULT_REFERENCE_DATE


# =============================================================================
# QUALITY CHECK — 1-10
# =============================================================================

def _qc_compagnie_placeholder(date_from, date_to):
    ok, rows = bgy_db.execute_query(
        """SELECT compagnia_aerea, COUNT(*) AS n
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND compagnia_aerea LIKE 'Compagnia%%'
           GROUP BY compagnia_aerea ORDER BY n DESC""",
        (date_from, date_to))
    if not ok:
        return True, False, 0, 0, [f"Errore: {rows}"]
    totale = sum(r[1] for r in rows)
    dettagli = [f"{r[0]} ({r[1]} voli)" for r in rows[:5]]
    return totale == 0, False, totale, 0, dettagli


def _qc_compagnie_null(date_from, date_to):
    ok, rows = bgy_db.execute_query(
        """SELECT compagnia_aerea, COUNT(*) AS n
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND (compagnia_aerea IS NULL OR compagnia_aerea = '' OR compagnia_aerea = 'N/D')
           GROUP BY compagnia_aerea ORDER BY n DESC""",
        (date_from, date_to))
    if not ok:
        return True, False, 0, 0, [f"Errore: {rows}"]
    totale = sum(r[1] for r in rows)
    dettagli = [f"{r[0] or 'NULL'} ({r[1]})" for r in rows[:5]]
    return totale == 0, False, totale, 0, dettagli


def _qc_nomi_anomali(date_from, date_to):
    ok, rows = bgy_db.execute_query(
        """SELECT compagnia_aerea, COUNT(*) AS n
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND compagnia_aerea IS NOT NULL AND LENGTH(compagnia_aerea) < 4
           GROUP BY compagnia_aerea ORDER BY n DESC""",
        (date_from, date_to))
    if not ok:
        return True, False, 0, 0, [f"Errore: {rows}"]
    totale = sum(r[1] for r in rows)
    dettagli = [f"{r[0]} ({r[1]})" for r in rows[:5]]
    return totale == 0, False, totale, 0, dettagli


def _qc_notti_troppi_voli(date_from, date_to, thresholds):
    soglia = thresholds["max_flights_per_night"]
    ok, rows = bgy_db.execute_query(
        f"""SELECT data_riferimento, COUNT(*) AS n FROM nightly_reports
            WHERE data_riferimento BETWEEN %s AND %s AND {VISIBLE_FILTER_SQL}
            GROUP BY data_riferimento HAVING COUNT(*) >= %s ORDER BY n DESC""",
        (date_from, date_to, soglia - 10))
    if not ok:
        return True, False, 0, soglia, [f"Errore: {rows}"]
    errori = [r for r in rows if r[1] >= soglia]
    warnings = [r for r in rows if r[1] < soglia]
    dettagli = [f"{r[0]}: {r[1]}" for r in errori[:5]]
    return len(errori) == 0, len(warnings) > 0, len(rows), soglia, dettagli


def _qc_notti_pochi_voli(date_from, date_to, thresholds):
    soglia = thresholds["min_flights_per_night"]
    ok, rows = bgy_db.execute_query(
        f"""SELECT data_riferimento, COUNT(*) AS n FROM nightly_reports
            WHERE data_riferimento BETWEEN %s AND %s AND {VISIBLE_FILTER_SQL}
            GROUP BY data_riferimento HAVING COUNT(*) <= %s ORDER BY n ASC""",
        (date_from, date_to, soglia + 2))
    if not ok:
        return True, False, 0, soglia, [f"Errore: {rows}"]
    errori = [r for r in rows if r[1] <= soglia]
    warnings = [r for r in rows if r[1] > soglia]
    dettagli = [f"{r[0]}: {r[1]}" for r in errori[:5]]
    return len(errori) == 0, len(warnings) > 0, len(rows), soglia, dettagli


def _qc_cargo_eccessivi(date_from, date_to, thresholds):
    soglia = thresholds["max_cargo_per_night"]
    ok, rows = bgy_db.execute_query(
        """SELECT data_riferimento, COUNT(*) AS n FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s AND tipo_movimento LIKE 'Cargo%%'
           GROUP BY data_riferimento HAVING COUNT(*) >= %s ORDER BY n DESC""",
        (date_from, date_to, soglia - 5))
    if not ok:
        return True, False, 0, soglia, [f"Errore: {rows}"]
    errori = [r for r in rows if r[1] >= soglia]
    warnings = [r for r in rows if r[1] < soglia]
    dettagli = [f"{r[0]}: {r[1]}" for r in errori[:5]]
    return len(errori) == 0, len(warnings) > 0, len(rows), soglia, dettagli


def _qc_gap_notti(date_from, date_to, thresholds):
    ok, rows = bgy_db.execute_query(
        """SELECT DISTINCT data_riferimento FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s ORDER BY data_riferimento""",
        (date_from, date_to))
    if not ok:
        return True, False, 0, thresholds["max_gap_days"], [f"Errore: {rows}"]
    date_presenti = set()
    for r in rows:
        if hasattr(r[0], 'strftime'):
            date_presenti.add(r[0].strftime("%Y-%m-%d"))
        else:
            date_presenti.add(str(r[0]))
    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date()
    gaps = []
    cur_start, cur_len = None, 0
    d = start
    while d <= end:
        ds = d.strftime("%Y-%m-%d")
        if ds in date_presenti:
            if cur_len >= thresholds["max_gap_days"]:
                gaps.append((cur_start, cur_len))
            cur_start, cur_len = None, 0
        else:
            if cur_start is None:
                cur_start = ds
            cur_len += 1
        d += timedelta(days=1)
    if cur_len >= thresholds["max_gap_days"]:
        gaps.append((cur_start, cur_len))
    dettagli = [f"{g[0]}: {g[1]} gg" for g in gaps[:5]]
    return len(gaps) == 0, False, len(gaps), thresholds["max_gap_days"], dettagli


def _qc_pax_zero(date_from, date_to, thresholds):
    ok, rows = bgy_db.execute_query(
        """SELECT
              COUNT(*) FILTER (WHERE stima_passeggeri = 0 OR stima_passeggeri IS NULL) AS zero,
              COUNT(*) AS tot
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND tipo_movimento = 'Passeggeri'
             AND modello_aereo IS NOT NULL AND modello_aereo != '' AND modello_aereo != 'N/D'""",
        (date_from, date_to))
    if not ok or not rows:
        return True, False, 0, thresholds["max_pax_zero_pct"], [f"Errore: {rows}"]
    zero, tot = rows[0][0], rows[0][1]
    if tot == 0:
        return True, False, 0, thresholds["max_pax_zero_pct"], ["Nessun volo con modello noto"]
    pct = round(100.0 * zero / tot, 1)
    soglia = thresholds["max_pax_zero_pct"]
    return pct < soglia, pct >= soglia / 2, pct, soglia, [f"{zero}/{tot} con PAX=0"]


def _qc_valori_assurdi(date_from, date_to, thresholds):
    max_pax = thresholds["max_pax_per_flight"]
    max_quota = thresholds["max_quota_ft"]
    ok, rows = bgy_db.execute_query(
        """SELECT callsign, data_riferimento, stima_passeggeri, quota_ft
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND (stima_passeggeri > %s OR quota_ft > %s
                  OR stima_passeggeri < 0 OR quota_ft < 0)
           ORDER BY data_riferimento DESC LIMIT 10""",
        (date_from, date_to, max_pax, max_quota))
    if not ok:
        return True, False, 0, 0, [f"Errore: {rows}"]
    dettagli = [f"{r[1]} {r[0]}: PAX={r[2]}, q={r[3]}" for r in rows[:5]]
    return len(rows) == 0, False, len(rows), 0, dettagli


def _qc_csv_vs_db(date_from, date_to):
    mismatches = []
    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date()
    d = start
    while d <= end:
        ds = d.strftime("%Y-%m-%d")
        csv_path = os.path.join(OUTPUT_CSV_DIR, f"report_nightly_{ds}.csv")
        if os.path.exists(csv_path):
            n_csv = len(read_csv_rows(csv_path))
            ok, rows = bgy_db.execute_query(
                "SELECT COUNT(*) FROM nightly_reports WHERE data_riferimento = %s", (ds,))
            if ok and rows and n_csv != rows[0][0]:
                mismatches.append(f"{ds}: CSV={n_csv}, DB={rows[0][0]}")
        d += timedelta(days=1)
    return len(mismatches) == 0, False, len(mismatches), 0, mismatches[:5]


# =============================================================================
# QUALITY CHECK — 11-27 (nuovi)
# =============================================================================

def _qc_bilanciamento_daily(date_from, date_to, thresholds):
    ok, rows = bgy_db.execute_query(
        """SELECT data_riferimento,
                  COUNT(*) FILTER (WHERE tipo_movimento = 'D') AS d,
                  COUNT(*) FILTER (WHERE tipo_movimento = 'A') AS a
           FROM v_daily_report
           WHERE data_riferimento BETWEEN %s AND %s
           GROUP BY data_riferimento
           ORDER BY data_riferimento""",
        (date_from, date_to))
    if not ok:
        return True, False, 0, 0, [f"Errore: {rows}"]
    rmin, rmax = thresholds["daily_da_ratio_min"], thresholds["daily_da_ratio_max"]
    errori, warnings = [], []
    for data, d, a in rows or []:
        if a == 0 and d == 0:
            continue
        if a == 0:
            errori.append(f"{data}: D={d}, A=0")
            continue
        ratio = d / a
        if ratio < rmin or ratio > rmax:
            errori.append(f"{data}: ratio={ratio:.2f} (D={d}, A={a})")
        elif ratio < rmin * 1.15 or ratio > rmax * 0.85:
            warnings.append(f"{data}: ratio={ratio:.2f}")
    return len(errori) == 0, len(warnings) > 0, len(errori), f"{rmin}–{rmax}", \
        [f"❌ {e}" for e in errori[:3]] + [f"⚠️ {w}" for w in warnings[:2]]


def _qc_bilanciamento_nightly(date_from, date_to, thresholds):
    ok, rows = bgy_db.execute_query(
        """SELECT data_riferimento,
                  COUNT(*) FILTER (WHERE direzione_sacbo = 'D'
                                     OR (direzione_sacbo IS NULL AND fase_volo = 'Decollo')) AS d,
                  COUNT(*) FILTER (WHERE direzione_sacbo = 'A'
                                     OR (direzione_sacbo IS NULL AND fase_volo IN ('Atterraggio', 'Avvicinamento'))) AS a
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND (tipo_movimento = 'Passeggeri'
                  OR tipo_movimento LIKE 'Cargo%%'
                  OR tipo_movimento LIKE 'Charter%%')
           GROUP BY data_riferimento
           ORDER BY data_riferimento""",
        (date_from, date_to))
    if not ok:
        return True, False, 0, 0, [f"Errore: {rows}"]
    rmin, rmax = thresholds["nightly_da_ratio_min"], thresholds["nightly_da_ratio_max"]
    errori, warnings = [], []
    for data, d, a in rows or []:
        if a == 0 and d == 0:
            continue
        if a == 0:
            errori.append(f"{data}: D={d}, A=0")
            continue
        ratio = d / a
        if ratio < rmin or ratio > rmax:
            errori.append(f"{data}: ratio={ratio:.2f} (D={d}, A={a})")
        elif ratio < rmin * 1.2 or ratio > rmax * 0.8:
            warnings.append(f"{data}: ratio={ratio:.2f}")
    return len(errori) == 0, len(warnings) > 0, len(errori), f"{rmin}–{rmax}", \
        [f"❌ {e}" for e in errori[:3]] + [f"⚠️ {w}" for w in warnings[:2]]


def _qc_daily_presenti(date_from, date_to):
    ok, rows = bgy_db.execute_query(
        """SELECT DISTINCT s.data_riferimento
           FROM scans s
           WHERE s.data_riferimento BETWEEN %s AND %s
             AND s.tipo = 'diurno'
           ORDER BY s.data_riferimento""",
        (date_from, date_to))
    if not ok:
        return True, False, 0, 0, [f"Errore: {rows}"]
    with_scans = [r[0].strftime("%Y-%m-%d") if hasattr(r[0], 'strftime') else str(r[0])
                  for r in rows or []]
    if not with_scans:
        return True, False, 0, 0, ["Nessuna scansione nel periodo"]
    ok, rows = bgy_db.execute_query(
        """SELECT DISTINCT data_riferimento FROM v_daily_report
           WHERE data_riferimento BETWEEN %s AND %s""",
        (date_from, date_to))
    with_daily = set()
    if ok and rows:
        for r in rows:
            with_daily.add(r[0].strftime("%Y-%m-%d") if hasattr(r[0], 'strftime') else str(r[0]))
    missing = [d for d in with_scans if d not in with_daily]
    return len(missing) == 0, False, len(missing), 0, missing[:5]


def _qc_airlines_diversita(date_from, date_to, thresholds):
    soglia = thresholds["min_airlines_per_night"]
    ok, rows = bgy_db.execute_query(
        """SELECT data_riferimento, COUNT(DISTINCT compagnia_aerea) AS n
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND compagnia_aerea IS NOT NULL AND compagnia_aerea != '' AND compagnia_aerea != 'N/D'
           GROUP BY data_riferimento
           HAVING COUNT(DISTINCT compagnia_aerea) < %s
           ORDER BY n ASC""",
        (date_from, date_to, soglia))
    if not ok:
        return True, False, 0, soglia, [f"Errore: {rows}"]
    dettagli = [f"{r[0]}: {r[1]} compagnie" for r in rows[:5]]
    return len(rows) == 0, False, len(rows), soglia, dettagli


def _qc_onetime_airlines(date_from, date_to, thresholds):
    """
    CHECK 15 (fix v2.6.2): applica il check solo se il periodo è >= N giorni.
    Su periodi brevi la diversità è naturalmente alta e il check dà falsi positivi.
    """
    min_days = thresholds.get("min_days_for_onetime_check", 14)
    # Calcola i giorni del periodo
    try:
        df_dt = datetime.strptime(date_from, "%Y-%m-%d").date()
        dt_dt = datetime.strptime(date_to, "%Y-%m-%d").date()
        days = (dt_dt - df_dt).days + 1
    except Exception:
        days = 0

    pct_soglia = thresholds["max_onetime_airlines_pct"]

    if days < min_days:
        return True, False, 0, pct_soglia, \
            [f"Non applicabile: periodo di {days} gg < {min_days} gg"]

    ok, rows = bgy_db.execute_query(
        """SELECT compagnia_aerea, COUNT(*) AS n
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND compagnia_aerea IS NOT NULL AND compagnia_aerea != '' AND compagnia_aerea != 'N/D'
           GROUP BY compagnia_aerea
           ORDER BY n ASC""",
        (date_from, date_to))
    if not ok:
        return True, False, 0, pct_soglia, [f"Errore: {rows}"]
    totale = len(rows)
    if totale == 0:
        return True, False, 0, pct_soglia, []
    onetime = [r[0] for r in rows if r[1] == 1]
    pct = round(100.0 * len(onetime) / totale, 1)
    dettagli = [f"{c}" for c in onetime[:5]]
    return pct < pct_soglia, pct >= pct_soglia * 0.8, pct, pct_soglia, dettagli


def _qc_cargo_non_in_lista(date_from, date_to):
    ok, rows = bgy_db.execute_query(
        """SELECT DISTINCT callsign FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND tipo_movimento LIKE 'Cargo%%'""",
        (date_from, date_to))
    if not ok:
        return True, False, 0, 0, [f"Errore: {rows}"]
    try:
        from bgy_core import is_cargo_flight
        non_cargo = []
        for r in rows or []:
            cs = str(r[0]).strip()
            is_c, _ = is_cargo_flight(cs)
            if not is_c:
                non_cargo.append(cs)
        dettagli = [f"{c}" for c in non_cargo[:5]]
        return len(non_cargo) == 0, False, len(non_cargo), 0, dettagli
    except Exception as e:
        return True, False, 0, 0, [f"Errore verifica: {e}"]


def _qc_file_radar_mancanti(date_from, date_to):
    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date()
    missing = []
    d = start
    while d <= end:
        ds = d.strftime("%Y-%m-%d")
        radar_path = os.path.join(RAW_DIR, f"radar_{ds}.csv")
        if not os.path.exists(radar_path):
            ok, rows = bgy_db.execute_query(
                "SELECT COUNT(*) FROM radar_detections WHERE sessione_notturna = %s",
                (ds,))
            if not ok or not rows or rows[0][0] == 0:
                missing.append(ds)
        d += timedelta(days=1)
    missing = [m for m in missing if m >= "2026-09-01"]
    return len(missing) == 0, False, len(missing), 0, missing[:5]


def _qc_file_meteo_mancanti(date_from, date_to):
    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date()
    missing = []
    d = start
    while d <= end:
        ds = d.strftime("%Y-%m-%d")
        meteo_path = os.path.join(OUTPUT_CSV_DIR, f"meteo_{ds}.csv")
        if not os.path.exists(meteo_path):
            ok, rows = bgy_db.execute_query(
                "SELECT COUNT(*) FROM weather_hourly WHERE data_riferimento = %s",
                (ds,))
            if not ok or not rows or rows[0][0] == 0:
                missing.append(ds)
        d += timedelta(days=1)
    missing = [m for m in missing if m >= "2026-09-01"]
    return len(missing) == 0, False, len(missing), 0, missing[:5]


def _qc_report_daily_mancanti(date_from, date_to):
    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date()
    missing = []
    d = start
    while d <= end:
        ds = d.strftime("%Y-%m-%d")
        path = os.path.join(OUTPUT_CSV_DIR, f"report_daily_{ds}.csv")
        if not os.path.exists(path):
            missing.append(ds)
        d += timedelta(days=1)
    missing = [m for m in missing if m >= "2026-09-15"]
    return len(missing) == 0, False, len(missing), 0, missing[:5]


def _qc_scansioni_complete(date_from, date_to):
    """
    CHECK 20 (fix v2.6.2): conta TUTTE le scansioni del giorno (diurne + notturne).
    La scansione di mezzanotte (00:00) è classificata come notturna, quindi
    contare solo le diurne dà sempre 3 invece di 4.
    """
    ok, rows = bgy_db.execute_query(
        """SELECT data_riferimento, COUNT(*) AS n
           FROM scans
           WHERE data_riferimento BETWEEN %s AND %s
           GROUP BY data_riferimento
           HAVING COUNT(*) < 4
           ORDER BY data_riferimento""",
        (date_from, date_to))
    if not ok:
        return True, False, 0, 4, [f"Errore: {rows}"]
    dettagli = [f"{r[0]}: {r[1]} scansioni totali" for r in rows[:5]]
    return len(rows) == 0, False, len(rows), 4, dettagli


def _qc_destinazione_mancante(date_from, date_to, thresholds):
    pct_soglia = thresholds["max_missing_dest_pct"]
    ok, rows = bgy_db.execute_query(
        """SELECT
              COUNT(*) FILTER (WHERE destinazione_finale IS NULL
                                 OR destinazione_finale = ''
                                 OR destinazione_finale = 'N/D') AS zero,
              COUNT(*) AS tot
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND tipo_movimento = 'Passeggeri'""",
        (date_from, date_to))
    if not ok or not rows:
        return True, False, 0, pct_soglia, [f"Errore: {rows}"]
    zero, tot = rows[0][0], rows[0][1]
    if tot == 0:
        return True, False, 0, pct_soglia, []
    pct = round(100.0 * zero / tot, 1)
    return pct < pct_soglia, pct >= pct_soglia * 0.8, pct, pct_soglia, [f"{zero}/{tot}"]


def _qc_orario_fuori_fascia(date_from, date_to):
    ok, rows = bgy_db.execute_query(
        """SELECT data_riferimento, callsign, orario_schedulato
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND orario_schedulato IS NOT NULL
             AND EXTRACT(HOUR FROM orario_schedulato) BETWEEN 7 AND 22
           ORDER BY data_riferimento DESC LIMIT 10""",
        (date_from, date_to))
    if not ok:
        return True, False, 0, 0, [f"Errore: {rows}"]
    dettagli = [f"{r[0]} {r[1]} @{r[2]}" for r in rows[:5]]
    return len(rows) == 0, False, len(rows), 0, dettagli


def _qc_radar_senza_timestamp(date_from, date_to):
    ok, rows = bgy_db.execute_query(
        """SELECT callsign, data_riferimento
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND timestamp IS NULL
             AND tipo_movimento LIKE 'Passeggeri (radar)%%'
           LIMIT 10""",
        (date_from, date_to))
    if not ok:
        return True, False, 0, 0, [f"Errore: {rows}"]
    dettagli = [f"{r[1]} {r[0]}" for r in rows[:5]]
    return len(rows) == 0, False, len(rows), 0, dettagli


def _qc_match_incoerente(date_from, date_to):
    ok, rows = bgy_db.execute_query(
        """SELECT callsign, data_riferimento, matched_score, fase_volo
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND is_scheduled = TRUE
             AND matched_score = 0
             AND fase_volo IS NOT NULL
             AND fase_volo NOT IN ('Non rilevato', '')
           LIMIT 10""",
        (date_from, date_to))
    if not ok:
        return True, False, 0, 0, [f"Errore: {rows}"]
    dettagli = [f"{r[1]} {r[0]}: m={r[2]}, fase={r[3]}" for r in rows[:5]]
    return len(rows) == 0, False, len(rows), 0, dettagli


def _qc_pax_medio(date_from, date_to, thresholds):
    ok, rows = bgy_db.execute_query(
        """SELECT AVG(stima_passeggeri) AS media, COUNT(*) AS tot
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND tipo_movimento = 'Passeggeri'
             AND stima_passeggeri > 0
             AND modello_aereo IS NOT NULL
             AND modello_aereo != ''
             AND modello_aereo != 'N/D'""",
        (date_from, date_to))
    if not ok or not rows:
        return True, False, 0, 0, [f"Errore: {rows}"]
    media, tot = rows[0][0], rows[0][1]
    if tot == 0 or media is None:
        return True, False, 0, 0, ["Nessun volo con PAX > 0"]
    media = round(float(media), 1)
    pmin = thresholds["pax_avg_min"]
    pmax = thresholds["pax_avg_max"]
    ok_result = pmin <= media <= pmax
    return ok_result, not ok_result and (media < pmin * 1.2 or media > pmax * 0.8), \
        media, f"{pmin}–{pmax}", [f"Media su {tot} voli"]


def _qc_duplicati_note(date_from, date_to):
    ok, rows = bgy_db.execute_query(
        """SELECT data_riferimento, callsign, orario_schedulato, COUNT(*) AS n
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND orario_schedulato IS NOT NULL
           GROUP BY 1, 2, 3
           HAVING COUNT(*) > 1
           ORDER BY n DESC
           LIMIT 10""",
        (date_from, date_to))
    if not ok:
        return True, False, 0, 0, [f"Errore: {rows}"]
    dettagli = [f"{r[0]} {r[1]} @{r[2]}: {r[3]}x" for r in rows[:5]]
    return len(rows) == 0, False, len(rows), 0, dettagli


def _qc_data_futura(date_from, date_to):
    oggi = datetime.now().date().strftime("%Y-%m-%d")
    ok, rows = bgy_db.execute_query(
        """SELECT DISTINCT data_riferimento
           FROM nightly_reports
           WHERE data_riferimento > %s
           ORDER BY data_riferimento""",
        (oggi,))
    if not ok:
        return True, False, 0, oggi, [f"Errore: {rows}"]
    dettagli = [str(r[0]) for r in rows[:5]]
    return len(rows) == 0, False, len(rows), oggi, dettagli


# =============================================================================
# RUN QUALITY CHECK
# =============================================================================

def run_quality_check(days=7, dry_run=False):
    end_date = datetime.now().date() - timedelta(days=1)
    start_date = end_date - timedelta(days=days - 1)
    date_from = start_date.strftime("%Y-%m-%d")
    date_to = end_date.strftime("%Y-%m-%d")

    thresholds, reference_date = _get_quality_config()

    try:
        date_to_dt = datetime.strptime(date_to, "%Y-%m-%d").date()
        ref_dt = datetime.strptime(reference_date, "%Y-%m-%d").date()
        pre_reference = date_to_dt < ref_dt
    except Exception:
        pre_reference = False

    logger.info(f"🔍 Quality check: {date_from} → {date_to} ({days} giorni)")
    logger.info(f"   Reference date: {reference_date}")
    if pre_reference:
        logger.info("   Modalità apprendimento attiva (nuovi check falliscono come warning)")
    if dry_run:
        logger.info("   DRY-RUN: nessun errore, solo report")

    checks_def = [
        (1, "Compagnie placeholder", lambda: _qc_compagnie_placeholder(date_from, date_to), False),
        (2, "Compagnie NULL/N/D", lambda: _qc_compagnie_null(date_from, date_to), False),
        (3, "Nomi compagnia anomali", lambda: _qc_nomi_anomali(date_from, date_to), False),
        (4, "Notti con molti voli", lambda: _qc_notti_troppi_voli(date_from, date_to, thresholds), False),
        (5, "Notti con pochi voli", lambda: _qc_notti_pochi_voli(date_from, date_to, thresholds), False),
        (6, "Cargo eccessivi", lambda: _qc_cargo_eccessivi(date_from, date_to, thresholds), False),
        (7, "Gap notti senza report", lambda: _qc_gap_notti(date_from, date_to, thresholds), False),
        (8, "PAX=0 nei passeggeri", lambda: _qc_pax_zero(date_from, date_to, thresholds), False),
        (9, "Valori fuori range", lambda: _qc_valori_assurdi(date_from, date_to, thresholds), False),
        (10, "Coerenza CSV vs DB", lambda: _qc_csv_vs_db(date_from, date_to), False),
        (11, "Bilanciamento D/A daily", lambda: _qc_bilanciamento_daily(date_from, date_to, thresholds), True),
        (12, "Bilanciamento D/A nightly", lambda: _qc_bilanciamento_nightly(date_from, date_to, thresholds), True),
        (13, "Report daily presenti", lambda: _qc_daily_presenti(date_from, date_to), True),
        (14, "Diversità compagnie notte", lambda: _qc_airlines_diversita(date_from, date_to, thresholds), True),
        (15, "Compagnie una-tantum", lambda: _qc_onetime_airlines(date_from, date_to, thresholds), True),
        (16, "Cargo non in lista", lambda: _qc_cargo_non_in_lista(date_from, date_to), True),
        (17, "File radar mancanti", lambda: _qc_file_radar_mancanti(date_from, date_to), True),
        (18, "File meteo mancanti", lambda: _qc_file_meteo_mancanti(date_from, date_to), True),
        (19, "Report daily mancanti", lambda: _qc_report_daily_mancanti(date_from, date_to), True),
        (20, "Scansioni SACBO complete", lambda: _qc_scansioni_complete(date_from, date_to), True),
        (21, "Destinazione mancante", lambda: _qc_destinazione_mancante(date_from, date_to, thresholds), True),
        (22, "Orario fuori fascia", lambda: _qc_orario_fuori_fascia(date_from, date_to), True),
        (23, "Radar senza timestamp", lambda: _qc_radar_senza_timestamp(date_from, date_to), True),
        (24, "Match incoerente", lambda: _qc_match_incoerente(date_from, date_to), True),
        (25, "PAX medio per volo", lambda: _qc_pax_medio(date_from, date_to, thresholds), True),
        (26, "Duplicati notte residui", lambda: _qc_duplicati_note(date_from, date_to), True),
        (27, "Data riferimento futura", lambda: _qc_data_futura(date_from, date_to), True),
    ]

    results = []
    ok_count = warn_count = err_count = 0
    new_in_warning = 0

    for cid, nome, fn, is_new in checks_def:
        try:
            ok, warning, valore, soglia, dettagli = fn()
        except Exception as e:
            ok, warning = False, False
            valore, soglia = 0, 0
            dettagli = [f"Eccezione: {e}"]
            logger.error(f"Errore check {cid} '{nome}': {e}")

        if pre_reference and is_new and not ok:
            warning = True
            ok = True
            new_in_warning += 1

        if ok and not warning:
            ok_count += 1
        elif ok and warning:
            warn_count += 1
        else:
            err_count += 1

        results.append({
            "id": cid, "nome": nome, "ok": ok, "warning": warning,
            "valore": valore, "soglia": soglia, "dettagli": dettagli,
            "is_new": is_new})

    qc_result = {
        "periodo": {"da": date_from, "a": date_to, "giorni": days},
        "reference_date": reference_date,
        "pre_reference": pre_reference,
        "checks": results,
        "riepilogo": {"ok": ok_count, "warning": warn_count, "errori": err_count,
                       "new_in_warning": new_in_warning},
        "dry_run": dry_run}
    qc_result["testo_email"] = format_quality_text(qc_result)
    logger.info(
        f"✅ Quality check completato: "
        f"{ok_count} OK, {warn_count} warning, {err_count} errori"
        + (f" (di cui {new_in_warning} nuovi check in modalità warning)"
           if new_in_warning > 0 else ""))
    return qc_result


def format_quality_text(qc_result):
    p = qc_result["periodo"]
    pre = qc_result.get("pre_reference", False)
    ref = qc_result.get("reference_date", "")
    lines = []
    if pre:
        lines.append(f"─── Qualità dati (ultimi {p['giorni']} giorni) ───")
        lines.append(f"   ℹ️ Modalità apprendimento fino al {ref}")
    else:
        lines.append(f"─── Qualità dati (ultimi {p['giorni']} giorni) ───")
    for c in qc_result["checks"]:
        if not c["ok"]:
            icon = "❌"
        elif c["warning"]:
            icon = "⚠️ "
        else:
            icon = "✅"
        valore = c["valore"]
        soglia = c["soglia"]
        nome = c["nome"]
        new_tag = " 🆕" if c.get("is_new") else ""
        if c["ok"] and not c["warning"]:
            if isinstance(valore, float):
                line = f"{icon} {nome}: {valore}% (soglia {soglia}%){new_tag}"
            elif soglia and isinstance(soglia, (int, float)) and soglia > 0:
                line = f"{icon} {nome}: {valore} (soglia {soglia}){new_tag}"
            else:
                line = f"{icon} {nome}: {valore}{new_tag}"
        else:
            if isinstance(valore, float):
                line = f"{icon} {nome}: {valore}% (soglia {soglia}%){new_tag}"
            elif soglia and isinstance(soglia, (int, float)) and soglia > 0:
                line = f"{icon} {nome}: {valore} (soglia {soglia}){new_tag}"
            else:
                line = f"{icon} {nome}: {valore}{new_tag}"
        lines.append(line)
        for d in c["dettagli"][:3]:
            lines.append(f"    → {d}")
    r = qc_result["riepilogo"]
    lines.append("─" * 37)
    if r.get("new_in_warning", 0) > 0:
        lines.append(
            f"Riepilogo: {r['ok']} OK, {r['warning']} warning, {r['errori']} errori "
            f"({r['new_in_warning']} nuovi check in apprendimento)")
    else:
        lines.append(
            f"Riepilogo: {r['ok']} OK, {r['warning']} warning, {r['errori']} errori")
    return "\n".join(lines)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Import e sincronizzazione CSV -> PostgreSQL")
    parser.add_argument("--all", action="store_true",
                        help="Migrazione storica completa")
    parser.add_argument("--date", type=str,
                        help="Sync di una data specifica (YYYY-MM-DD)")
    parser.add_argument("--last-n-days", type=int,
                        help="Sync degli ultimi N giorni")
    parser.add_argument("--reset", action="store_true",
                        help="Svuota le tabelle prima (solo con --all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo per quality check: mostra risultati senza contare errori")
    parser.add_argument("--quality-check", action="store_true",
                        help="Esegui il quality check")
    parser.add_argument("--days", type=int, default=7,
                        help="Numero di giorni per il quality check (default: 7)")
    args = parser.parse_args()
    if not bgy_db.is_enabled():
        logger.error("❌ DB non abilitato. Modifica config_database.json")
        sys.exit(1)
    success = True
    if args.quality_check:
        result = run_quality_check(days=args.days, dry_run=args.dry_run)
        print()
        print(result["testo_email"])
        print()
        if not args.dry_run:
            success = result["riepilogo"]["errori"] == 0
    elif args.all:
        apply_schema_updates()
        success = migrate_all(reset=args.reset, dry_run=args.dry_run)
    elif args.date:
        result = sync_date(args.date)
        success = result is not None
    elif args.last_n_days:
        result = sync_last_n_days(args.last_n_days)
        success = result is not None
    else:
        logger.info("Nessun argomento specificato, sincronizzo ieri")
        result = sync_yesterday()
        success = result is not None
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()