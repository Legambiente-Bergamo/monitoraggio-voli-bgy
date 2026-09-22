"""
rigenera_e_sync.py - Rigenera i report notturni e risincronizza il DB.

Per ogni data presente nel DB:
1. Verifica se esistono file raw (scan_YYYY-MM-DD_*.csv)
2. Rigenera il report notturno
3. Pulisce il DB per quella data
4. Risincronizza il DB

Uso:
    py -3.12 rigenera_e_sync.py
"""
import os
import sys
from pathlib import Path

from bgy_core import bgy_db, get_logger
from bgy_core.bgy_paths import RAW_DIR
from bgy_reports.bgy_report_night import generate_nightly_report

logger = get_logger("RigeneraSync")


def get_dates_in_db():
    """Ritorna lista date (YYYY-MM-DD) presenti nel DB, ordinata desc."""
    ok, rows = bgy_db.execute_query(
        "SELECT DISTINCT data_riferimento FROM nightly_reports "
        "ORDER BY data_riferimento DESC"
    )
    if not ok:
        return []
    return [r[0].isoformat() if hasattr(r[0], 'isoformat') else str(r[0]) for r in rows]


def has_raw_files(date_str):
    """Verifica se esistono file scan_YYYY-MM-DD_*.csv in RAW_DIR."""
    if not os.path.isdir(RAW_DIR):
        return False
    for f in os.listdir(RAW_DIR):
        if f.startswith(f"scan_{date_str}_") and f.endswith(".csv"):
            return True
    return False


def main():
    dates = get_dates_in_db()
    print(f"📅 Date nel DB: {len(dates)}")
    print()

    # Classifica per disponibilità raw
    with_raw = [d for d in dates if has_raw_files(d)]
    without_raw = [d for d in dates if not has_raw_files(d)]

    print(f"✅ Con file raw: {len(with_raw)}")
    print(f"❌ Senza file raw: {len(without_raw)}")
    if without_raw:
        print(f"   (non rigenerabili): {', '.join(without_raw)}")
    print()

    if not with_raw:
        print("⚠️  Nessuna data rigenerabile.")
        return

    # Rigenera + sync
    print("=" * 60)
    print("🔄 RIGENERAZIONE + SYNC")
    print("=" * 60)

    for i, date_str in enumerate(with_raw, 1):
        print(f"\n[{i}/{len(with_raw)}] {date_str}")

        # 1. Rigenera report
        try:
            path, msg = generate_nightly_report(date_str)
            print(f"   📄 {msg}")
        except Exception as e:
            print(f"   ❌ Errore rigenerazione: {e}")
            continue

        # 2. Pulisci DB
        ok, _ = bgy_db.execute_query(
            "DELETE FROM nightly_reports WHERE data_riferimento = %s",
            (date_str,),
            fetch=False
        )
        if not ok:
            print(f"   ⚠️  Errore DELETE DB")
            continue

        # 3. Risincronizza
        try:
            from bgy_core.bgy_db_migrate import migrate_date
            result = migrate_date(date_str)
            print(f"   💾 Sync DB: {result}")
        except ImportError:
            # Fallback: chiamata via subprocess
            import subprocess
            r = subprocess.run(
                [sys.executable, "-m", "bgy_core.bgy_db_migrate", "--date", date_str],
                capture_output=True, text=True
            )
            if r.returncode == 0:
                print(f"   💾 Sync DB: OK")
            else:
                print(f"   ❌ Sync DB: errore")
        except Exception as e:
            print(f"   ❌ Errore sync: {e}")

    # Report finale
    print()
    print("=" * 60)
    print("📊 VERIFICA FINALE")
    print("=" * 60)
    ok, rows = bgy_db.execute_query(
        "SELECT DISTINCT compagnia_aerea FROM nightly_reports "
        "WHERE compagnia_aerea LIKE 'Compagnia%%' ORDER BY 1"
    )
    if ok:
        print(f"Placeholder rimasti: {len(rows)}")
        for r in rows:
            print(f"   - {r[0]}")


if __name__ == "__main__":
    main()