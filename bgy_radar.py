#!/usr/bin/env python3
import requests
import csv
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = "dati"
LOG_FILE = "report/diario_operazioni.log"
LAT_MIN, LAT_MAX = 45.55, 45.78
LON_MIN, LON_MAX = 9.50, 9.90

def scrivi_log(testo):
    ora = datetime.now().strftime("%H:%M:%S")
    Path("report").mkdir(exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ora}][RADAR] {testo}\n")

def get_opensky_data():
    url = "https://opensky-network.org/api/states/all"
    params = {'lamin': LAT_MIN, 'lamax': LAT_MAX, 'lomin': LON_MIN, 'lomax': LON_MAX}
    response = requests.get(url, params=params, timeout=12)
    if response.status_code == 200:
        return response.json().get('states', []) or []
    raise Exception(f"OpenSky status {response.status_code}")

def get_adsb_fi_data():
    url = "https://opendata.adsb.fi/api/v2/lat/45.667/lon/9.700/dist/20"
    response = requests.get(url, timeout=12)
    if response.status_code == 200:
        return response.json().get('ac', []) or []
    raise Exception(f"ADSB.fi status {response.status_code}")

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    Path(DATA_DIR).mkdir(exist_ok=True)
    filename = Path(DATA_DIR) / f"radar_{date_str}.csv"
    
    opensky_states, adsb_ac = [], []
    errori = []

    try:
        opensky_states = get_opensky_data()
    except Exception as e:
        errori.append(f"OpenSky fallito ({e})")

    try:
        adsb_ac = get_adsb_fi_data()
    except Exception as e:
        errori.append(f"ADSB.fi fallito ({e})")

    # Fusione dati
    movements = []
    now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    seen_icaos = set()
    
    for s in opensky_states:
        if s[5] and s[6]:
            icao = s[0].strip().lower()
            seen_icaos.add(icao)
            movements.append({
                'timestamp': now_str, 'icao24': s[0].strip(), 'callsign': s[1].strip() if s[1] else 'UNK',
                'latitude': s[6], 'longitude': s[5], 'altitude': s[7] if s[7] else 0,
                'velocity': s[9] if s[9] else 0, 'heading': s[10] if s[10] else 0, 'onground': s[8]
            })
            
    for ac in adsb_ac:
        icao = ac.get('hex', '').strip().lower()
        if icao and icao not in seen_icaos and ac.get('lat') and ac.get('lon'):
            seen_icaos.add(icao)
            movements.append({
                'timestamp': now_str, 'icao24': ac.get('hex', '').strip(), 'callsign': ac.get('flight', 'UNK').strip(),
                'latitude': ac.get('lat'), 'longitude': ac.get('lon'),
                'altitude': int(ac.get('alt_baro', 0)) * 0.3048 if ac.get('alt_baro') else 0,
                'velocity': int(ac.get('gs', 0)) * 0.514 if ac.get('gs') else 0,
                'heading': ac.get('track', 0), 'onground': ac.get('gs', 0) < 10
            })

    if movements:
        write_header = not filename.exists()
        with open(filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=movements[0].keys())
            if write_header: writer.writeheader()
            writer.writerows(movements)
        scrivi_log(f"✅ SUCCESS: Rilevati {len(movements)} vettori radar attivi.")
    else:
        if errori:
            scrivi_log(f"❌ ERROR: Nessun dato radar salvato. Dettagli: {', '.join(errori)}")
        else:
            scrivi_log("✅ SUCCESS: Server online, ma 0 aerei presenti nel raggio di Bergamo in questo minuto.")

if __name__ == "__main__":
    main()
