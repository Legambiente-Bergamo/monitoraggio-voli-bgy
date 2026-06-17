#!/usr/bin/env python3
import requests
import csv
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = "dati"
URL_METEO = "https://api.open-meteo.com/v1/forecast?latitude=45.667&longitude=9.700&current=temperature_2m,relative_humidity_2m,weather_code,cloud_cover,wind_speed_10m,wind_direction_10m&timezone=Europe%2FRome"

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    Path(DATA_DIR).mkdir(exist_ok=True)
    filename = Path(DATA_DIR) / f"meteo_{date_str}.csv"
    try:
        response = requests.get(URL_METEO, timeout=10)
        if response.status_code == 200:
            current = response.json().get('current', {})
            data = {
                'timestamp': current.get('time', datetime.now().strftime("%Y-%m-%dT%H:%M")),
                'temperatura_c': current.get('temperature_2m'),
                'umidita_percento': current.get('relative_humidity_2m'),
                'copertura_nuvolosa': current.get('cloud_cover'),
                'velocita_vento_kmh': current.get('wind_speed_10m'),
                'direzione_vento_gradi': current.get('wind_direction_10m')
            }
            write_header = not filename.exists()
            with open(filename, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=data.keys())
                if write_header: writer.writeheader()
                writer.writerow(data)
            print("[METEO] ✅ Dati meteo registrati con successo.")
    except Exception as e:
        print(f"[METEO] Errore: {e}")

if __name__ == "__main__":
    main()
