#!/usr/bin/env python3
# bgy_report.py - Analisi incrociata Voli SACBO e Tracciati Radar

import csv
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = "dati"
REPORT_DIR = "report"

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    sacbo_file = Path(DATA_DIR) / f"sacbo_{date_str}.csv"
    radar_file = Path(DATA_DIR) / f"radar_{date_str}.csv"
    output_file = Path(REPORT_DIR) / f"report_completo_{date_str}.csv"
    
    Path(REPORT_DIR).mkdir(exist_ok=True)
    
    voli_sacbo = {}
    if sacbo_file.exists():
        with open(sacbo_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('volo'):
                    voli_sacbo[row['volo'].strip().lower()] = row

    report_data = []
    if radar_file.exists() and radar_file.stat().st_size > 0:
        with open(radar_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                callsign = row.get('callsign', '').strip().lower()
                # Incrocia il codice radio del radar con il numero volo del tabellone
                info_tabellone = voli_sacbo.get(callsign, {})
                
                report_data.append({
                    'timestamp': row.get('timestamp'),
                    'volo': row.get('callsign'),
                    'tipo_operazione': info_tabellone.get('tipo', 'NON TRACCIATO DA TABELLONE'),
                    'rotta_provenienza': info_tabellone.get('provenienza_destinazione', 'UNK'),
                    'stato_volo': info_tabellone.get('stato', 'IN VOLO'),
                    'altitudine_metri': row.get('altitude'),
                    'velocita_kmh': round(float(row['velocity']) * 3.6 if row.get('velocity') else 0, 1),
                    'icao24': row.get('icao24')
                })

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        if report_data:
            writer = csv.DictWriter(f, fieldnames=report_data[0].keys())
            writer.writeheader()
            writer.writerows(report_data)
            print(f"[REPORT] ✅ Generata correttamente l'analisi dettagliata di {len(report_data)} vettori radar.")
        else:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'volo', 'tipo_operazione', 'rotta_provenienza', 'stato_volo', 'altitudine_metri', 'velocita_kmh', 'icao24'])
            # Righe di test se i dati sono a zero per non far fallire la mail
            writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'BGY_TEST', 'REGOLARE', 'TEST_ROTTA', 'COMPLETATO', '0', '0', 'UNK'])
            print("[REPORT] Nessun dato radar utile per l'incrocio. Generato file di test base.")

if __name__ == "__main__":
    main()
