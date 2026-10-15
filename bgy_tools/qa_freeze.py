"""
bgy_tools/qa_freeze.py - Congela una sessione notturna per QA-01.
Versione 1.0.0

Uso:
    # Congela una data specifica
    py -3.12 -m bgy_tools.qa_freeze --date 2026-10-07

    # Congela tutte le date previste
    py -3.12 -m bgy_tools.qa_freeze --all

    # Force refresh: ricongela anche se già presente
    py -3.12 -m bgy_tools.qa_freeze --date 2026-10-07 --force

    # Elenca lo stato dei fixture
    py -3.12 -m bgy_tools.qa_freeze --status

Cosa fa per ogni data:
  1. Verifica presenza file raw + avionio della sessione
  2. Copia i file in bgy_tests/fixtures/{date}/raw/ e avionio/
  3. (Prima esecuzione) Dump anagrafiche + config in fixtures/
  4. Crea sandbox temporanea, applica monkey-patch
  5. Esegue generate_nightly_report(date)
  6. Salva output in fixtures/{date}/golden/v{version}/
  7. Aggiorna metadata.json

Novità v1.0.0 (QA-01, 13/10/2026):
- Prima versione.
- Freeze di 2026-10-07, 2026-10-09, 2026-10-12.
- Golden versionato per versione modulo (v2.9.29).
- Dump anagrafiche e config una tantum per rendere il test ripetibile.

Riferimenti: bgy_tools/qa_common.py, Addendum 3 (ciclo v3.8).
"""
import os
import sys
import shutil
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import (PROJECT_ROOT, RAW_DIR, OUTPUT_CSV_DIR,
                                CONFIG_DATA, CONFIG_DATABASE)
from bgy_core.bgy_dates import normalize_date

from bgy_tools.qa_common import (
    QA_ROOT, FIXTURES_DIR, AVIONIO_PROD_DIR,
    get_report_night_version,
    compute_sha256,
    list_session_files,
    load_metadata, save_metadata, build_metadata_entry,
    create_sandbox, cleanup_sandbox, patch_paths_for_sandbox,
    ensure_qa_dirs,
)

logger = get_logger("QAFreeze")

DEFAULT_DATES = ["2026-10-07", "2026-10-09", "2026-10-12"]


# -----------------------------------------------------------------------------
# VERIFICA PRE-FLIGHT
# -----------------------------------------------------------------------------

def check_session_availability(date_norm):
    """
    Verifica la presenza dei file per la sessione.
    Ritorna (ok, info) dove info è un dict con dettagli.
    """
    files = list_session_files(date_norm)
    info = {
        "scans":   {"found": 0, "total": 0, "files": []},
        "radar":   {"found": 0, "total": 0, "files": []},
        "avionio": {"found": 0, "total": 0, "files": []},
    }

    # Scans: cerchiamo almeno 3 file (23:00, una mezzanotte, una 05:00)
    scan_expected = 4
    info["scans"]["total"] = scan_expected
    info["scans"]["files"] = files["scans"]
    info["scans"]["found"] = len(files["scans"])

    # Radar: 2 file attesi (X, X+1)
    info["radar"]["total"] = 2
    info["radar"]["files"] = files["radar"]
    info["radar"]["found"] = len(files["radar"])

    # Avionio: almeno 1 file (a volte la finestra è corta)
    info["avionio"]["total"] = 1
    info["avionio"]["files"] = files["avionio"]
    info["avionio"]["found"] = len(files["avionio"])

    # Consideriamo "ok" se abbiamo almeno:
    #   - 3 file scan
    #   - 1 file radar
    #   - 1 file avionio
    ok = (info["scans"]["found"] >= 3
          and info["radar"]["found"] >= 1
          and info["avionio"]["found"] >= 1)
    return ok, info


# -----------------------------------------------------------------------------
# DUMP UNA TANTUM
# -----------------------------------------------------------------------------

def freeze_anagrafiche_once():
    """
    Dump delle anagrafiche da produzione in fixtures/anagrafiche_frozen.sql.
    Salta se il file esiste già.
    """
    target = os.path.join(FIXTURES_DIR, "anagrafiche_frozen.sql")
    if os.path.exists(target):
        logger.info(f"ℹ️ Dump anagrafiche già presente: {target}")
        return True

    logger.info("📤 Dump anagrafiche da produzione...")
    import subprocess

    cfg_path = CONFIG_DATABASE
    try:
        import json
        with open(cfg_path, "r", encoding="utf-8-sig") as f:
            cfg = json.load(f)
        user = cfg.get("user", "bgy_user")
        host = cfg.get("host", "localhost")
        dbname = cfg.get("dbname", "bgy_monitoring")
        password = cfg.get("password", "")
    except Exception as e:
        logger.error(f"Errore lettura config DB: {e}")
        return False

    tables = [
        "airlines", "iata_to_icao", "countries", "aircraft_models",
        "aircraft_by_code", "load_factors", "config_settings",
        "noise_stations", "noise_curves", "alert_messages",
        "assaeroporti_stats", "callsign_classifications",
        "callsign_airline_patterns",
    ]
    cmd = [
        r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe",
        "-U", user, "-h", host, "-d", dbname,
        "--data-only", "--column-inserts", "--on-conflict-do-nothing",
    ]
    for t in tables:
        cmd.extend(["--table", t])
    cmd.extend(["-f", target])

    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    try:
        r = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if r.returncode != 0:
            logger.error(f"pg_dump fallito: {r.stderr}")
            return False
        logger.info(f"✅ Dump anagrafiche: {target} ({os.path.getsize(target)} byte)")
        return True
    except Exception as e:
        logger.error(f"Errore pg_dump: {e}")
        return False


def freeze_config_once():
    """
    Copia config_data.json in fixtures/config_frozen.json.
    Salta se il file esiste già.
    """
    target = os.path.join(FIXTURES_DIR, "config_frozen.json")
    if os.path.exists(target):
        logger.info(f"ℹ️ Config frozen già presente: {target}")
        return True
    try:
        shutil.copy2(CONFIG_DATA, target)
        logger.info(f"✅ Config frozen: {target}")
        return True
    except Exception as e:
        logger.error(f"Errore copia config: {e}")
        return False


# -----------------------------------------------------------------------------
# FREEZE DI UNA DATA
# -----------------------------------------------------------------------------

def _copy_files(file_list, src_dir, dst_dir):
    """Copia i file in lista da src_dir a dst_dir."""
    os.makedirs(dst_dir, exist_ok=True)
    n = 0
    for f in file_list:
        src = os.path.join(src_dir, f)
        if not os.path.exists(src):
            logger.warning(f"⚠️ File atteso non trovato: {src}")
            continue
        shutil.copy2(src, os.path.join(dst_dir, f))
        n += 1
    return n


def freeze_date(date_norm, force=False, note=""):
    """
    Congela una sessione notturna:
      1. Copia raw + avionio in fixtures/{date}/
      2. Esegue generate_nightly_report in sandbox
      3. Salva golden in fixtures/{date}/golden/v{version}/
      4. Aggiorna metadata.json
    """
    date_norm = normalize_date(date_norm)
    if not date_norm:
        logger.error(f"Data non valida")
        return False

    fixture_dir = os.path.join(FIXTURES_DIR, date_norm)

    if os.path.exists(fixture_dir) and not force:
        logger.info(f"⏭️ Fixture già presente: {fixture_dir} (usa --force per ricongelare)")
        return True

    logger.info("=" * 60)
    logger.info(f"FREEZE sessione notturna: {date_norm}")
    logger.info("=" * 60)

    # 1) Verifica disponibilità
    ok, info = check_session_availability(date_norm)
    if not ok:
        logger.error(f"❌ File insufficienti per {date_norm}")
        logger.error(f"   Scans: {info['scans']['found']}/{info['scans']['total']}")
        logger.error(f"   Radar: {info['radar']['found']}/{info['radar']['total']}")
        logger.error(f"   Avionio: {info['avionio']['found']}/{info['avionio']['total']}")
        return False

    logger.info(f"✅ File trovati:")
    logger.info(f"   Scans: {info['scans']['found']} ({', '.join(info['scans']['files'])})")
    logger.info(f"   Radar: {info['radar']['found']} ({', '.join(info['radar']['files'])})")
    logger.info(f"   Avionio: {info['avionio']['found']}")

    # 2) Copia file nei fixture
    if force and os.path.exists(fixture_dir):
        shutil.rmtree(fixture_dir)
    os.makedirs(fixture_dir, exist_ok=True)

    n_scans = _copy_files(info["scans"]["files"], RAW_DIR,
                          os.path.join(fixture_dir, "raw"))
    n_radar = _copy_files(info["radar"]["files"], RAW_DIR,
                          os.path.join(fixture_dir, "raw"))
    n_avionio = _copy_files(info["avionio"]["files"], AVIONIO_PROD_DIR,
                            os.path.join(fixture_dir, "avionio"))

    logger.info(f"📦 Copiati: {n_scans} scans, {n_radar} radar, {n_avionio} avionio")

    # 3) Sandbox + run
    sandbox = create_sandbox(date_norm, fixture_dir)
    logger.info(f"🧪 Sandbox: {sandbox}")

    try:
        import bgy_reports.bgy_report_night as bgy_rn

        with patch_paths_for_sandbox(sandbox):
            logger.info(f"▶️  Esecuzione generate_nightly_report({date_norm})...")
            out_path, msg = bgy_rn.generate_nightly_report(date_norm)
            logger.info(f"   {msg}")

        if not out_path or not os.path.exists(out_path):
            logger.error(f"❌ Nessun output prodotto da generate_nightly_report")
            return False

        # 4) Salva golden
        version = get_report_night_version()
        golden_dir = os.path.join(fixture_dir, "golden", f"v{version}")
        os.makedirs(golden_dir, exist_ok=True)

        golden_report = os.path.join(golden_dir, os.path.basename(out_path))
        shutil.copy2(out_path, golden_report)

        # Anche borderline
        sandbox_output = os.path.join(sandbox, "output")
        borderline_file = os.path.join(sandbox_output,
                                        f"borderline_{date_norm}.csv")
        golden_borderline = None
        if os.path.exists(borderline_file):
            golden_borderline = os.path.join(golden_dir,
                                              f"borderline_{date_norm}.csv")
            shutil.copy2(borderline_file, golden_borderline)

        # 5) Calcola hash e righe del golden
        import pandas as pd
        n_rows = len(pd.read_csv(golden_report))
        sha = compute_sha256(golden_report)

        # 6) Aggiorna metadata.json
        meta = load_metadata(date_norm)
        entry = build_metadata_entry(version, sha, n_rows, note=note)

        if "history" not in meta:
            meta["history"] = []
        meta["history"].append(entry)
        meta["date"] = date_norm
        meta["current"] = entry

        save_metadata(date_norm, meta)

        logger.info(f"✅ Golden salvato: {golden_report}")
        logger.info(f"   Versione modulo: {version}")
        logger.info(f"   Righe: {n_rows}")
        logger.info(f"   SHA256: {sha[:16]}...")
        if golden_borderline:
            logger.info(f"   Borderline: {golden_borderline}")

        return True

    except Exception as e:
        logger.error(f"❌ Errore durante il freeze: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        cleanup_sandbox(sandbox)


# -----------------------------------------------------------------------------
# STATUS
# -----------------------------------------------------------------------------

def show_status():
    """Elenca lo stato dei fixture presenti."""
    ensure_qa_dirs()
    print()
    print("=" * 70)
    print("STATO FIXTURES QA-01")
    print("=" * 70)

    if not os.path.isdir(FIXTURES_DIR):
        print("Nessun fixture presente.")
        return

    n = 0
    for entry in sorted(os.listdir(FIXTURES_DIR)):
        sub = os.path.join(FIXTURES_DIR, entry)
        if not os.path.isdir(sub):
            continue
        meta = load_metadata(entry)
        cur = meta.get("current", {})
        version = cur.get("version", "?")
        n_rows = cur.get("n_rows", "?")
        freeze_date = cur.get("freeze_date", "?")
        history_len = len(meta.get("history", []))
        print(f"  {entry}  v{version}  righe={n_rows}  "
              f"freeze={freeze_date}  history={history_len}")
        n += 1

    print()
    print(f"Totale fixture: {n}")

    # File di supporto
    for support in ("anagrafiche_frozen.sql", "config_frozen.json"):
        p = os.path.join(FIXTURES_DIR, support)
        if os.path.exists(p):
            size = os.path.getsize(p)
            print(f"  {support}  ({size} byte)")
        else:
            print(f"  {support}  [assente]")


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Congela una sessione notturna per QA-01")
    parser.add_argument("--date", type=str,
                        help="Data della sessione (YYYY-MM-DD)")
    parser.add_argument("--all", action="store_true",
                        help=f"Congela le date default: {DEFAULT_DATES}")
    parser.add_argument("--force", action="store_true",
                        help="Ricongela anche se il fixture esiste")
    parser.add_argument("--status", action="store_true",
                        help="Mostra lo stato dei fixture e termina")
    parser.add_argument("--note", type=str, default="",
                        help="Nota per il metadata (opzionale)")
    args = parser.parse_args()

    if args.status:
        show_status()
        return 0

    if not args.date and not args.all:
        parser.print_help()
        return 1

    ensure_qa_dirs()

    # Dump una tantum
    if not freeze_anagrafiche_once():
        logger.error("Impossibile preparare il dump anagrafiche")
        return 1
    if not freeze_config_once():
        logger.error("Impossibile preparare il config frozen")
        return 1

    dates = [args.date] if args.date else DEFAULT_DATES
    results = {}
    for d in dates:
        try:
            ok = freeze_date(d, force=args.force, note=args.note)
            results[d] = ok
        except Exception as e:
            logger.error(f"Errore su {d}: {e}")
            results[d] = False

    print()
    print("=" * 60)
    print("RIEPILOGO FREEZE")
    print("=" * 60)
    for d, ok in results.items():
        print(f"  {d}: {'OK' if ok else 'FALLITO'}")

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())