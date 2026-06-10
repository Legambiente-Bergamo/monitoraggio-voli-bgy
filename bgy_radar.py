#!/usr/bin/env python3
# bgy_radar.py - Rilevazione voli da MULTIPLE FONTI
# OpenSky + ADS-B Exchange + adsb.fi

import requests
import csv
import time
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

DATA_DIR = "dati"

# Cache per evitare duplicati
_seen_aircraft = {}
CACHE_TIMEOUT = 60  # secondi

def load_config():
    """Carica la configurazione"""
    config = {}
    try:
        with open("config.txt", 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and ':' in line:
                    if not line.startswith('CENTRALINE') and not line.startswith('COMPAGNIE'):
                        key, value = line.split(':', 1)
                        config[key.strip()] = value.strip()
        
        config['LAT_MIN'] = float(config.get('LAT_MIN', 45.60))
        config['LAT_MAX'] = float(config.get('LAT_MAX', 45.75))
        config['LON_MIN'] = float(config.get('LON_MIN', 9.60))
        config['LON_MAX'] = float(config.get('LON_MAX', 9.80))
        
        return config
    except Exception as e:
        print(f"[RADAR] ERRORE config: {e}")
        sys.exit(1)

def is_in_bbox(lat, lon, config):
    """Verifica se coordinate sono nell'area monitorata"""
    if not lat or not lon:
        return False
    return (config['LAT_MIN'] <= lat <= config['LAT_MAX'] and 
            config['LON_MIN'] <= lon <= config['LON_MAX'])

def get_opensky_data(config):
    """Fonte 1: OpenSky Network"""
    url = "https://opensky-network.org/api/states/all"
    params = {
        "lamin": config['LAT_MIN'],
        "lamax": config['LAT_MAX'],
        "lomin": config['LON_MIN'],
        "lomax": config['LON_MAX']
    }
    
    username = config.get('OPENSKY_USER', '')
    password = config.get('OPENSKY_PASS', '')
    
    try:
        auth = (username, password) if username and password else None
        response = requests.get(url, params=params, auth=auth, timeout=15)
        
        if response.status_code == 200:
            states = response.json().get('states', [])
            results = []
            for s in states:
                if s[1]:  # callsign presente
                    results.append({
                        'fonte': 'OpenSky',
                        'callsign': s[1].strip(),
                        'icao24': s[0],
                        'origin_country': s[2],
                        'latitude': s[5],
                        'longitude': s[6],
                        'altitude_m': s[7],
                        'velocity_kmh': s[9] * 3.6 if s[9] else 0,
                        'heading': s[10],
                        'on_ground': s[8]
                    })
            print(f"   [OpenSky] {len(results)} aerei")
            return results
    except Exception as e:
        print(f"   [OpenSky] ERRORE: {e}")
    return []

def get_adsb_fi_data(config):
    """Fonte 2: adsb.fi (gratuito, senza limiti)"""
    results = []
    
    # Costruisce bounding box per API
    url = f"https://opendata.adsb.fi/api/v3/lat/{config['LAT_MIN']}/lon/{config['LON_MIN']}/dist/30"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            aircraft = data.get('aircraft', [])
            
            for a in aircraft:
                lat = a.get('lat')
                lon = a.get('lon')
                if is_in_bbox(lat, lon, config):
                    results.append({
                        'fonte': 'adsb.fi',
                        'callsign': a.get('flight', '').strip(),
                        'icao24': a.get('hex', ''),
                        'origin_country': a.get('origin_country', ''),
                        'latitude': lat,
                        'longitude': lon,
                        'altitude_m': a.get('altitude'),
                        'velocity_kmh': a.get('speed', 0) * 1.852 if a.get('speed') else 0,
                        'heading': a.get('track'),
                        'on_ground': a.get('ground', False)
                    })
            print(f"   [adsb.fi] {len(results)} aerei")
    except Exception as e:
        print(f"   [adsb.fi] ERRORE: {e}")
    return results

def get_adsb_exchange_data(config):
    """Fonte 3: ADS-B Exchange (100 req/giorno)"""
    results = []
    
    # Bounding box in formato: minlat,minlon,maxlat,maxlon
    bbox = f"{config['LAT_MIN']},{config['LON_MIN']},{config['LAT_MAX']},{config['LON_MAX']}"
    url = f"https://adsbexchange.com/api/aircraft/bbox/{bbox}"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            aircraft = data.get('aircraft', [])
            
            for a in aircraft:
                results.append({
                    'fonte': 'ADS-B Exchange',
                    'callsign': a.get('flight', '').strip(),
                    'icao24': a.get('hex', ''),
                    'origin_country': a.get('origin_country', ''),
                    'latitude': a.get('lat'),
                    'longitude': a.get('lon'),
                    'altitude_m': a.get('altitude'),
                    'velocity_kmh': a.get('speed', 0) * 1.852 if a.get('speed') else 0,
                    'heading': a.get('track'),
                    'on_ground': a.get('ground', False)
                })
            print(f"   [ADS-B Exchange] {len(results)} aerei")
    except Exception as e:
        print(f"   [ADS-B Exchange] ERRORE: {e}")
    return results

def merge_results(results_by_fonte):
    """Fusione risultati da più fonti, eliminando duplicati"""
    merged = {}
    
    for fonte, results in results_by_fonte.items():
        for a in results:
            key = a['callsign'] or a['icao24']
            if not key:
                continue
            
            if key not in merged:
                merged[key] = a
            else:
                # Se già presente, unisci i dati (dai priorità a OpenSky per affidabilità)
                for field in ['latitude', 'longitude', 'altitude_m', 'velocity_kmh', 'heading']:
                    if merged[key].get(field) is None and a.get(field) is not None:
                        merged[key][field] = a[field]
    
    return list(merged.values())

def save_aircraft(aircraft, date_str, config):
    """Salva i dati in CSV con informazioni sulla fonte"""
    Path(DATA_DIR).mkdir(exist_ok=True)
    
    filename = Path(DATA_DIR) / f"radar_{date_str}.csv"
    write_header = not filename.exists()
    
    with open(filename, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow([
                'timestamp', 'fonte', 'callsign', 'icao24', 'origin_country',
                'latitude', 'longitude', 'altitude_m', 'velocity_kmh',
                'heading', 'on_ground'
            ])
        
        for a in aircraft:
            writer.writerow([
                datetime.now().isoformat(),
                a.get('fonte', ''),
                a.get('callsign', ''),
                a.get('icao24', ''),
                a.get('origin_country', ''),
                round(a.get('latitude', 0), 4) if a.get('latitude') else '',
                round(a.get('longitude', 0), 4) if a.get('longitude') else '',
                round(a.get('altitude_m', 0), 0) if a.get('altitude_m') else '',
                round(a.get('velocity_kmh', 0), 1) if a.get('velocity_kmh') else '',
                round(a.get('heading', 0), 0) if a.get('heading') else '',
                a.get('on_ground', False)
            ])
    
    print(f"\n[RADAR] TOTALE: {len(aircraft)} aerei unici salvati")

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    config = load_config()
    interval = 60  # 1 minuto
    
    print(f"\n{'='*50}")
    print(f"🛰️ RADAR MULTI-FONTE BGY")
    print(f"{'='*50}")
    print(f"Data: {date_str}")
    print(f"Intervallo: {interval} secondi")
    print(f"Area: {config['LAT_MIN']}°-{config['LAT_MAX']}N, {config['LON_MIN']}°-{config['LON_MAX']}E")
    print(f"{'='*50}\n")
    
    error_count = 0
    
    while True:
        try:
            print(f"\n⏰ {datetime.now().strftime('%H:%M:%S')} - Rilevamento...")
            
            # Interroga tutte le fonti
            results_by_fonte = {}
            
            # Fonte 1: OpenSky (primaria)
            results_by_fonte['OpenSky'] = get_opensky_data(config)
            
            # Fonte 2: adsb.fi (gratuita)
            results_by_fonte['adsb.fi'] = get_adsb_fi_data(config)
            
            # Fonte 3: ADS-B Exchange (se non abbiamo troppi dati)
            if len(results_by_fonte['OpenSky']) < 10:  # Solo se OpenSky ha pochi dati
                results_by_fonte['ADS-B Exchange'] = get_adsb_exchange_data(config)
            
            # Fusione risultati
            merged = merge_results(results_by_fonte)
            
            if merged:
                save_aircraft(merged, date_str, config)
                error_count = 0
            else:
                print("   ⚠️ Nessun aereo rilevato da nessuna fonte")
                error_count += 1
            
            if error_count > 10:
                print("   ⚠️ Troppi errori consecutivi, attesa 60s...")
                time.sleep(60)
                error_count = 0
            
            time.sleep(interval)
            
        except KeyboardInterrupt:
            print("\n[RADAR] Arresto manuale")
            break
        except Exception as e:
            print(f"   ❌ ERRORE: {e}")
            time.sleep(interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[RADAR] Arresto")