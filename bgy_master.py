#!/usr/bin/env python3
# bgy_master.py - Orchestratore ottimizzato per l'ambiente Cloud GitHub Actions

import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

CONFIG_FILE = "config.txt"
DATA_DIR = "dati"
REPORT_DIR = "report"
SCREENSHOT_DIR = "screenshots"

def create_directories():
    for dir_name in [DATA_DIR, REPORT_DIR, SCREENSHOT_DIR]:
        Path(dir_name).mkdir(exist_ok=True)

def run_script(script_name, date_str):
    print(f"[MASTER] Avvio esecuzione modulo: {script_name}")
    try:
        # Passa la data corrente come argomento allo script figlio
        result = subprocess.run([sys.executable, script_name, date_str], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[MASTER] ⚠️ Errore durante l'esecuzione di {script_name}: {e}")
        return False

def main():
    create_directories()
    date_str = datetime.now().strftime("%Y%m%d")
    print(f"[MASTER] --- AVVIO SESSIONE DI MONITORAGGIO CLOUD PER IL {date_str} ---")

    # 1. Cattura dati meteo e calcolo direzione pista attiva
    run_script("bgy_meteo.py", date_str)

    # 2. Cattura voli radar ADS-B
    run_script("bgy_radar.py", date_str)

    # 3. Scraping e screenshot tabellone SACBO
    run_script("bgy_sacbo_capture.py", date_str)

    print("[MASTER] Cattura dati completata. Avvio generazione reportistica...")

    # 4. Generazione report statistico voli e incrocio dati
    run_script("bgy_report.py", date_str)
    
    if os.path.exists("bgy_report_vettori.py"):
        run_script("bgy_report_vettori.py", date_str)

    # 5. Algoritmo avanzato di stima acustica per modello aereo su centraline ARPA
    run_script("bgy_centralina_rumore.py", date_str)

    print(f"[MASTER] ✅ Sessione completata con successo. I file sono pronti per il caricamento.")

if __name__ == "__main__":
    main()
