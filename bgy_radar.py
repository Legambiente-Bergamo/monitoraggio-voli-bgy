#!/usr/bin/env python3
# bgy_radar.py - Rilevazione voli potenziata per ambiente Cloud (Coordinate Hardcoded)

import requests
import csv
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = "dati"

# Coordinate fisse area Bergamo (BGY) per evitare problemi di lettura config.txt
LAT_MIN = 45.55
LAT_MAX = 45.78
LON_MIN = 9.50
LON_MAX = 9.90

def get_opensky_data():
    url = "https://opensky-network.org/api/states/all"
    params = {'lamin': LAT_MIN, 'lamax': LAT_MAX, 'lomin': LON_MIN, 'lomax': LON_MAX}
    try:
        # Tentativo senza autenticazione (richiesta pubblica generica)
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            return response.json().get('states', []) or []
    except:
        pass
    return []

def get_adsb_fi_data():
    # API pubblica geografica centrata sulla pista di Orio al Serio
    url = "https://opendata.adsb.fi/api/v2/lat/45.667/lon/9.700/dist/20"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return response.json().get('ac', []) or []
    except:
        pass
    return []

def merge_and_format(opensky_states, adsb_ac):
    movements = []
    now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    seen_icaos = set()
    
    # 1. Elaborazione dati OpenSky
    for s in opensky_states:
        if s[5] and s[6]: # Verifica che ci siano lat e lon
            icao = s[0].strip().lower()
            seen_icaos.add(icao)
            movements.append({
                'timestamp': now_str, 
                'icao24': s[0].strip(), 
                'callsign': s[1].strip() if s[1] else 'UNK',
                'latitude': s[6], 
                'longitude': s[5], 
                'altitude': s[7] if s[7] else 0,
                'velocity': s[9] if s[9] else 0, 
                'heading': s[10] if s[10] else 0, 
                'onground': s[8]
            })
            
    # 2. Integrazione dati ADSB.fi (evitando duplicati)
    for ac in adsb_ac:
        icao = ac.get('hex', '').strip().lower()
        if icao and icao not in seen_icaos and ac.get('lat') and ac.get('lon'):
            seen_icaos.add(icao)
            movements.append({
                'timestamp': now_str, 
                'icao24': ac.get('hex', '').strip(), 
                'callsign': ac.get('flight', 'UNK').strip(),
                'latitude': ac.get('lat'), 
                'longitude': ac.get('lon'),
                'altitude': int(ac.get('alt_baro', 0)) * 0.3048 if ac.get('alt_baro') else 0, # Converte piedi in metri
                'velocity': int(ac.get('gs', 0)) * 0.514 if ac.get('gs') else 0, # Nodi in m/s
                'heading': ac.get('track', 0), 
                'onground': ac.get('gs', 0) < 10 if ac.get('gs') else False
            })
    return movements

def save_aircraft(data, date_str):
    if not data: return
    Path(DATA_DIR).mkdir(exist_ok=True)
    filename = Path(DATA_DIR) / f"radar_{date_str}.csv"
    write_header = not filename.exists()
    
    with open(filename, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        if write_header:
            writer.writeheader()
        writer.writerows(data)

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    print(f"[RADAR] Istantanea dello spazio aereo BGY per la data: {date_str}")
    
    op_data = get_opensky_data()
    fi_data = get_adsb_fi_data()
    merged = merge_and_format(op_data, fi_data)
    
    if merged:
        save_aircraft(merged, date_str)
        print(f"[RADAR] ✅ Salvati correttamente {len(merged)} vettori in volo.")
    else:
        print("[RADAR] ⚠️ Nessun vettore intercettato in questo turno. Invoco fallback vuoto per sicurezza.")
        # Crea comunque il file con intestazione per non far fallire i report successivi
        filename = Path(DATA_DIR) / f"radar_{date_str}.csv"
        if not filename.exists():
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'icao24', 'callsign', 'latitude', 'longitude', 'altitude', 'velocity', 'heading', 'onground'])

if __name__ == "__main__":
    main()
