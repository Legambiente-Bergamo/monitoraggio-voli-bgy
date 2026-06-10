#!/usr/bin/env python3
# bgy_centralina_rumore.py - Calcolo rumore con firma acustica per modello aereo

import csv
import math
import sys
import os
from datetime import datetime
from pathlib import Path
from collections import defaultdict

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

DATA_DIR = "dati"
REPORT_DIR = "report"
CONFIG_FILE = "config.txt"

# Firma acustica stimata (dB standard a 1000 metri di quota/distanza tridimensionale)
FIRMA_ACUSTICA_MODELLI = {
    'B738': {'base_db': 82.0, 'tipo': 'Boeing 737-800 Standard'},
    'B737': {'base_db': 83.5, 'tipo': 'Boeing 737 Classic (Elevato impatto)'},
    'A320': {'base_db': 78.5, 'tipo': 'Airbus A320 Ceo'},
    'A321': {'base_db': 79.0, 'tipo': 'Airbus A321 Ceo'},
    'A20N': {'base_db': 73.0, 'tipo': 'Airbus A320 Neo (Nuova motorizzazione)'},
    'A21N': {'base_db': 74.0, 'tipo': 'Airbus A321 Neo (Silenzioso)'},
    'B752': {'base_db': 86.0, 'tipo': 'Boeing 757 Cargo (Molto rumoroso)'},
    'A306': {'base_db': 87.5, 'tipo': 'Airbus A300 Cargo (Forte impatto notturno)'},
    'C25A': {'base_db': 68.0, 'tipo': 'Business Jet Privato'},
    'P28A': {'base_db': 60.0, 'tipo': 'Aviazione Generale Leggera'},
    'DEFAULT': {'base_db': 80.0, 'tipo': 'Modello Standard'}
}

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def load_centraline():
    centraline = []
    reading = False
    if not os.path.exists(CONFIG_FILE):
        return []
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line == 'CENTRALINE:':
                reading = True
                continue
            if reading and ',' in line:
                parts = line.split(',')
                if len(parts) >= 3:
                    centraline.append({
                        'nome': parts[0].strip(),
                        'lat': float(parts[1].strip()),
                        'lon': float(parts[2].strip())
                    })
            elif reading and not line:
                break
    return centraline

def get_modello_da_config(icao24):
    if not os.path.exists(CONFIG_FILE):
        return 'DEFAULT'
    reading = False
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
    return 'DEFAULT'

def calculate_noise(dist_orizzontale_km, quota_metri, modello_icao):
    firma = FIRMA_ACUSTICA_MODELLI.get(modello_icao, FIRMA_ACUSTICA_MODELLI['DEFAULT'])
    db_base = firma['base_db']
    
    dist_verticale_km = quota_metri / 1000.0
    dist_3d_km = math.sqrt(dist_orizzontale_km**2 + dist_verticale_km**2)
    
    if dist_3d_km < 0.1:
        dist_3d_km = 0.1
        
    rumore_stimato = db_base - (20 * math.log10(dist_3d_km))
    if dist_3d_km > 1.5:
        rumore_stimato -= (dist_3d_km * 1.2) # Attenuazione atmosferica aggiuntiva
        
    return max(30.0, rumore_stimato)

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    radar_file = Path(DATA_DIR) / f"radar_{date_str}.csv"
    
    print(f"[RUMORE] Avvio elaborazione impatto acustico per {date_str}...")
    
    centraline = load_centraline()
    if not centraline or not radar_file.exists():
        print("[RUMORE] Database delle centraline o file dati radar mancanti.")
        return

    # Organizza le coordinate per singoli voli
    voli_punti = defaultdict(list)
    with open(radar_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('callsign'):
                voli_punti[row['callsign'].strip()].append(row)

    results = []

    for callsign, punti in voli_punti.items():
        icao24 = punti[0]['icao24']
        modello_icao = get_modello_da_config(icao24)
        
        for centrale in centraline:
            dist_minima = 999.0
            punto_critico = None
            
            for p in punti:
                try:
                    d = haversine(float(p['latitude']), float(p['longitude']), centrale['lat'], centrale['lon'])
                    if d < dist_minima:
                        dist_minima = d
                        punto_critico = p
                except:
                    continue
            
            # Limite massimo di calcolo impostato a 5 km
            if dist_minima <= 5.0 and punto_critico:
                quota = float(punto_critico['altitude']) if punto_critico['altitude'] else 300.0
                noise_db = calculate_noise(dist_minima, quota, modello_icao)
                
                results.append({
                    'timestamp': punto_critico['timestamp'].split('T')[-1][:8] if 'T' in punto_critico['timestamp'] else punto_critico['timestamp'],
                    'callsign': callsign,
                    'modello': modello_icao,
                    'descrizione_aereo': FIRMA_ACUSTICA_MODELLI.get(modello_icao, FIRMA_ACUSTICA_MODELLI['DEFAULT'])['tipo'],
                    'centralina': centrale['nome'],
                    'distanza_km': round(dist_minima, 3),
                    'altitudine_m': round(quota, 0),
                    'rumore_stimato_db': round(noise_db, 1),
                    'valutazione': "CRITICO (SFORAMENTO)" if noise_db >= 60.0 else "REGOLARE"
                })

    results.sort(key=lambda x: x['timestamp'])
    
    Path(REPORT_DIR).mkdir(exist_ok=True)
    output_file = Path(REPORT_DIR) / f"rumore_centraline_{date_str}.csv"
    
    if results:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        print(f"[RUMORE] ✅ Registro generato con successo per {len(results)} eventi di prossimità.")
    else:
        print("[RUMORE] Nessun volo intercettato nel raggio di monitoraggio delle centraline.")

if __name__ == "__main__":
    main()
