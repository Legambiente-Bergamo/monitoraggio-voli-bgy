#!/usr/bin/env python3
# bgy_radar.py - Rilevazione voli da fonti multiple - Versione Cloud

import requests
import csv
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = "dati"

def load_config():
    config = {}
    try:
        with open("config.txt", 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and ':' in line:
                    if not line.startswith(('CENTRALINE', 'COMPAGNIE', 'AEROPORTI', 'MODELLI_AEREI')):
                        key, value = line.split(':', 1)
                        config[key.strip()] = value.strip()
        config['LAT_MIN'] = float(config.get('LAT_MIN', 45.60))
        config['LAT_MAX'] = float(config.get('LAT_MAX', 45.75))
        config['LON_MIN'] = float(config.get('LON_MIN', 9.60))
        config['LON_MAX'] = float(config.get('LON_MAX', 9.80))
        return config
    except Exception as e:
        print(f"[RADAR] Errore lettura config: {e}")
        return {'LAT_MIN': 45.60, 'LAT_MAX': 45.75, 'LON_MIN': 9.60, 'LON_MAX': 9.80}

def get_opensky_data(config):
    url = "https://opensky-network.org/api/states/all"
    params = {
        'lamin': config['LAT_MIN'], 'lamax': config['LAT_MAX'],
        'lomin': config['LON_MIN'], 'lomax': config['LON_MAX']
    }
    user = config.get('OPENSKY_USER')
    password = config.get('OPENSKY_PASS')
    auth = (user, password) if user and password else None
    try:
        response = requests.get(url, params=params, auth=auth, timeout=20)
        if response.status_code == 200:
            return response.json().get('states', []) or []
    except:
        pass
    return []

def get_adsb_fi_data(config):
    url = f"https://opendata.adsb.fi/api/v2/lat/{config.get('BGY_LAT', 45.667)}/lon/{config.get('BGY_LON', 9.700)}/dist/15"
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
    
    for s in opensky_states:
        if s[5] and s[6]:
            movements.append({
                'timestamp': now_str, 'icao24': s[0].strip(), 'callsign': s[1].strip() if s[0] else 'UNK',
                'latitude': s[6], 'longitude': s[5], 'altitude': s[7] if s[7] else 0,
                'velocity': s[9] if s[9] else 0, 'heading': s[10] if s[10] else 0, 'onground': s[8]
            })
            
    seen_icaos = {m['icao24'] for m in movements}
    for ac in adsb_ac:
        icao = ac.get('hex', '').strip()
        if icao and icao not in seen_icaos and ac.get('lat') and ac.get('lon'):
            movements.append({
                'timestamp': now_str, 'icao24': icao, 'callsign': ac.get('flight', 'UNK').strip(),
                'latitude': ac.get('lat'), 'longitude': ac.get('lon'),
                'altitude': ac.get('alt_baro', 0) * 0.3048,
                'velocity': ac.get('gs', 0) * 0.514,
                'heading': ac.get('track', 0), 'onground': ac.get('gs', 0) < 5
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
    print(f"[RADAR] Istantanea ADS-B per la data: {date_str}")
    config = load_config()
    op_data = get_opensky_data(config)
    fi_data = get_adsb_fi_data(config)
    merged = merge_and_format(op_data, fi_data)
    
    if merged:
        save_aircraft(merged, date_str)
        print(f"[RADAR] ✅ Salvati {len(merged)} vettori.")
    else:
        print("[RADAR] Mappa aerea momentaneamente vuota.")

if __name__ == "__main__":
    main()
