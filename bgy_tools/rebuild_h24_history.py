"""
bgy_tools/rebuild_h24_history.py
Rigenera e reimporta i report H24 per tutto lo storico (dal 30/09 a oggi).
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.getcwd())
from bgy_reports.bgy_report_h24 import generate_h24_report
from bgy_core import bgy_db
import subprocess

def main():
    apply = '--apply' in sys.argv
    start_date = datetime.strptime('2026-09-30', '%Y-%m-%d')
    end_date = datetime.strptime('2026-11-15', '%Y-%m-%d')
    
    date_list = []
    curr = start_date
    while curr <= end_date:
        date_list.append(curr.strftime('%Y-%m-%d'))
        curr += timedelta(days=1)
        
    print(f"\n=== REBUILD H24 STORICO: {len(date_list)} giorni ===")
    if not apply:
        print("DRY-RUN: verranno rigenerate le seguenti date:")
        print(", ".join(date_list))
        print("\nEsegui con --apply per rigenerare, reimportare e ricalcolare.")
        return

    print("Fase 1: Rigenerazione CSV e reimport forzato...")
    success_count = 0
    error_count = 0
    
    for d in date_list:
        try:
            print(f"\n--- Elaborazione {d} ---")
            # 1. Rigenera il CSV
            path, msg = generate_h24_report(d)
            if not path:
                print(f"  ERRORE: {msg}")
                error_count += 1
                continue
                
            # 2. Importa forzatamente nel DB
            cmd = f"py -3.12 -m bgy_core.bgy_db_migrate --date {d} --force"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                success_count += 1
                print(f"  ✅ {d} completato.")
            else:
                error_count += 1
                print(f"  ❌ Errore reimport {d}: {result.stderr[:200]}")
                
        except Exception as e:
            error_count += 1
            print(f"  ❌ Eccezione su {d}: {e}")
            
    print(f"\n=== COMPLETATO: {success_count} successi, {error_count} errori ===")

if __name__ == '__main__':
    main()