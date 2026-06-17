#!/usr/bin/env python3
import csv
import sys
import requests
from datetime import datetime
from pathlib import Path

DATA_DIR = "dati"
URL_ARRIVI = "https://www.milanbergamoairport.it/fids-servlet/fids?type=A&lang=it"
URL_PARTENZE = "https://www.milanbergamoairport.it/fids-servlet/fids?type=D&lang=it"

def fetch_flights(url, tipo_volo):
    flights = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            items = response.json().get('flights', []) or response.json().get('rows', []) or response.json()
            for item in items:
                if isinstance(item, dict):
                    flights.append({
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'tipo': tipo_volo,
                        'orario_previsto': item.get('scheduledTime') or item.get('ora') or item.get('time', '00:00'),
                        'volo': item.get('flightNumber') or item.get('volo') or item.get('code', 'UNK'),
                        'provenienza_destinazione': item.get('fromTo') or item.get('scalo') or item.get('city', 'UNK'),
                        'stato': item.get('status') or item.get('stato') or item.get('statusDesc', 'PROGRAMMATO')
                    })
    except Exception as e:
        print(f"[SACBO API] Errore {tipo_volo}: {e}")
    return flights

def save_to_csv(flights, date_str):
    if not flights: return
    Path(DATA_DIR).mkdir(exist_ok=True)
    file_path = Path(DATA_DIR) / f"sacbo_{date_str}.csv"
    file_exists = file_path.exists()
    with open(file_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=flights[0].keys())
        if not file_exists: writer.writeheader()
        writer.writerows(flights)

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    print(f"[SACBO API] Recupero tabellone per data: {date_str}")
    arrivi = fetch_flights(URL_ARRIVI, 'ARRIVO')
    partenze = fetch_flights(URL_PARTENZE, 'PARTENZA')
    totali = arrivi + partenze
    if totali:
        save_to_csv(totali, date_str)
        print(f"[SACBO API] ✅ Salvati {len(totali)} voli.")
    else:
        print("[SACBO API] ⚠️ Nessun dato ricevuto.")

if __name__ == "__main__":
    main()
