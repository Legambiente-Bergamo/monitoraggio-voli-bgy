"""
bgy_core/bgy_db_migrate.py - Import e sincronizzazione CSV -> PostgreSQL.
Versione 2.5.8

Modulo unificato che contiene:
  - Funzioni di import per ogni tipo di file (scan, radar, meteo, nightly)
  - Parser per il formato vecchio di scan_*.csv (gennaio-luglio 2026)
  - Logica di migrazione storica completa (tutte le directory)
  - Logica di sincronizzazione incrementale (per data, per ultimi N giorni)
  - Quality check (F11e) sui dati degli ultimi N giorni
  - Statistiche movimenti giornalieri e notturni (F18b)

Uso:
    py -3.12 -m bgy_core.bgy_db_migrate                      # sync di ieri
    py -3.12 -m bgy_core.bgy_db_migrate --date 2026-09-17    # sync di una data
    py -3.12 -m bgy_core.bgy_db_migrate --last-n-days 7      # ultimi 7 giorni
    py -3.12 -m bgy_core.bgy_db_migrate --all                # migrazione completa
    py -3.12 -m bgy_core.bgy_db_migrate --all --reset        # reset + reimport
    py -3.12 -m bgy_core.bgy_db_migrate --all --dry-run      # analisi senza import
    py -3.12 -m bgy_core.bgy_db_migrate --quality-check      # quality check (7 gg)
    py -3.12 -m bgy_core.bgy_db_migrate --quality-check --days 30

Fix v2.5.8:
- Aggiunta colonna `direzione_sacbo` a nightly_reports (F18b).
- `apply_schema_updates()` applicato automaticamente prima di ogni sync.
- Nuove funzioni: `get_daily_stats()`, `get_nightly_stats()`.

Fix v2.5.6:
- CHECK 4 e 8 del quality check affinati.
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
    "decollo": "D",
    "atterraggio": "A",
    "partenza": "D",
    "arrivo": "A",
}

stats = {
    "scans_imported": 0,
    "scans_skipped": 0,
    "scans_recovered": 0,
    "scans_old_format": 0,
    "scans_unsupported": 0,
    "flights_imported": 0,
    "radar_imported": 0,
    "weather_imported": 0,
    "nightly_imported": 0,
    "errors": 0,
}

_schema_updates_applied = False


def _reset_stats():
    for k in stats:
        stats[k] = 0


# =============================================================================
# SCHEMA UPDATES (F12a, F18b)
# =============================================================================

def apply_schema_updates():
    """
    Applica modifiche incrementali allo schema esistente.
    Idempotente: usa IF NOT EXISTS / ADD COLUMN IF NOT EXISTS.
    """
    global _schema_updates_applied
    if _schema_updates_applied:
        return True

    updates = [
        # F18b: direzione_sacbo in nightly_reports
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


# =============================================================================
# RILEVAMENTO FORMATO
# =============================================================================

def detect_scan_format(rows):
    if not rows:
        return None
    keys = set(rows[0].keys())
    if EXPECTED_NEW_COLUMNS.issubset(keys):
        return "new"
    if EXPECTED_OLD_COLUMNS.issubset(keys):
        return "old"
    return None


# =============================================================================
# PARSER FORMATO VECCHIO
# =============================================================================

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
        "callsign_volo": callsign,
        "tipo_movimento": tipo_new,
        "destinazione_origine": dest,
        "orario_schedulato": orario_schedulato,
        "orario_effettivo": orario_effettivo,
        "stato_volo": stato_volo,
    }


# =============================================================================
# FUNZIONI DI IMPORT (singolo file)
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
        "FROM scans s WHERE s.file_name = %s",
        (filename,)
    )
    if ok and rows:
        scan_id_existing, n_flights = rows[0]
        if n_flights and n_flights > 0:
            logger.info(f"⏭️ Già importato: {filename} "
                        f"(scan_id={scan_id_existing}, {n_flights} voli)")
            stats["scans_skipped"] += 1
            return False, None
        else:
            logger.warning(f"⚠️ Record scan orfano (id={scan_id_existing}), "
                           f"lo rimuovo: {filename}")
            bgy_db.execute_query("DELETE FROM scans WHERE id = %s",
                                  (scan_id_existing,))
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
        (scan_ts, filename, date_str, tipo, len(csv_rows))
    )
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
            scan_ts, date_str,
        ))

    total_inserted = 0
    for i in range(0, len(flights_params), BATCH_SIZE):
        batch = flights_params[i:i+BATCH_SIZE]
        ok, result = bgy_db.execute_many(
            """INSERT INTO flights_sacbo
               (scan_id, callsign_volo, tipo_movimento, destinazione_origine,
                orario_schedulato, orario_effettivo, stato_volo,
                scan_timestamp, data_riferimento)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            batch
        )
        if ok:
            total_inserted += len(batch)
        else:
            logger.error(f"Errore insert flights per {filename}: {result}")
            stats["errors"] += 1

    logger.info(f"✅ Importato [{fmt}] {filename}: scan_id={scan_id}, {total_inserted} voli")
    stats["scans_imported"] += 1
    stats["flights_imported"] += total_inserted
    return True, total_inserted


def import_radar_file(filepath):
    filename = os.path.basename(filepath)
    date_str = parse_radar_filename(filename)
    if not date_str:
        logger.warning(f"File radar non riconosciuto: {filename}")
        return False, None

    ok, rows = bgy_db.execute_query(
        "SELECT COUNT(1) FROM radar_detections WHERE sessione_notturna = %s",
        (date_str,)
    )
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
            ts,
            safe_str(r.get("callsign"), ""),
            safe_str(r.get("icao24"), ""),
            safe_str(r.get("pista"), ""),
            safe_str(r.get("fase_volo"), ""),
            safe_str(r.get("direzione"), ""),
            safe_int(r.get("quota_ft"), 0),
            safe_float(r.get("rotta_deg"), 0.0),
            safe_float(r.get("distanza_km"), 0.0),
            safe_str(r.get("paese"), ""),
            sessione,
        ))

    if not params:
        return False, None

    total = 0
    for i in range(0, len(params), BATCH_SIZE):
        batch = params[i:i+BATCH_SIZE]
        ok, result = bgy_db.execute_many(
            """INSERT INTO radar_detections
               (timestamp, callsign, icao24, pista, fase_volo, direzione,
                quota_ft, rotta_deg, distanza_km, paese, sessione_notturna)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            batch
        )
        if ok:
            total += len(batch)
        else:
            logger.error(f"Errore insert radar {filename}: {result}")
            stats["errors"] += 1

    logger.info(f"✅ Importato {filename}: {total} rilevamenti radar")
    stats["radar_imported"] += total
    return True, total


def import_meteo_file(filepath):
    filename = os.path.basename(filepath)
    date_str = parse_meteo_filename(filename)
    if not date_str:
        logger.warning(f"File meteo non riconosciuto: {filename}")
        return False, None

    ok, rows = bgy_db.execute_query(
        "SELECT COUNT(1) FROM weather_hourly WHERE data_riferimento = %s",
        (date_str,)
    )
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
            date_str,
            orario,
            safe_float(r.get("temperatura_c")),
            safe_float(r.get("precipitazioni_mm")),
            safe_float(r.get("vento_kmh")),
            safe_int(r.get("vento_direzione_deg")),
            safe_str(r.get("condizioni"), ""),
        ))

    if not params:
        return False, None

    ok, result = bgy_db.execute_many(
        """INSERT INTO weather_hourly
           (data_riferimento, orario, temperatura_c, precipitazioni_mm,
            vento_kmh, vento_direzione_deg, condizioni)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (data_riferimento, orario) DO NOTHING""",
        params
    )
    if not ok:
        logger.error(f"Errore insert meteo {filename}: {result}")
        stats["errors"] += 1
        return False, None

    logger.info(f"✅ Importato {filename}: {len(params)} ore meteo")
    stats["weather_imported"] += len(params)
    return True, len(params)


def import_nightly_file(filepath):
    filename = os.path.basename(filepath)
    date_str = parse_nightly_filename(filename)
    if not date_str:
        logger.warning(f"File report notturno non riconosciuto: {filename}")
        return False, None

    ok, rows = bgy_db.execute_query(
        "SELECT COUNT(1) FROM nightly_reports WHERE data_riferimento = %s",
        (date_str,)
    )
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
            date_str,
            safe_str(r.get("callsign"), ""),
            safe_str(r.get("tipo_movimento"), ""),
            safe_str(r.get("direzione_sacbo"), ""),  # nuova colonna
            safe_bool(r.get("is_scheduled")),
            safe_str(r.get("destinazione_finale"), ""),
            safe_str(r.get("stato_destinazione"), ""),
            safe_str(r.get("compagnia_aerea"), ""),
            safe_str(r.get("modello_aereo"), ""),
            safe_time(r.get("orario_schedulato")),
            safe_timestamp(r.get("timestamp")),
            safe_str(r.get("pista"), ""),
            safe_str(r.get("fase_volo"), ""),
            safe_str(r.get("direzione"), ""),
            safe_int(r.get("quota_ft"), 0),
            safe_float(r.get("rotta_deg"), 0.0),
            safe_float(r.get("distanza_km"), 0.0),
            safe_str(r.get("paese"), ""),
            safe_int(r.get("matched_score"), 0),
            safe_int(r.get("stima_passeggeri"), 0),
            safe_int(r.get("stima_rumore_db"), 0),
        ))

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
                       %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            batch
        )
        if ok:
            total += len(batch)
        else:
            logger.error(f"Errore insert nightly {filename}: {result}")
            stats["errors"] += 1

    logger.info(f"✅ Importato {filename}: {total} voli notturni")
    stats["nightly_imported"] += total
    return True, total


# =============================================================================
# SINCRONIZZAZIONE INCREMENTALE
# =============================================================================

def _date_matches(filename, date_str):
    compact = date_str.replace("-", "")
    return date_str in filename or compact in filename


def list_files_for_date(date_str):
    scan_files = []
    radar_files = []

    if os.path.isdir(RAW_DIR):
        for f in sorted(os.listdir(RAW_DIR)):
            full = os.path.join(RAW_DIR, f)
            if not os.path.isfile(full):
                continue
            if not f.endswith(".csv"):
                continue
            if f.startswith("scan_") and _date_matches(f, date_str):
                scan_files.append(full)
            elif (f.startswith("radar_") or f.startswith("bgy_night_flights_")) \
                    and _date_matches(f, date_str):
                radar_files.append(full)

    meteo_files = []
    nightly_files = []

    if os.path.isdir(OUTPUT_CSV_DIR):
        for f in sorted(os.listdir(OUTPUT_CSV_DIR)):
            full = os.path.join(OUTPUT_CSV_DIR, f)
            if not os.path.isfile(full):
                continue
            if not f.endswith(".csv"):
                continue
            if f.startswith("meteo_") and _date_matches(f, date_str):
                meteo_files.append(full)
            elif f.startswith("report_nightly_") and _date_matches(f, date_str):
                nightly_files.append(full)

    return {
        "scans": scan_files,
        "radar": radar_files,
        "meteo": meteo_files,
        "nightly": nightly_files,
    }


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
        return {
            "scans": {"imported": 0, "skipped": 0, "errors": 0},
            "radar": {"imported": 0, "skipped": 0, "errors": 0},
            "meteo": {"imported": 0, "skipped": 0, "errors": 0},
            "nightly": {"imported": 0, "skipped": 0, "errors": 0},
        }

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
        ("nightly", files["nightly"], import_nightly_file),
    ):
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


# =============================================================================
# STATISTICHE MOVIMENTI (F18b)
# =============================================================================

def get_daily_stats(date_str):
    """
    Ritorna statistiche dei movimenti del giorno specificato.
    Output: {"decolli": N, "atterraggi": N, "totale": N}
    """
    result = {"decolli": 0, "atterraggi": 0, "totale": 0}
    ok, rows = bgy_db.execute_query(
        """SELECT tipo_movimento, COUNT(*) AS n
           FROM v_daily_report
           WHERE data_riferimento = %s
           GROUP BY tipo_movimento""",
        (date_str,)
    )
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
    """
    Ritorna statistiche dei movimenti notturni (solo Visibili):
    Passeggeri, Cargo, Charter, con split decolli/atterraggi.
    """
    empty = {
        "passeggeri": {"decolli": 0, "atterraggi": 0, "totale": 0},
        "cargo": {"decolli": 0, "atterraggi": 0, "totale": 0},
        "charter": {"decolli": 0, "atterraggi": 0, "totale": 0},
        "totale": 0,
    }

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
           GROUP BY 1, 2""",
        (date_str,)
    )
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
# QUALITY CHECK (F11e)
# =============================================================================

DEFAULT_THRESHOLDS = {
    "max_flights_per_night": 40,
    "min_flights_per_night": 3,
    "max_cargo_per_night": 15,
    "max_pax_zero_pct": 10,
    "max_pax_per_flight": 500,
    "max_quota_ft": 50000,
    "max_gap_days": 3,
}

VISIBLE_FILTER_SQL = (
    "(tipo_movimento = 'Passeggeri' "
    " OR tipo_movimento LIKE 'Cargo%%' "
    " OR tipo_movimento LIKE 'Charter%%')"
)


def _get_quality_thresholds():
    try:
        from bgy_core.bgy_config_manager import config_manager
        cfg = config_manager.get_data_config()
        qc = cfg.get("quality_check", {}).get("thresholds", {})
        result = dict(DEFAULT_THRESHOLDS)
        result.update(qc)
        return result
    except Exception:
        return dict(DEFAULT_THRESHOLDS)


def _qc_compagnie_placeholder(date_from, date_to):
    ok, rows = bgy_db.execute_query(
        """SELECT compagnia_aerea, COUNT(*) AS n
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND compagnia_aerea LIKE 'Compagnia%%'
           GROUP BY compagnia_aerea
           ORDER BY n DESC""",
        (date_from, date_to)
    )
    if not ok:
        return True, False, 0, 0, [f"Errore query: {rows}"]
    totale = sum(r[1] for r in rows)
    dettagli = [f"{r[0]} ({r[1]} voli)" for r in rows[:5]]
    return totale == 0, False, totale, 0, dettagli


def _qc_compagnie_null(date_from, date_to):
    ok, rows = bgy_db.execute_query(
        """SELECT compagnia_aerea, COUNT(*) AS n
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND (compagnia_aerea IS NULL
                  OR compagnia_aerea = ''
                  OR compagnia_aerea = 'N/D')
           GROUP BY compagnia_aerea
           ORDER BY n DESC""",
        (date_from, date_to)
    )
    if not ok:
        return True, False, 0, 0, [f"Errore query: {rows}"]
    totale = sum(r[1] for r in rows)
    dettagli = [f"{r[0] or 'NULL'} ({r[1]} voli)" for r in rows[:5]]
    return totale == 0, False, totale, 0, dettagli


def _qc_nomi_anomali(date_from, date_to):
    ok, rows = bgy_db.execute_query(
        """SELECT compagnia_aerea, COUNT(*) AS n
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND compagnia_aerea IS NOT NULL
             AND LENGTH(compagnia_aerea) < 4
           GROUP BY compagnia_aerea
           ORDER BY n DESC""",
        (date_from, date_to)
    )
    if not ok:
        return True, False, 0, 0, [f"Errore query: {rows}"]
    totale = sum(r[1] for r in rows)
    dettagli = [f"{r[0]} ({r[1]} voli)" for r in rows[:5]]
    return totale == 0, False, totale, 0, dettagli


def _qc_notti_troppi_voli(date_from, date_to, thresholds):
    soglia = thresholds["max_flights_per_night"]
    ok, rows = bgy_db.execute_query(
        f"""SELECT data_riferimento, COUNT(*) AS n
            FROM nightly_reports
            WHERE data_riferimento BETWEEN %s AND %s
              AND {VISIBLE_FILTER_SQL}
            GROUP BY data_riferimento
            HAVING COUNT(*) >= %s
            ORDER BY n DESC""",
        (date_from, date_to, soglia - 10)
    )
    if not ok:
        return True, False, 0, soglia, [f"Errore query: {rows}"]
    errori = [r for r in rows if r[1] >= soglia]
    warnings = [r for r in rows if r[1] < soglia]
    dettagli = [f"{r[0]}: {r[1]} voli visibili" for r in errori[:5]]
    return len(errori) == 0, len(warnings) > 0, len(rows), soglia, dettagli


def _qc_notti_pochi_voli(date_from, date_to, thresholds):
    soglia = thresholds["min_flights_per_night"]
    ok, rows = bgy_db.execute_query(
        f"""SELECT data_riferimento, COUNT(*) AS n
            FROM nightly_reports
            WHERE data_riferimento BETWEEN %s AND %s
              AND {VISIBLE_FILTER_SQL}
            GROUP BY data_riferimento
            HAVING COUNT(*) <= %s
            ORDER BY n ASC""",
        (date_from, date_to, soglia + 2)
    )
    if not ok:
        return True, False, 0, soglia, [f"Errore query: {rows}"]
    errori = [r for r in rows if r[1] <= soglia]
    warnings = [r for r in rows if r[1] > soglia]
    dettagli = [f"{r[0]}: {r[1]} voli visibili" for r in errori[:5]]
    return len(errori) == 0, len(warnings) > 0, len(rows), soglia, dettagli


def _qc_cargo_eccessivi(date_from, date_to, thresholds):
    soglia = thresholds["max_cargo_per_night"]
    ok, rows = bgy_db.execute_query(
        """SELECT data_riferimento, COUNT(*) AS n
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND tipo_movimento LIKE 'Cargo%%'
           GROUP BY data_riferimento
           HAVING COUNT(*) >= %s
           ORDER BY n DESC""",
        (date_from, date_to, soglia - 5)
    )
    if not ok:
        return True, False, 0, soglia, [f"Errore query: {rows}"]
    errori = [r for r in rows if r[1] >= soglia]
    warnings = [r for r in rows if r[1] < soglia]
    dettagli = [f"{r[0]}: {r[1]} cargo" for r in errori[:5]]
    return len(errori) == 0, len(warnings) > 0, len(rows), soglia, dettagli


def _qc_gap_notti(date_from, date_to, thresholds):
    ok, rows = bgy_db.execute_query(
        """SELECT DISTINCT data_riferimento
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
           ORDER BY data_riferimento""",
        (date_from, date_to)
    )
    if not ok:
        return True, False, 0, thresholds["max_gap_days"], [f"Errore query: {rows}"]

    date_presenti = set()
    for r in rows:
        if hasattr(r[0], 'strftime'):
            date_presenti.add(r[0].strftime("%Y-%m-%d"))
        else:
            date_presenti.add(str(r[0]))

    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date()

    gaps = []
    current_gap_start = None
    current_gap_len = 0
    d = start
    while d <= end:
        ds = d.strftime("%Y-%m-%d")
        if ds in date_presenti:
            if current_gap_len >= thresholds["max_gap_days"]:
                gaps.append((current_gap_start, current_gap_len))
            current_gap_start = None
            current_gap_len = 0
        else:
            if current_gap_start is None:
                current_gap_start = ds
            current_gap_len += 1
        d += timedelta(days=1)

    if current_gap_len >= thresholds["max_gap_days"]:
        gaps.append((current_gap_start, current_gap_len))

    dettagli = [f"{g[0]}: {g[1]} giorni senza report" for g in gaps[:5]]
    return len(gaps) == 0, False, len(gaps), thresholds["max_gap_days"], dettagli


def _qc_pax_zero(date_from, date_to, thresholds):
    ok, rows = bgy_db.execute_query(
        """SELECT
              COUNT(*) FILTER (WHERE stima_passeggeri = 0 OR stima_passeggeri IS NULL) AS zero,
              COUNT(*) AS tot
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND tipo_movimento = 'Passeggeri'
             AND modello_aereo IS NOT NULL
             AND modello_aereo != ''
             AND modello_aereo != 'N/D'""",
        (date_from, date_to)
    )
    if not ok or not rows:
        return True, False, 0, thresholds["max_pax_zero_pct"], [f"Errore query: {rows}"]
    zero, tot = rows[0][0], rows[0][1]
    if tot == 0:
        return True, False, 0, thresholds["max_pax_zero_pct"], ["Nessun volo con modello noto"]
    pct = round(100.0 * zero / tot, 1)
    soglia = thresholds["max_pax_zero_pct"]
    warning_soglia = soglia / 2
    dettagli = [f"{zero}/{tot} voli (con modello noto) con PAX=0"]
    return pct < soglia, pct >= warning_soglia, pct, soglia, dettagli


def _qc_valori_assurdi(date_from, date_to, thresholds):
    max_pax = thresholds["max_pax_per_flight"]
    max_quota = thresholds["max_quota_ft"]
    ok, rows = bgy_db.execute_query(
        """SELECT callsign, data_riferimento, stima_passeggeri, quota_ft
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND (
               stima_passeggeri > %s
               OR quota_ft > %s
               OR stima_passeggeri < 0
               OR quota_ft < 0
             )
           ORDER BY data_riferimento DESC
           LIMIT 10""",
        (date_from, date_to, max_pax, max_quota)
    )
    if not ok:
        return True, False, 0, 0, [f"Errore query: {rows}"]
    dettagli = []
    for r in rows[:5]:
        callsign, data, pax, quota = r
        dettagli.append(f"{data} {callsign}: PAX={pax}, quota={quota}")
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
            csv_rows = read_csv_rows(csv_path)
            n_csv = len(csv_rows)
            ok, rows = bgy_db.execute_query(
                "SELECT COUNT(*) FROM nightly_reports WHERE data_riferimento = %s",
                (ds,)
            )
            if ok and rows:
                n_db = rows[0][0]
                if n_csv != n_db:
                    mismatches.append(f"{ds}: CSV={n_csv}, DB={n_db}")
        d += timedelta(days=1)
    return len(mismatches) == 0, False, len(mismatches), 0, mismatches[:5]


def run_quality_check(days=7):
    end_date = datetime.now().date() - timedelta(days=1)
    start_date = end_date - timedelta(days=days - 1)
    date_from = start_date.strftime("%Y-%m-%d")
    date_to = end_date.strftime("%Y-%m-%d")

    logger.info(f"🔍 Quality check: {date_from} → {date_to} ({days} giorni)")

    thresholds = _get_quality_thresholds()

    checks_def = [
        (1, "Compagnie placeholder", lambda: _qc_compagnie_placeholder(date_from, date_to)),
        (2, "Compagnie NULL/N/D", lambda: _qc_compagnie_null(date_from, date_to)),
        (3, "Nomi compagnia anomali", lambda: _qc_nomi_anomali(date_from, date_to)),
        (4, "Notti con molti voli", lambda: _qc_notti_troppi_voli(date_from, date_to, thresholds)),
        (5, "Notti con pochi voli", lambda: _qc_notti_pochi_voli(date_from, date_to, thresholds)),
        (6, "Cargo eccessivi", lambda: _qc_cargo_eccessivi(date_from, date_to, thresholds)),
        (7, "Gap notti senza report", lambda: _qc_gap_notti(date_from, date_to, thresholds)),
        (8, "PAX=0 nei passeggeri", lambda: _qc_pax_zero(date_from, date_to, thresholds)),
        (9, "Valori fuori range", lambda: _qc_valori_assurdi(date_from, date_to, thresholds)),
        (10, "Coerenza CSV vs DB", lambda: _qc_csv_vs_db(date_from, date_to)),
    ]

    results = []
    ok_count = warn_count = err_count = 0

    for cid, nome, fn in checks_def:
        try:
            ok, warning, valore, soglia, dettagli = fn()
        except Exception as e:
            ok, warning = False, False
            valore, soglia = 0, 0
            dettagli = [f"Eccezione: {e}"]
            logger.error(f"Errore check {cid} '{nome}': {e}")

        if ok and not warning:
            ok_count += 1
        elif ok and warning:
            warn_count += 1
        else:
            err_count += 1

        results.append({
            "id": cid,
            "nome": nome,
            "ok": ok,
            "warning": warning,
            "valore": valore,
            "soglia": soglia,
            "dettagli": dettagli,
        })

    qc_result = {
        "periodo": {"da": date_from, "a": date_to, "giorni": days},
        "checks": results,
        "riepilogo": {"ok": ok_count, "warning": warn_count, "errori": err_count},
    }
    qc_result["testo_email"] = format_quality_text(qc_result)

    logger.info(
        f"✅ Quality check completato: "
        f"{ok_count} OK, {warn_count} warning, {err_count} errori"
    )
    return qc_result


def format_quality_text(qc_result):
    p = qc_result["periodo"]
    lines = [f"─── Qualità dati (ultimi {p['giorni']} giorni) ───"]

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

        if c["ok"] and not c["warning"]:
            if isinstance(valore, float):
                line = f"{icon} {nome}: {valore}% (soglia {soglia}%)"
            elif soglia > 0:
                line = f"{icon} {nome}: {valore} (soglia {soglia})"
            else:
                line = f"{icon} {nome}: {valore}"
        else:
            if isinstance(valore, float):
                line = f"{icon} {nome}: {valore}% (soglia {soglia}%)"
            elif soglia > 0:
                line = f"{icon} {nome}: {valore} (soglia {soglia})"
            else:
                line = f"{icon} {nome}: {valore}"

        lines.append(line)

        for d in c["dettagli"][:3]:
            lines.append(f"    → {d}")

    r = qc_result["riepilogo"]
    lines.append("─" * 37)
    lines.append(f"Riepilogo: {r['ok']} OK, {r['warning']} warning, {r['errori']} errori")

    return "\n".join(lines)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Import e sincronizzazione CSV -> PostgreSQL")
    parser.add_argument("--all", action="store_true",
                        help="Migrazione storica completa (tutte le directory)")
    parser.add_argument("--date", type=str,
                        help="Sync di una data specifica (YYYY-MM-DD)")
    parser.add_argument("--last-n-days", type=int,
                        help="Sync degli ultimi N giorni (incluso oggi)")
    parser.add_argument("--reset", action="store_true",
                        help="Svuota le tabelle prima (solo con --all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Analizza senza importare (solo con --all)")
    parser.add_argument("--quality-check", action="store_true",
                        help="Esegui solo il quality check (default: ultimi 7 giorni)")
    parser.add_argument("--days", type=int, default=7,
                        help="Numero di giorni per il quality check (default: 7)")
    args = parser.parse_args()

    if not bgy_db.is_enabled():
        logger.error("❌ DB non abilitato. Modifica config_database.json")
        sys.exit(1)

    success = True

    if args.quality_check:
        result = run_quality_check(days=args.days)
        print()
        print(result["testo_email"])
        print()
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