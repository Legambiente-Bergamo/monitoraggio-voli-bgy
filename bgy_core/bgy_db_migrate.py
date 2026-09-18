"""
bgy_core/bgy_db_migrate.py - Import e sincronizzazione CSV -> PostgreSQL.
Versione 2.5.4

Modulo unificato che contiene:
  - Funzioni di import per ogni tipo di file (scan, radar, meteo, nightly)
  - Parser per il formato vecchio di scan_*.csv (gennaio-luglio 2026)
  - Logica di migrazione storica completa (tutte le directory)
  - Logica di sincronizzazione incrementale (per data, per ultimi N giorni)

Uso:
    py -3.12 -m bgy_core.bgy_db_migrate                      # sync di ieri
    py -3.12 -m bgy_core.bgy_db_migrate --date 2026-09-17    # sync di una data
    py -3.12 -m bgy_core.bgy_db_migrate --last-n-days 7      # ultimi 7 giorni
    py -3.12 -m bgy_core.bgy_db_migrate --all                # migrazione completa
    py -3.12 -m bgy_core.bgy_db_migrate --all --reset        # reset + reimport
    py -3.12 -m bgy_core.bgy_db_migrate --all --dry-run      # analisi senza import
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

# Colonne attese nel formato nuovo
EXPECTED_NEW_COLUMNS = {
    "callsign_volo", "tipo_movimento", "destinazione_origine",
    "orario_schedulato", "orario_effettivo", "stato_volo",
}

# Colonne attese nel formato vecchio
EXPECTED_OLD_COLUMNS = {
    "flight_num", "type", "sched_time", "actual_time",
    "origin_dest", "status",
}

# Mappa tipo movimento formato vecchio -> nuovo
OLD_MOVEMENT_MAP = {
    "decollo": "D",
    "atterraggio": "A",
    "partenza": "D",
    "arrivo": "A",
}

# Contatori globali (per la modalità --all)
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


def _reset_stats():
    for k in stats:
        stats[k] = 0


# =============================================================================
# PARSING NOME FILE
# =============================================================================

def parse_date_from_scan_filename(filename):
    """Estrae data di riferimento, orario e tipo da un file scan_*.csv."""
    base = filename.replace(".csv", "")
    # Nuovo: scan_YYYY-MM-DD_HH-MM.csv
    m = re.match(r'^scan_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2})$', base)
    if m:
        date_str = m.group(1)
        hh_mm = m.group(2).replace("-", ":")
        hh = int(hh_mm.split(":")[0])
        tipo = "notturno" if hh >= 23 or hh < 6 else "diurno"
        return date_str, hh_mm, tipo
    # Vecchio: scan_YYYYMMDD_HHMM.csv
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
    """Ritorna 'new', 'old', o None."""
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
    """Estrae (destinazione, orario_sched, orario_eff, stato) da origin_dest."""
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
    """Converte una riga del formato vecchio nel formato nuovo (dict)."""
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
    """Importa un file scan_*.csv (nuovo o vecchio formato)."""
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
               (data_riferimento, callsign, tipo_movimento, is_scheduled,
                destinazione_finale, stato_destinazione, compagnia_aerea,
                modello_aereo, orario_schedulato, timestamp, pista, fase_volo,
                direzione, quota_ft, rotta_deg, distanza_km, paese,
                matched_score, stima_passeggeri, stima_rumore_db)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       %s, %s, %s, %s, %s, %s, %s, %s)""",
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
# SINCRONIZZAZIONE INCREMENTALE (per data)
# =============================================================================

def _date_matches(filename, date_str):
    """Verifica se il nome file contiene la data specificata."""
    compact = date_str.replace("-", "")
    return date_str in filename or compact in filename


def list_files_for_date(date_str):
    """Ritorna i path dei file CSV da sincronizzare per una data specifica."""
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
    """Sincronizza tutti i CSV relativi alla data specificata."""
    if not bgy_db.is_enabled():
        logger.warning("⚠️ DB non abilitato in config_database.json, sync saltato")
        return None

    ok, msg = bgy_db.test_connection()
    if not ok:
        logger.error(f"❌ Connessione DB fallita: {msg}")
        return None

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
    """Sincronizza i file di ieri (default per il job giornaliero)."""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    return sync_date(yesterday)


def sync_last_n_days(n):
    """Sincronizza i file degli ultimi n giorni (incluso oggi)."""
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
# MIGRAZIONE STORICA COMPLETA (--all)
# =============================================================================

def reset_tables():
    """Svuota le tabelle (TRUNCATE) per ricominciare da zero."""
    logger.warning("⚠️ RESET: svuoto tutte le tabelle...")
    tables = ["nightly_reports", "weather_hourly", "radar_detections",
              "flights_sacbo", "scans"]
    ok, result = bgy_db.execute_query(
        f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE",
        fetch=False
    )
    if ok:
        logger.info("✅ Tabelle svuotate")
    else:
        logger.error(f"❌ Errore reset: {result}")
    return ok


def migrate_all(reset=False, dry_run=False):
    """Migrazione storica completa: scansiona tutte le directory e importa."""
    if not bgy_db.is_enabled():
        logger.error("❌ DB non abilitato in config_database.json")
        return False

    ok, msg = bgy_db.test_connection()
    if not ok:
        logger.error(f"❌ Connessione DB fallita: {msg}")
        return False

    logger.info(f"Connessione DB OK: {msg}")
    logger.info(f"Schema version: {bgy_db.get_schema_version()}")

    if reset and not dry_run:
        reset_tables()

    scan_files = []
    radar_files = []
    meteo_files = []
    nightly_files = []

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
    logger.info(f"  Scansioni SACBO:      {len(scan_files)}")
    logger.info(f"  Radar:                {len(radar_files)}")
    logger.info(f"  Meteo:                {len(meteo_files)}")
    logger.info(f"  Report notturni:      {len(nightly_files)}")
    logger.info(f"  TOTALE:               {len(scan_files) + len(radar_files) + len(meteo_files) + len(nightly_files)}")
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
    logger.info(f"Scansioni importate:      {stats['scans_imported']}")
    logger.info(f"Scansioni già presenti:   {stats['scans_skipped']}")
    logger.info(f"Scansioni recuperate:     {stats['scans_recovered']}")
    logger.info(f"Scansioni formato vecchio:{stats['scans_old_format']}")
    logger.info(f"Scansioni non supportate: {stats['scans_unsupported']}")
    logger.info(f"Voli SACBO importati:     {stats['flights_imported']}")
    logger.info(f"Rilevamenti radar:        {stats['radar_imported']}")
    logger.info(f"Righe meteo:              {stats['weather_imported']}")
    logger.info(f"Voli notturni:            {stats['nightly_imported']}")
    logger.info(f"Errori:                   {stats['errors']}")
    logger.info("=" * 60)

    counts = bgy_db.get_table_counts()
    logger.info("Stato tabelle DB:")
    for t, c in counts.items():
        logger.info(f"  {t}: {c}")

    return True


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
    args = parser.parse_args()

    if not bgy_db.is_enabled():
        logger.error("❌ DB non abilitato. Modifica config_database.json")
        sys.exit(1)

    success = True

    if args.all:
        success = migrate_all(reset=args.reset, dry_run=args.dry_run)
    elif args.date:
        result = sync_date(args.date)
        success = result is not None
    elif args.last_n_days:
        result = sync_last_n_days(args.last_n_days)
        success = result is not None
    else:
        # Default: sincronizza ieri
        logger.info("Nessun argomento specificato, sincronizzo ieri")
        result = sync_yesterday()
        success = result is not None

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()