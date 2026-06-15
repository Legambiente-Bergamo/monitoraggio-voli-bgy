#!/usr/bin/env python3
# bgy_master.py - Orchestratore sequenziale lineare per ambiente Cloud

import subprocess
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = "dati"
REPORT_DIR = "report"
SCREENSHOT_DIR = "screenshots"

def create_directories():
    for dir_name in [DATA_DIR, REPORT_DIR, SCREENSHOT_DIR]:
        Path(dir_name).mkdir(exist_ok=True)

def run_script(script_name, date_str):
    print(f"[MASTER] Avvio modulo: {script_name}")
    try:
        subprocess.run([sys.executable, script_name, date_str], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[MASTER] ⚠️ Errore modulo {script_name}: {e}")
        return False

def main():
    create_directories()
    date_str = datetime.now().strftime("%Y%m%d")
    print(f"[MASTER] --- AVVIO SESSIONE CAMPIONAMENTO RAPIDO CLOUD PER IL {date_str} ---")

    # Esecuzione dei tre moduli di cattura istantanea
    run_script("bgy_meteo.py", date_str)
    run_script("bgy_radar.py", date_str)
    run_script("bgy_sacbo_capture.py", date_str)
    
    print("[MASTER] ✅ Campionamento terminato. I dati intermedi sono stati scritti.")

if __name__ == "__main__":
    main()
