#!/usr/bin/env python3
# bgy_centralina_rumore.py - Stima acustica ed elaborazione sforamenti - Cloud Corretto

import csv
import math
import sys
import os
from datetime import datetime
from pathlib import Path
from collections import defaultdict

DATA_DIR = "dati"
REPORT_DIR = "report"
CONFIG_FILE = "config.txt"

FIRMA_ACUSTICA_MODELLI = {
    'B738': {'base_db': 82.0, 'tipo': 'Boeing 737-800 Standard'},
    'B737': {'base_db': 83.5, 'tipo': 'Boeing 737 Classic (Elevato impatto)'},
    'A320': {'base_db': 78.5, 'tipo': 'Airbus A320 Ceo'},
    'A321': {'base_db': 79.0, 'tipo': 'Airbus A321 Ceo'},
    'A20N': {'base_db': 73.0, 'tipo': 'Airbus A320 Neo (Silenzioso)'},
    'A21N': {'base_db': 74.0, 'tipo': 'Airbus A321 Neo (Nuova motorizzazione)'},
    'B752': {'base_db': 86.0, 'tipo': 'Boeing 757 Cargo (Forte impatto notturno)'},
    'A306': {'base_db': 87.5, 'tipo': 'Airbus A300 Cargo (Pesante)'},
    'C25A': {'base_db': 68.0, 'tipo': 'Business Jet Privato'},
    'DEFAULT': {'base_db': 80.0, 'tipo': 'Velivolo Standard'}
}

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    return R * 2 * math.asin(math.sqrt(math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2))

def load_centraline():
    # Ritorna le centraline di default per la bergamasca se config.txt non è accessibile
    default_centraline = [
        {'nome': 'Bergamo - Via San Bernardino', 'lat': 45.684, 'lon': 9.661},
        {'nome': 'Colognola IC Muzio', 'lat': 45.672, 'lon': 9.675},
        {'nome': 'Tre Cantoni - Ciserano', 'lat': 45.585, 'lon': 9.602}
    ]
    if not os.path.exists(CONFIG_FILE): return default_centraline
    centraline = []
    reading = False
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line == 'CENTRALINE:':
                    reading = True
                    continue
                if reading and ',' in line:
                    parts = line.split(',')
                    if len(parts) >= 3:
                        centraline.append({'nome': parts[0].strip(), 'lat': float(parts[1]), 'lon': float(parts[2])})
                elif reading and not line:
                    break
        return centraline if centraline else default_centraline
    except:
        return default_centraline

def get_modello_da_config(icao24):
    if not os.path.exists(CONFIG_FILE): return 'DEFAULT'
    reading = False
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line == 'MODELLI_AEREI:':
                    reading = True
                    continue
                if reading and ',' in line:
                    parts = line.split(',')
                    if parts[0].strip().lower() == icao24.lower() and len(parts) >= 3:
                        return parts[2].strip()
                elif reading and not line:
                    break
    except:
        pass
    return 'DEFAULT'

def calculate_noise(dist_orizzontale_km, quota_metri, modello_icao):
    firma = FIRMA_ACUSTICA_MODELLI.get(modello_icao, FIRMA_ACUSTICA_MODELLI['DEFAULT'])
    db_base = firma['base_db']
    dist_3d = math.sqrt(dist_orizzontale_km**2 + (quota_metri/1000.0)**2)
    if dist_3d < 0.1: dist_3d = 0.1
    rumore = db_base - (20 * math.log10(dist_3d))
    if dist_3d > 1.5:
        rumore -= (dist_3d * 1.2)
    return max(30.0, rumore)

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    radar_file = Path(DATA_DIR) / f"radar_{date_str}.csv"
    output_file = Path(REPORT_DIR) / f"rumore_centraline_{date_str}.csv"
    Path(REPORT_DIR).mkdir(exist_ok=True)

    # CORREZIONE BUG DI SINTASSI QUI (Utilizzo corretto di os.path.getsize)
    if not radar_file.exists() or os.path.getsize(str(radar_file)) == 0:
        print(f"[RUMORE] File {radar_file.name} vuoto o assente. Genero report vuoto preventivo.")
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'callsign', 'modello', 'descrizione_aereo', 'centralina', 'distanza_km', 'altitudine_m', 'rumore_stimato_db', 'valutazione'])
        return

    centraline = load_centraline()
    voli_punti = defaultdict(list)
    
    try:
        with open(radar_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('callsign') and row.get('latitude') and row.get('longitude'):
                    voli_punti[row['callsign'].strip()].append(row)
    except Exception as e:
        print(f"[RUMORE] Errore lettura file radar: {e}")

    results = []
    for callsign, punti in voli_punti.items():
        if not punti: continue
        icao24 = punti[0].get('icao24', 'UNK')
        modello = get_modello_da_config(icao24)
        for centrale in centraline:
            dist_min = 999.0
            punto_critico = None
            for p in punti:
                try:
                    d = haversine(float(p['latitude']), float(p['longitude']), centrale['lat'], centrale['lon'])
                    if d < dist_min:
                        dist_min = d
                        punto_critico = p
                except: continue
                
            if dist_min <= 5.0 and punto_critico:
                try:
                    quota = float(punto_critico['altitude']) if punto_critico['altitude'] else 300.0
                    noise_db = calculate_noise(dist_min, quota, modello)
                    results.append({
                        'timestamp': punto_critico['timestamp'].split('T')[-1][:8],
                        'callsign': callsign, 'modello': modello,
                        'descrizione_aereo': FIRMA_ACUSTICA_MODELLI.get(modello, FIRMA_ACUSTICA_MODELLI['DEFAULT'])['tipo'],
                        'centralina': centrale['nome'], 'distanza_km': round(dist_min, 3),
                        'altitudine_m': round(quota, 0), 'rumore_stimato_db': round(noise_db, 1),
                        'valutazione': "CRITICO (SFORAMENTO)" if noise_db >= 60.0 else "REGOLARE"
                    })
                except: continue

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        if results:
            results.sort(key=lambda x: x['timestamp'])
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
            print(f"[RUMORE] ✅ Generato report acustico con {len(results)} intercettazioni vicine alle centraline.")
        else:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'callsign', 'modello', 'descrizione_aereo', 'centralina', 'distanza_km', 'altitudine_m', 'rumore_stimato_db', 'valutazione'])
            print("[RUMORE] Nessun volo sotto la soglia dei 5 km dalle centraline, file salvato come regolare.")

if __name__ == "__main__":
    main()
