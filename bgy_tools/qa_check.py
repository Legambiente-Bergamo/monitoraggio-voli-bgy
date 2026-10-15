"""
bgy_tools/qa_check.py - Verifica regressione notturna (QA-01).
Versione 1.0.1

Esegue generate_nightly_report() sulle sessioni congelate in
bgy_tests/fixtures/ e confronta l'output con i golden di riferimento
della versione corrente di bgy_report_night.py.

Uso:
    # Check di tutte le fixture
    py -3.12 -m bgy_tools.qa_check

    # Check di una data specifica
    py -3.12 -m bgy_tools.qa_check --date 2026-10-09

    # Non cancellare DB test a fine esecuzione (debug)
    py -3.12 -m bgy_tools.qa_check --keep-db

Workflow:
  1. Salva il config_database.json originale (in memoria)
  2. Crea DB test bgy_qa_test
  3. Override config → bgy_qa_test
  4. Applica bgy_db.apply_schema() (tabelle operative + vista)
  5. Applica bgy_docs/anagrafiche_schema.sql (13 tabelle anagrafiche)
  6. Applica bgy_tests/fixtures/anagrafiche_frozen.sql (dati anagrafiche)
  7. Per ogni fixture: sandbox, esecuzione, confronto con golden
  8. Ripristina config (sempre, anche in caso di errore)
  9. Drop DB test (salvo --keep-db)

Prerequisiti:
  - PostgreSQL attivo su localhost:5432
  - Fixture preparate con qa_freeze.py
  - Utente postgres con accesso senza password (o PGPASSWORD in env)

Novità v1.0.1 (QA-01, 13/10/2026):
- FIX: applica bgy_docs/anagrafiche_schema.sql prima del dump dei dati.
  apply_schema() crea solo le tabelle operative; le 13 tabelle anagrafiche
  sono definite in bgy_docs/anagrafiche_schema.sql e vanno create prima
  di importare anagrafiche_frozen.sql.
- FIX: drop del DB test garantito anche se il setup fallisce a metà.
  Prima un errore su anagrafiche lasciava bgy_qa_test orfano.

Novità v1.0.0 (QA-01, 13/10/2026):
- Prima versione.

Riferimenti: bgy_tools/qa_common.py, bgy_tools/qa_freeze.py, Addendum 3.
"""
import os
import sys
import json
import shutil
import argparse
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import (
    PROJECT_ROOT, CONFIG_DATABASE,
)
from bgy_core.bgy_dates import normalize_date

from bgy_tools.qa_common import (
    FIXTURES_DIR,
    get_report_night_version,
    compute_sha256,
    load_metadata,
    create_sandbox, cleanup_sandbox, patch_paths_for_sandbox,
    diff_reports,
)

logger = get_logger("QACheck")

TEST_DB_NAME = "bgy_qa_test"
PSQL = r"C:\Program Files\PostgreSQL\17\bin\psql.exe"

ANAGRAFICHE_SCHEMA_PATH = os.path.join(
    PROJECT_ROOT, "bgy_docs", "anagrafiche_schema.sql"
)


# -----------------------------------------------------------------------------
# CONFIG OVERRIDE (senza BOM, come da Addendum 2 §6.4)
# -----------------------------------------------------------------------------

def _read_config_db():
    with open(CONFIG_DATABASE, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _write_config_db(cfg):
    """Scrittura senza BOM."""
    with open(CONFIG_DATABASE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)


def override_config_to_test_db():
    """Salva l'originale in memoria e sovrascrive dbname → bgy_qa_test."""
    cfg_orig = _read_config_db()
    cfg_test = dict(cfg_orig)
    cfg_test["dbname"] = TEST_DB_NAME
    _write_config_db(cfg_test)
    return cfg_orig


def restore_config_db(cfg_orig):
    """Ripristina il config originale."""
    _write_config_db(cfg_orig)


# -----------------------------------------------------------------------------
# DB TEST
# -----------------------------------------------------------------------------

def _psql_superuser(sql, db="postgres"):
    """Esegue un comando psql come superuser (postgres)."""
    cmd = [PSQL, "-U", "postgres", "-h", "localhost", "-d", db, "-c", sql]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0, r.stdout + r.stderr


def _psql_user(sql_or_file, user, password, db, is_file=False):
    """Esegue psql come bgy_user, con file o SQL inline."""
    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password
    if is_file:
        cmd = [PSQL, "-U", user, "-h", "localhost", "-d", db,
               "-v", "ON_ERROR_STOP=1", "-f", sql_or_file]
    else:
        cmd = [PSQL, "-U", user, "-h", "localhost", "-d", db, "-c", sql_or_file]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return r.returncode == 0, r.stdout + r.stderr


def create_test_db(user):
    """Drop + create bgy_qa_test. Owner: bgy_user."""
    ok, out = _psql_superuser(
        f"DROP DATABASE IF EXISTS {TEST_DB_NAME};"
    )
    if not ok:
        return False, f"DROP fallito: {out}"
    ok, out = _psql_superuser(
        f"CREATE DATABASE {TEST_DB_NAME} OWNER {user};"
    )
    if not ok:
        return False, f"CREATE fallito: {out}"
    return True, ""


def drop_test_db():
    """Drop bgy_qa_test (ignora errori)."""
    _psql_superuser(f"DROP DATABASE IF EXISTS {TEST_DB_NAME};")


def apply_schema_to_test_db(user, password):
    """Applica lo schema operativo via bgy_db.apply_schema()."""
    from bgy_core.bgy_db import apply_schema, SCHEMA_VERSION
    ok, msg = apply_schema()
    return ok, f"{msg} (SCHEMA_VERSION={SCHEMA_VERSION})"


def apply_anagrafiche_schema_to_test_db(user, password):
    """
    v1.0.1: applica bgy_docs/anagrafiche_schema.sql (crea le 13 tabelle
    anagrafiche). Deve precedere il dump dei dati.
    """
    if not os.path.exists(ANAGRAFICHE_SCHEMA_PATH):
        return False, f"File non trovato: {ANAGRAFICHE_SCHEMA_PATH}"
    ok, out = _psql_user(ANAGRAFICHE_SCHEMA_PATH, user, password,
                         TEST_DB_NAME, is_file=True)
    return ok, out


def apply_anagrafiche_to_test_db(user, password):
    """Carica anagrafiche_frozen.sql nel DB test (dati)."""
    sql_path = os.path.join(FIXTURES_DIR, "anagrafiche_frozen.sql")
    if not os.path.exists(sql_path):
        return False, f"File non trovato: {sql_path}"
    ok, out = _psql_user(sql_path, user, password, TEST_DB_NAME, is_file=True)
    return ok, out


# -----------------------------------------------------------------------------
# CHECK DI UNA FIXTURE
# -----------------------------------------------------------------------------

def check_fixture(date_norm, note="", verbose=False):
    """
    Esegue generate_nightly_report sulla fixture e confronta col golden.
    """
    result = {
        "date": date_norm,
        "status": "SKIP",
        "reason": "",
        "golden_path": "",
        "actual_path": "",
        "diff": {},
    }

    fixture_dir = os.path.join(FIXTURES_DIR, date_norm)
    if not os.path.isdir(fixture_dir):
        result["reason"] = f"Fixture non trovata: {fixture_dir}"
        return result

    version = get_report_night_version()
    if version == "unknown":
        result["reason"] = "Impossibile determinare versione di bgy_report_night.py"
        return result

    golden_dir = os.path.join(fixture_dir, "golden", f"v{version}")
    golden_report = os.path.join(golden_dir, f"report_nightly_{date_norm}.csv")
    if not os.path.exists(golden_report):
        result["reason"] = (
            f"Golden per v{version} non trovato in {golden_dir}. "
            f"Ricongela con: py -3.12 -m bgy_tools.qa_freeze --date {date_norm} --force"
        )
        return result

    result["golden_path"] = golden_report

    sandbox = create_sandbox(date_norm, fixture_dir)
    try:
        import bgy_reports.bgy_report_night as bgy_rn
        import importlib
        importlib.reload(bgy_rn)

        with patch_paths_for_sandbox(sandbox):
            if verbose:
                logger.info(f"▶️  Esecuzione generate_nightly_report({date_norm})")
            out_path, msg = bgy_rn.generate_nightly_report(date_norm)

        if not out_path or not os.path.exists(out_path):
            result["status"] = "FAIL"
            result["reason"] = f"generate_nightly_report non ha prodotto output: {msg}"
            return result

        result["actual_path"] = out_path

        diff = diff_reports(golden_report, out_path)
        result["diff"] = diff

        if diff["identical"]:
            result["status"] = "PASS"
            result["reason"] = f"Identico (SHA256 match, {diff['row_count_golden']} righe)"
        else:
            if diff["shape_match"] and diff["columns_match"]:
                n_diff = len(diff["cells_diff"])
                result["status"] = "FAIL"
                result["reason"] = (
                    f"{n_diff} celle diverse (righe {diff['row_count_golden']} → "
                    f"{diff['row_count_actual']})"
                )
            elif diff["shape_match"] is False:
                n_gold = len(diff["rows_only_in_golden"])
                n_act = len(diff["rows_only_in_actual"])
                result["status"] = "FAIL"
                result["reason"] = (
                    f"Shape diversa: {n_gold} righe solo nel golden, "
                    f"{n_act} solo nell'actual "
                    f"(golden {diff['row_count_golden']} → actual {diff['row_count_actual']})"
                )
            elif not diff["columns_match"]:
                result["status"] = "FAIL"
                result["reason"] = (
                    f"Colonne diverse: mancanti={diff['columns_missing']}, "
                    f"extra={diff['columns_extra']}"
                )
            else:
                result["status"] = "FAIL"
                result["reason"] = "Differenza non classificata"

        # Borderline
        sandbox_borderline = os.path.join(sandbox, "output",
                                           f"borderline_{date_norm}.csv")
        golden_borderline = os.path.join(golden_dir,
                                          f"borderline_{date_norm}.csv")
        both_exist = os.path.exists(sandbox_borderline) and os.path.exists(golden_borderline)
        neither_exist = (not os.path.exists(sandbox_borderline)
                         and not os.path.exists(golden_borderline))
        if both_exist:
            b_diff = diff_reports(golden_borderline, sandbox_borderline)
            result["borderline_identical"] = b_diff["identical"]
            if not b_diff["identical"] and result["status"] == "PASS":
                result["status"] = "FAIL"
                result["reason"] = "Borderline diverso dal golden"
        elif neither_exist:
            result["borderline_identical"] = True
        else:
            result["borderline_identical"] = False
            if result["status"] == "PASS":
                result["status"] = "FAIL"
                result["reason"] = "Borderline presente solo in uno dei due"

        return result
    except Exception as e:
        result["status"] = "FAIL"
        result["reason"] = f"Eccezione: {e}"
        import traceback
        logger.error(traceback.format_exc())
        return result
    finally:
        cleanup_sandbox(sandbox)


# -----------------------------------------------------------------------------
# REPORT DIFF
# -----------------------------------------------------------------------------

def print_diff_summary(r):
    """Stampa un riassunto del diff per una fixture fallita."""
    d = r.get("diff", {})
    if not d:
        return
    print()
    print(f"  --- Diff per {r['date']} ---")
    if not d.get("columns_match", True):
        print(f"  Colonne mancanti (golden-only): {d['columns_missing']}")
        print(f"  Colonne extra   (actual-only): {d['columns_extra']}")
        return
    if not d.get("shape_match", True):
        print(f"  Righe golden: {d['row_count_golden']}")
        print(f"  Righe actual: {d['row_count_actual']}")
        n_gold = len(d.get("rows_only_in_golden", []))
        n_act = len(d.get("rows_only_in_actual", []))
        print(f"  Righe solo golden ({n_gold}): {d.get('rows_only_in_golden', [])[:5]}")
        print(f"  Righe solo actual ({n_act}): {d.get('rows_only_in_actual', [])[:5]}")
        return
    cells = d.get("cells_diff", [])
    print(f"  Celle diverse: {len(cells)}")
    for c in cells[:10]:
        print(f"    · riga {c['row']} col '{c['col']}': "
              f"golden='{c['golden']}' actual='{c['actual']}'")
    if len(cells) > 10:
        print(f"    · ... e altre {len(cells) - 10}")


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Check regressione notturna QA-01")
    parser.add_argument("--date", type=str,
                        help="Check di una data specifica (YYYY-MM-DD)")
    parser.add_argument("--keep-db", action="store_true",
                        help="Non cancellare bgy_qa_test a fine esecuzione")
    parser.add_argument("--verbose", action="store_true",
                        help="Log dettagliato")
    parser.add_argument("--no-db", action="store_true",
                        help="Salta setup DB (usa il DB puntato dal config)")
    args = parser.parse_args()

    if not os.path.isdir(FIXTURES_DIR):
        logger.error(f"Cartella fixtures non trovata: {FIXTURES_DIR}")
        logger.error("Esegui prima: py -3.12 -m bgy_tools.qa_freeze --all")
        return 1

    if args.date:
        dates = [normalize_date(args.date)]
    else:
        dates = sorted([
            d for d in os.listdir(FIXTURES_DIR)
            if os.path.isdir(os.path.join(FIXTURES_DIR, d))
            and d[:2] == "20" and "-" in d
        ])

    if not dates or dates == [None]:
        logger.error("Nessuna fixture trovata.")
        return 1

    print()
    print("=" * 70)
    print(f"QA-01 — CHECK REGRESSIONE NOTTURNA")
    print("=" * 70)
    print(f"Fixture: {len(dates)} date → {dates}")
    print(f"Versione modulo: {get_report_night_version()}")
    print()

    cfg_orig = None
    # v1.0.1: db_created parte a False e diventa True subito dopo CREATE
    db_created = False
    try:
        cfg_orig = _read_config_db()
        user = cfg_orig.get("user", "bgy_user")
        password = cfg_orig.get("password", "")

        if not args.no_db:
            print(f"🔧 Setup DB test: {TEST_DB_NAME}")
            ok, msg = create_test_db(user)
            if not ok:
                logger.error(f"❌ {msg}")
                return 1
            db_created = True  # v1.0.1: dal prossimo errore, il finally droppa

            # Override config PRIMA di apply_schema (che legge dbname)
            cfg_orig = override_config_to_test_db()

            ok, msg = apply_schema_to_test_db(user, password)
            if not ok:
                logger.error(f"❌ apply_schema: {msg}")
                return 1
            print(f"   ✅ {msg}")

            # v1.0.1: applica schema anagrafiche (13 tabelle)
            ok, msg = apply_anagrafiche_schema_to_test_db(user, password)
            if not ok:
                logger.error(f"❌ Anagrafiche schema: {msg}")
                return 1
            print(f"   ✅ Anagrafiche schema (13 tabelle)")

            # v1.0.1: poi i dati
            ok, msg = apply_anagrafiche_to_test_db(user, password)
            if not ok:
                logger.error(f"❌ Anagrafiche dati: {msg}")
                return 1
            print(f"   ✅ Anagrafiche dati caricati")

        print()
        results = []
        for d in dates:
            print(f"▶️  {d} ... ", end="", flush=True)
            r = check_fixture(d, verbose=args.verbose)
            results.append(r)
            icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}.get(r["status"], "?")
            print(f"{icon} {r['status']}")
            if r["status"] != "PASS":
                print(f"     {r['reason']}")
                if r["status"] == "FAIL" and args.verbose:
                    print_diff_summary(r)

        print()
        print("=" * 70)
        print("RIEPILOGO")
        print("=" * 70)
        n_pass = sum(1 for r in results if r["status"] == "PASS")
        n_fail = sum(1 for r in results if r["status"] == "FAIL")
        n_skip = sum(1 for r in results if r["status"] == "SKIP")
        for r in results:
            icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}.get(r["status"], "?")
            print(f"  {icon} {r['date']}: {r['status']} — {r['reason']}")
        print()
        print(f"Totale: {n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP")
        print()

        return 0 if n_fail == 0 else 1

    finally:
        # Ripristino config SEMPRE
        if cfg_orig is not None:
            try:
                restore_config_db(cfg_orig)
                print("🔄 config_database.json ripristinato")
            except Exception as e:
                logger.error(f"❌ ERRORE RIPRISTINO CONFIG: {e}")
                logger.error(f"   Ripristina manualmente da E:\\BGY_Backup")

        # v1.0.1: droppa anche se il setup è fallito a metà
        if db_created and not args.keep_db:
            drop_test_db()
            print(f"🗑️  DB test {TEST_DB_NAME} eliminato")


if __name__ == "__main__":
    sys.exit(main())