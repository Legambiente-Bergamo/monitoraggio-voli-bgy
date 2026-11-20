import os
import sys
import pandas as pd
import re
from collections import defaultdict

sys.path.insert(0, os.getcwd())
from bgy_core.bgy_paths import RAW_DIR, OUTPUT_CSV_DIR

TARGET_DATE = '2026-11-14'

def norm_cs(cs):
    if not cs: return ''
    return re.sub(r'\s+', '', str(cs)).upper()

def main():
    print(f"\n=== DIAGNOSTICA VOLI PERSI: {TARGET_DATE} ===\n")

    # FASE 1: File Grezzi
    scan_files = [f for f in os.listdir(RAW_DIR) if f.startswith(f"scan_{TARGET_DATE}_") and f.endswith(".csv")]
    
    raw_flights = set()
    for f in scan_files:
        try:
            df = pd.read_csv(os.path.join(RAW_DIR, f))
            for _, row in df.iterrows():
                cs = norm_cs(row.get('callsign_volo', ''))
                sched = str(row.get('orario_schedulato', '')).strip()
                tipo = str(row.get('tipo_movimento', '')).strip().upper()
                if cs and sched and tipo in ('D', 'A'):
                    raw_flights.add((cs, sched, tipo))
        except Exception:
            pass

    # FASE 2: Report Generato
    report_path = os.path.join(OUTPUT_CSV_DIR, f"report_h24_{TARGET_DATE}.csv")
    if not os.path.exists(report_path):
        return

    df_report = pd.read_csv(report_path)
    df_report_sched = df_report[df_report['is_scheduled'] == True]
    
    report_flights = set()
    for _, row in df_report_sched.iterrows():
        cs = norm_cs(row.get('callsign', ''))
        sched = str(row.get('orario_schedulato', '')).strip()
        tipo = str(row.get('direzione_sacbo', '')).strip().upper()
        if cs and sched and tipo in ('D', 'A'):
            report_flights.add((cs, sched, tipo))

    voli_persi = raw_flights - report_flights
    
    print(f"Voli unici nei grezzi: {len(raw_flights)}")
    print(f"Voli unici nel report: {len(report_flights)}")
    print(f"Voli presenti nei grezzi ma non nel report: {len(voli_persi)}\n")
    
    if voli_persi:
        print("--- ELENCO DEI VOLI PERSI ---")
        for v in sorted(voli_persi, key=lambda x: (x[1], x[2])):
            print(f"Direzione: {v[2]} | Callsign: {v[0]} | Orario Sched: {v[1]}")
    else:
        print("Nessun volo perso. Il report contiene tutti i voli unici dei grezzi.")

if __name__ == "__main__":
    main()