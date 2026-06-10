#!/usr/bin/env python3
# bgy_meteo.py - Dati METAR per LIME (Bergamo Orio al Serio)

import requests
import csv
import time
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = "dati"

def get_metar():
    """Scarica METAR da NOAA"""
    url = "https://tgftp.nws.noaa.gov/data/observations/metar/stations/LIME.TXT"
    
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            raw = response.text.strip()
            
            # Parsing base
            wind_dir = None
            wind_speed = None
            
            # Cerca pattern vento (es: 23010KT)
            import re
            wind_match = re.search(r'(\d{3})(\d{2})KT', raw)
            if wind_match:
                wind_dir = int(wind_match.group(1))
                wind_speed = int(wind_match.group(2))
            
            # Determina pista attiva
            if wind_dir:
                if 250 <= wind_dir <= 310:
                    active_runway = "28"  # Vento da ovest
                elif 70 <= wind_dir <= 130:
                    active_runway = "10"  # Vento da est
                else:
                    active_runway = "variabile"
            else:
                active_runway = "ND"
            
            return {
                'timestamp': datetime.now().isoformat(),
                'raw_metar': raw,
                'wind_direction': wind_dir,
                'wind_speed_kt': wind_speed,
                'active_runway': active_runway
            }
    except Exception as e:
        print(f"[METEO] Errore: {e}")
        return None

def save_metar(data, date_str):
    """Salva dati meteo"""
    if not data:
        return
    
    Path(DATA_DIR).mkdir(exist_ok=True)
    filename = Path(DATA_DIR) / f"meteo_{date_str}.csv"
    write_header = not filename.exists()
    
    with open(filename, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data.keys())
        if write_header:
            writer.writeheader()
        writer.writerow(data)
    
    print(f"[METEO] 💨 Vento: {data['wind_direction']}° {data['wind_speed_kt']}kt - Pista {data['active_runway']}")

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    
    # Carica intervallo da config
    interval = 1800  # default 30 min
    try:
        with open("config.txt", 'r') as f:
            for line in f:
                if 'INTERVALLO_METEO' in line:
                    interval = int(line.split(':')[1].strip())
                    break
    except:
        pass
    
    print(f"[METEO] Avviato - Data {date_str} - Intervallo {interval}s")
    
    while True:
        data = get_metar()
        if data:
            save_metar(data, date_str)
        time.sleep(interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[METEO] Arresto")