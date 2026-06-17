#!/usr/bin/env python3
# bgy_sacbo_capture.py - Versione Sessione Protetta Anti-Blocco

import csv
import sys
import requests
from datetime import datetime
from pathlib import Path

DATA_DIR = "dati"
URL_HOME = "https://www.milanbergamoairport.it/it/voli-tempo-reale/"
URL_ARRIVI = "https://www.milanbergamoairport.it/fids-servlet/fids?type=A&lang=it"
URL_PARTENZE = "https://www.milanbergamoairport.it/fids-servlet/fids?type=D&lang=it"

def fetch_flights_with_session():
    flights = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": URL_HOME
    }
    
    try:
        # Usa un'unica sessione per mantenere vivi i Cookie di autorizzazione
        session = requests.Session()
        print("[SACBO Session] Generazione cookie di sessione sulla home page...")
        session.get(URL_HOME, headers={"User-Agent": headers["User-Agent"]}, timeout=15)
        
        # Scarica gli Arrivi
        print("[SACBO Session] Scarico Arrivi...")
        r_arr = session.get(URL_ARRIVI, headers=headers, timeout=15)
        if r_arr.status_code == 200:
            items = r_arr.json().get('flights', []) or r_arr.json().get('rows', [])
            for item in items:
                if isinstance(item, dict):
                    flights.append(parse_flight(item, 'ARRIVO'))
                    
        # Scarica le Partenze
        print("[SACBO Session] Scarico Partenze...")
        r_dep = session.get(URL_PARTENZE, headers=headers, timeout=15)
        if r_dep.status_code == 200:
            items = r_dep.json().get('flights', []) or r_dep.json().get('rows', [])
            for item in items:
                if isinstance(item, dict):
                    flights.append(parse_flight(item, 'PARTENZA'))
                    
    except Exception as e:
        print(f"[SACBO Session] ❌ Errore critico durante la chiamata: {e}")
        
    return flights

def parse_flight(item, tipo_volo):
    return {
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'tipo': tipo_volo,
        'orario_previsto': item.get('scheduledTime') or item.get('ora') or item.get('time', '00:00'),
        'volo': item.get('flightNumber') or item.get('volo') or item.get('code', 'UNK'),
        'provenienza_destinazione': item.get('fromTo') or item.get('scalo') or item.get('city', 'UNK'),
        'stato': item.get('status') or item.get('stato') or item.get('statusDesc', 'PROGRAMMATO')
    }

def save_to_csv(flights, date_str):
    if not flights: return
    Path(DATA_DIR).mkdir(exist_ok=True)
    file_path = Path(DATA_DIR) / f"sacbo_{date_str}.csv"
    file_exists = file_path.exists()
    
    with open(file_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=flights[0].keys())
        if not file_exists:
            writer.writeheader()
        writer.writerows(flights)

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    print(f"[SACBO Session] Avvio estrazione per il {date_str}...")
    
    voli = fetch_flights_with_session()
    if voli:
        save_to_csv(voli, date_str)
        print(f"[SACBO Session] ✅ Salvati correttamente {len(voli)} voli totali in {DATA_DIR}/sacbo_{date_str}.csv")
    else:
        print("[SACBO Session] ⚠️ Nessun dato estratto dal tabellone. Creo record vuoto strutturato.")
        # Forza la creazione del file per evitare che bgy_report si blocchi
        save_to_csv([{
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'tipo': 'MONITOR',
            'orario_previsto': '00:00', 'volo': 'ASSENTE', 'provenienza_destinazione': 'UNK', 'stato': 'LOG_VUOTO'
        }], date_str)

if __name__ == "__main__":
    main()
