#!/usr/bin/env python3
# bgy_summary.py - Genera il riassunto testuale della notte per Legambiente

import csv
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = "dati"
REPORT_DIR = "report"

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    report_completo = Path(REPORT_DIR) / f"report_completo_{date_str}.csv"
    rumore_file = Path(REPORT_DIR) / f"rumore_centraline_{date_str}.csv"
    output_txt = Path(REPORT_DIR) / f"riassunto_notte_{date_str}.txt"
    
    total_punti_radar = 0
    voli_unici = set()
    sforamenti_totali = 0
    sforamenti_per_centralina = {}
    
    # Analisi report completo (Voli)
    if report_completo.exists() and report_completo.stat().st_size > 0:
        with open(report_completo, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_punti_radar += 1
                if row.get('volo') and row['volo'] != 'BGY_TEST':
                    voli_unici.add(row['volo'].strip())

    # Analisi rumore (Sforamenti acustici)
    if rumore_file.exists() and rumore_file.stat().st_size > 0:
        with open(rumore_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('valutazione') == 'CRITICO (SFORAMENTO)':
                    sforamenti_totali += 1
                    centr = row.get('centralina', 'Sconosciuta')
                    sforamenti_per_centralina[centr] = sforamenti_per_centralina.get(centr, 0) + 1

    # Formattazione del testo del riassunto
    data_it = datetime.strptime(date_str, "%Y%m%d").strftime("%d/%m/%Y")
    linee = [
        f"==================================================",
        f"📊 DIARIO DI MONITORAGGIO NOTTURNO - BGY ORIO",
        f"Report della notte: {data_it}",
        f"==================================================\n",
        f"✈️ TRAFFICO AEREO RILEVATO:",
        f"  - Velivoli unici tracciati dal radar: {len(voli_unici)}",
        f"  - Campionamenti di posizione registrati: {total_punti_radar}\n",
        f"🔊 IMPATTO ACUSTICO STIMATO (Soglia > 60 dB):",
        f"  - Eventi di sforamento totali calcolati: {sforamenti_totali}"
    ]
    
    if sforamenti_totali > 0:
        linee.append("  - Sforamenti per singola centralina ARPA:")
        for cb, count in sforamenti_per_centralina.items():
            linee.append(f"    * {cb}: {count} passaggi critici")
    else:
        linee.append("  - ✅ Nessuno sforamento teorico critico sopra i 60 dB calcolato nei punti sensibili.")
        
    linee.extend([
        f"\n--------------------------------------------------",
        f"Generato automaticamente dal Bot Ambientale Legambiente Bergamo.",
        f"I file CSV di dettaglio sono disponibili nella cartella 'report/'."
    ])
    
    # Scrittura del file di testo
    with open(output_txt, 'w', encoding='utf-8') as f:
        f.write("\n".join(linee))
    
    print(f"[SUMMARY] ✅ Generato riassunto testuale leggibile in {output_txt}")

if __name__ == "__main__":
    main()
