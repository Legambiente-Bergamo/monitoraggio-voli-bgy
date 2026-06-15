#!/usr/bin/env python3
# bgy_meteo.py - Dati METAR per LIME (Bergamo Orio al Serio) - Versione Cloud

import requests
import csv
import sys
import re
from datetime import datetime
from pathlib import Path

DATA_DIR = "dati"

def get_metar():
    url = "https://tgftp.nws.noaa.gov/data/observations/metar/stations/LIME.TXT"
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            raw = response.text.strip()
            wind_dir = None
            wind_speed = None
            
            wind_match = re.search(r'(\d{3})(\d{2})KT', raw)
            if wind_match:
                wind_dir = int(wind_match.group(1))
                wind_speed = int(wind_match.group(2))
            
            if wind_dir:
                if 250 <= wind_dir <= 310:
                    active_runway = "28"
                elif 70 <= wind_dir <= 130:
                    active_runway = "10"
                else:
                    active_runway = "variabile"
            else:
                active_runway = "ND"
                
            return {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'raw_metar': raw,
                'wind_direction': wind_dir if wind_dir else 0,
                'wind_speed_kt': wind_speed if wind_speed else 0,
                'active_runway': active_runway
            }
    except Exception as e:
        print(f"[METEO] Errore download: {e}")
        return None
    return None

def save_metar(data, date_str):
    if not data: return
    Path(DATA_DIR).mkdir(exist_ok=True)
    filename = Path(DATA_DIR) / f"meteo_{date_str}.csv"
    write_header = not filename.exists()
    
    with open(filename, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data.keys())
        if write_header:
            writer.writeheader()
        writer.writerow(data)
    print(f"[METEO] 💨 Vento: {data['wind_direction']}° {data['wind_speed_kt']}kt - Pista: {data['active_runway']}")

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    print(f"[METEO] Richiesta bollettino METAR per aeroporto LIME (BGY) il {date_str}...")
    metar_data = get_metar()
    if metar_data:
        save_metar(metar_data, date_str)
    else:
        print("[METEO] ⚠️ Server NOAA non raggiungibile, salto turno senza bloccare il workflow.")

if __name__ == "__main__":
    main()
