"""
bgy_tools/qa_common.py - Utility condivise per QA-01 (regressione notturna).
Versione 1.0.1

Contiene:
  - Costanti di percorso (bgy_tests/, fixtures/)
  - Utility: hashing SHA256, lettura versione modulo
  - Selezione file di sessione (raw + avionio)
  - Context manager per monkey-patch di path e side-effect
  - Sandbox temporanea
  - Diff semantico di report CSV

Novità v1.0.1 (QA-01, 13/10/2026):
- FIX: diff_reports() ora popola row_count_golden / row_count_actual
  anche in caso di SHA256 match. Prima il messaggio di PASS riportava
  erroneamente "0 righe". Il conteggio è ora calcolato prima del check
  hash tramite _count_csv_rows().

Novità v1.0.0 (QA-01, 13/10/2026):
- Prima versione. Utility per qa_freeze.py e qa_check.py.
- Freeze di 3 sessioni notturne (2026-10-07, 2026-10-09, 2026-10-12)
  con golden versionati per versione modulo.
- Check ripetibile contro DB test bgy_qa_test.

Riferimenti: Addendum 3 (ciclo v3.8), Relazione v3.8 §13.3 (metodologia
analoga a INFRA-07).
"""
import os
import sys
import json
import shutil
import hashlib
import tempfile
import re
import csv
from datetime import datetime, timedelta
from contextlib import contextmanager

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import PROJECT_ROOT, RAW_DIR, OUTPUT_CSV_DIR
from bgy_core.bgy_dates import normalize_date

logger = get_logger("QACommon")

QA_ROOT = os.path.join(PROJECT_ROOT, "bgy_tests")
FIXTURES_DIR = os.path.join(QA_ROOT, "fixtures")

# Cartella Avionio di produzione (in bgy_scanner_alt è calcolata da _PROJECT_ROOT)
AVIONIO_PROD_DIR = os.path.join(PROJECT_ROOT, "bgy_data", "bgy_avionio")

# Finestra file Avionio per la sessione notturna
SESSION_AVIONIO_START_HOUR = 22   # giorno X: file con ora >= 22:00
SESSION_AVIONIO_END_HOUR = 7      # giorno X+1: file con ora < 07:00

# Finestra scan SACBO per la sessione notturna
SESSION_SCAN_TIMES = ['23-00', '00-00', '00-01', '02-00', '05-00', '06-00']

# Regex nome file Avionio
_AVIONIO_FILENAME_RE = re.compile(
    r"^avionio_(arrivals|departures)_(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})\.csv$"
)


# -----------------------------------------------------------------------------
# VERSIONE MODULO
# -----------------------------------------------------------------------------

def get_report_night_version():
    """
    Legge la versione di bgy_reports/bgy_report_night.py dal docstring.
    Ritorna 'X.Y.Z' o 'unknown' se non trovata.
    """
    path = os.path.join(PROJECT_ROOT, "bgy_reports", "bgy_report_night.py")
    if not os.path.exists(path):
        logger.warning(f"bgy_report_night.py non trovato in {path}")
        return "unknown"
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            head = "".join(f.readline() for _ in range(50))
    except Exception as e:
        logger.warning(f"Errore lettura versione bgy_report_night.py: {e}")
        return "unknown"
    m = re.search(r"Versione\s+(\d+\.\d+\.\d+)", head)
    return m.group(1) if m else "unknown"


# -----------------------------------------------------------------------------
# HASH
# -----------------------------------------------------------------------------

def compute_sha256(path):
    """SHA256 di un file. Ritorna stringa esadecimale."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _count_csv_rows(path):
    """
    v1.0.1: conta le righe dati di un CSV (esclusa la riga di header).
    Usa la stdlib csv, non pandas (leggero, sufficiente per il conteggio).
    Ritorna 0 in caso di errore.
    """
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            return sum(1 for _ in reader)
    except Exception as e:
        logger.warning(f"Errore conteggio righe {path}: {e}")
        return 0


# -----------------------------------------------------------------------------
# SELEZIONE FILE DI SESSIONE
# -----------------------------------------------------------------------------

def _extract_scan_time(filename):
    """Estrae 'HH-MM' dal nome file scan_*.csv. Ritorna None se non trovato."""
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


def list_scan_files_for_session(date_norm):
    """
    Ritorna i file scan_*.csv della sessione notturna:
      - giorno X: scan con ora >= 23
      - giorno X+1: scan con ora < 06
    """
    date_norm = normalize_date(date_norm)
    if not date_norm:
        return []
    next_date = (datetime.strptime(date_norm, "%Y-%m-%d")
                 + timedelta(days=1)).strftime("%Y-%m-%d")

    files = []
    if not os.path.isdir(RAW_DIR):
        return files

    for f in os.listdir(RAW_DIR):
        if not f.startswith("scan_") or not f.endswith(".csv"):
            continue
        scan_time = _extract_scan_time(f)
        if not scan_time or scan_time not in SESSION_SCAN_TIMES:
            continue
        if f.startswith(f"scan_{date_norm}_"):
            try:
                hh = int(scan_time.split("-")[0])
                if hh >= 23:
                    files.append(f)
            except Exception:
                pass
        elif f.startswith(f"scan_{next_date}_"):
            try:
                hh = int(scan_time.split("-")[0])
                if hh < 6:
                    files.append(f)
            except Exception:
                pass
    return sorted(files)


def list_radar_files_for_session(date_norm):
    """
    Ritorna i file radar_*.csv della sessione notturna:
    radar_{date}.csv e radar_{date+1}.csv (se esistono).
    """
    date_norm = normalize_date(date_norm)
    if not date_norm:
        return []
    next_date = (datetime.strptime(date_norm, "%Y-%m-%d")
                 + timedelta(days=1)).strftime("%Y-%m-%d")

    files = []
    for d in (date_norm, next_date):
        p = os.path.join(RAW_DIR, f"radar_{d}.csv")
        if os.path.exists(p):
            files.append(f"radar_{d}.csv")
    return files


def list_avionio_files_for_session(date_norm):
    """
    Ritorna i file avionio_*.csv della sessione notturna:
      - giorno X: file con ora >= 22:00
      - giorno X+1: file con ora < 07:00
    """
    date_norm = normalize_date(date_norm)
    if not date_norm:
        return []
    next_date = (datetime.strptime(date_norm, "%Y-%m-%d")
                 + timedelta(days=1)).strftime("%Y-%m-%d")

    files = []
    if not os.path.isdir(AVIONIO_PROD_DIR):
        return files

    for fname in os.listdir(AVIONIO_PROD_DIR):
        m = _AVIONIO_FILENAME_RE.match(fname)
        if not m:
            continue
        fdate = m.group(2)
        fhour = int(m.group(3))
        if fdate == date_norm and fhour >= SESSION_AVIONIO_START_HOUR:
            files.append(fname)
        elif fdate == next_date and fhour < SESSION_AVIONIO_END_HOUR:
            files.append(fname)
    return sorted(files)


def list_session_files(date_norm):
    """
    Ritorna dict con le liste di file per la sessione:
        {
            "scans":   [nomi file],
            "radar":   [nomi file],
            "avionio": [nomi file],
        }
    """
    return {
        "scans":   list_scan_files_for_session(date_norm),
        "radar":   list_radar_files_for_session(date_norm),
        "avionio": list_avionio_files_for_session(date_norm),
    }


# -----------------------------------------------------------------------------
# METADATA
# -----------------------------------------------------------------------------

def _metadata_path(date_norm):
    return os.path.join(FIXTURES_DIR, date_norm, "metadata.json")


def load_metadata(date_norm):
    """Legge metadata.json della fixture. Ritorna dict vuoto se assente."""
    p = _metadata_path(date_norm)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Errore lettura metadata {date_norm}: {e}")
        return {}


def save_metadata(date_norm, meta):
    """Scrive metadata.json della fixture."""
    p = _metadata_path(date_norm)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Errore scrittura metadata {date_norm}: {e}")
        return False


def build_metadata_entry(version, golden_sha256, n_rows, note=""):
    """Costruisce un entry per history[]."""
    return {
        "version": version,
        "freeze_date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "golden_sha256": golden_sha256,
        "n_rows": n_rows,
        "note": note,
    }


# -----------------------------------------------------------------------------
# SANDBOX
# -----------------------------------------------------------------------------

def create_sandbox(date_norm, fixture_dir):
    """
    Crea una sandbox temporanea con la struttura attesa da
    generate_nightly_report():

      {tmp}/
        raw/           <- copia di fixtures/{date}/raw/
        avionio/       <- copia di fixtures/{date}/avionio/
        output/        <- vuota (dove verrà scritto il report)

    Ritorna il path della sandbox. Da cancellare con shutil.rmtree a fine uso.
    """
    sandbox = tempfile.mkdtemp(prefix=f"bgy_qa_{date_norm}_")
    raw_src = os.path.join(fixture_dir, "raw")
    avionio_src = os.path.join(fixture_dir, "avionio")

    raw_dst = os.path.join(sandbox, "raw")
    avionio_dst = os.path.join(sandbox, "avionio")
    output_dst = os.path.join(sandbox, "output")

    os.makedirs(raw_dst, exist_ok=True)
    os.makedirs(avionio_dst, exist_ok=True)
    os.makedirs(output_dst, exist_ok=True)

    if os.path.isdir(raw_src):
        for f in os.listdir(raw_src):
            shutil.copy2(os.path.join(raw_src, f), os.path.join(raw_dst, f))
    if os.path.isdir(avionio_src):
        for f in os.listdir(avionio_src):
            shutil.copy2(os.path.join(avionio_src, f), os.path.join(avionio_dst, f))

    return sandbox


def cleanup_sandbox(sandbox):
    """Rimuove la sandbox e il suo contenuto."""
    if sandbox and os.path.isdir(sandbox):
        try:
            shutil.rmtree(sandbox)
        except Exception as e:
            logger.warning(f"Errore cleanup sandbox {sandbox}: {e}")


# -----------------------------------------------------------------------------
# MONKEY-PATCH CONTEXT
# -----------------------------------------------------------------------------

@contextmanager
def patch_paths_for_sandbox(sandbox):
    """
    Context manager che monkey-patcha i path usati da bgy_report_night.py
    per far leggere/scrivere dalla sandbox anziché dalle cartelle di
    produzione.

    Patch:
        bgy_reports.bgy_report_night.RAW_DIR
        bgy_reports.bgy_report_night.OUTPUT_CSV_DIR
        bgy_reports.bgy_report_night.save_night_weather  (no-op)
        bgy_scanners.bgy_scanner_alt.AVIONIO_DIR
    """
    import bgy_reports.bgy_report_night as bgy_rn
    import bgy_scanners.bgy_scanner_alt as bgy_alt

    saved = {
        "rn_raw_dir":       bgy_rn.RAW_DIR,
        "rn_output_csv":    bgy_rn.OUTPUT_CSV_DIR,
        "rn_save_weather":  bgy_rn.save_night_weather,
        "alt_avionio_dir":  bgy_alt.AVIONIO_DIR,
    }

    try:
        bgy_rn.RAW_DIR = os.path.join(sandbox, "raw")
        bgy_rn.OUTPUT_CSV_DIR = os.path.join(sandbox, "output")
        bgy_rn.save_night_weather = lambda *a, **kw: None
        bgy_alt.AVIONIO_DIR = os.path.join(sandbox, "avionio")
        yield
    finally:
        bgy_rn.RAW_DIR = saved["rn_raw_dir"]
        bgy_rn.OUTPUT_CSV_DIR = saved["rn_output_csv"]
        bgy_rn.save_night_weather = saved["rn_save_weather"]
        bgy_alt.AVIONIO_DIR = saved["alt_avionio_dir"]


# -----------------------------------------------------------------------------
# DIFF
# -----------------------------------------------------------------------------

def diff_reports(golden_path, actual_path, numeric_tolerance=1):
    """
    Confronto semantico di due CSV di report.

    Ritorna dict:
        {
            "identical": bool,              # SHA256 o contenuto identico
            "shape_match": bool,
            "columns_match": bool,
            "columns_missing": [col],
            "columns_extra": [col],
            "row_count_golden": int,
            "row_count_actual": int,
            "cells_diff": [                 # lista di differenze cella
                {"row": i, "col": "...", "golden": v, "actual": w},
            ],
            "rows_only_in_golden": [...],   # se shape diversa
            "rows_only_in_actual": [...],
        }
    """
    import pandas as pd

    result = {
        "identical": False,
        "shape_match": False,
        "columns_match": False,
        "columns_missing": [],
        "columns_extra": [],
        "row_count_golden": 0,
        "row_count_actual": 0,
        "cells_diff": [],
        "rows_only_in_golden": [],
        "rows_only_in_actual": [],
    }

    if not os.path.exists(golden_path) or not os.path.exists(actual_path):
        return result

    # v1.0.1: popola SEMPRE i counts prima di qualsiasi early-return.
    # Così anche in caso di SHA256 match il messaggio di PASS è corretto.
    result["row_count_golden"] = _count_csv_rows(golden_path)
    result["row_count_actual"] = _count_csv_rows(actual_path)

    # Check hash rapido
    if compute_sha256(golden_path) == compute_sha256(actual_path):
        result["identical"] = True
        return result

    try:
        df_g = pd.read_csv(golden_path)
        df_a = pd.read_csv(actual_path)
    except Exception as e:
        logger.error(f"Errore lettura CSV per diff: {e}")
        return result

    # v1.0.1: i counts sono già stati popolati sopra; non li riassegnamo.
    result["columns_match"] = list(df_g.columns) == list(df_a.columns)
    if not result["columns_match"]:
        result["columns_missing"] = sorted(set(df_g.columns) - set(df_a.columns))
        result["columns_extra"] = sorted(set(df_a.columns) - set(df_g.columns))
        return result

    result["shape_match"] = len(df_g) == len(df_a)

    if result["shape_match"]:
        # Confronto cella per cella
        for i in range(len(df_g)):
            for col in df_g.columns:
                vg = df_g.iloc[i][col]
                va = df_a.iloc[i][col]
                if pd.isna(vg) and pd.isna(va):
                    continue
                # Tolleranza su numerici
                try:
                    if pd.api.types.is_number(vg) and pd.api.types.is_number(va):
                        if abs(float(vg) - float(va)) <= numeric_tolerance:
                            continue
                except (TypeError, ValueError):
                    pass
                if str(vg) != str(va):
                    result["cells_diff"].append({
                        "row": i, "col": col,
                        "golden": vg, "actual": va,
                    })
                    if len(result["cells_diff"]) >= 50:
                        # Cap per non esplodere su diff enormi
                        return result
        return result

    # Shape diversa: confronto per chiave (callsign, orario_schedulato)
    key_cols = ["callsign", "orario_schedulato"]
    if not all(c in df_g.columns for c in key_cols):
        return result
    if not all(c in df_a.columns for c in key_cols):
        return result

    def _key(r):
        return (str(r.get("callsign", "")),
                str(r.get("orario_schedulato", "")))

    keys_g = {_key(r) for _, r in df_g.iterrows()}
    keys_a = {_key(r) for _, r in df_a.iterrows()}

    for k in sorted(keys_g - keys_a):
        result["rows_only_in_golden"].append(list(k))
    for k in sorted(keys_a - keys_g):
        result["rows_only_in_actual"].append(list(k))

    return result


# -----------------------------------------------------------------------------
# ENSURE DIRS
# -----------------------------------------------------------------------------

def ensure_qa_dirs():
    """Crea bgy_tests/ e bgy_tests/fixtures/ se non esistono."""
    os.makedirs(FIXTURES_DIR, exist_ok=True)