#!/usr/bin/env python3
# bgy_report.py - Report integrato SACBO + Radar
# Versione stabile e funzionante

import csv
import math
import sys
import os
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# ============================================================
# CONFIGURAZIONE
# ============================================================

DATA_DIR = "dati"
REPORT_DIR = "report"
CONFIG_FILE = "config.txt"

# Coordinate aeroporto BGY
BGY_LAT = 45.667
BGY_LON = 9.700

# ============================================================
# FUNZIONI DI UTILITA
# ============================================================

def haversine(lat1, lon1, lat2, lon2):
    """Distanza in km tra due coordinate"""
    R = 6371
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def get_airline_from_callsign(callsign):
    """Identifica compagnia dal prefisso del callsign"""
    prefix = ''.join([c for c in callsign if c.isalpha()])[:3]
    
    airlines = {
        'RYR': 'Ryanair (Irlanda)',
        'WZZ': 'Wizz Air (Ungheria)',
        'WMT': 'Wizz Air Malta (Malta)',
        'EZY': 'EasyJet (Regno Unito)',
        'VND': 'Air Dolomiti (Italia)',
        'DLH': 'Lufthansa (Germania)',
        'AFR': 'Air France (Francia)',
        'KLM': 'KLM (Paesi Bassi)',
        'BAW': 'British Airways (Regno Unito)',
        'IBE': 'Iberia (Spagna)',
        'SAS': 'SAS (Svezia)',
        'UAL': 'United Airlines (USA)',
        'DHK': 'DHL Air (Regno Unito)',
        'FDX': 'FedEx Express (USA)',
        'UPS': 'UPS Airlines (USA)',
        'NO': 'Neos Air (Italia)',
        'H7': 'HiSky (Romania)',
        'W6': 'Wizz Air (Ungheria)',
        'FR': 'Ryanair (Irlanda)',
        '3O': 'Air Arabia Maroc (Marocco)',
        'DY': 'Norwegian (Norvegia)',
        'VF': 'AJet (Turchia)',
        'PC': 'Pegasus Airlines (Turchia)',
        'AZ': 'ITA Airways (Italia)',
    }
    
    return airlines.get(prefix, 'Compagnia sconosciuta')

def get_aircraft_model_from_callsign(callsign):
    """Ottiene modello tipico per compagnia"""
    prefix = ''.join([c for c in callsign if c.isalpha()])[:3]
    
    models = {
        'RYR': 'Boeing 737-800',
        'WZZ': 'Airbus A320/A321',
        'WMT': 'Airbus A320/A321',
        'EZY': 'Airbus A320',
        'VND': 'Embraer E195',
        'DLH': 'Airbus A320',
        'AFR': 'Airbus A320',
        'KLM': 'Boeing 737-800',
        'BAW': 'Airbus A320',
        'NO': 'Boeing 787',
        'H7': 'Airbus A320',
        'W6': 'Airbus A320',
        'FR': 'Boeing 737-800',
        'DY': 'Boeing 737-800',
        'PC': 'Airbus A320',
        'AZ': 'Airbus A220',
    }
    
    return models.get(prefix, 'Modello non identificato')

def determine_movement(points):
    """Determina se e' decollo o atterraggio"""
    if len(points) < 2:
        return None
    
    points.sort(key=lambda x: x['timestamp'])
    alt_start = points[0]['altitude']
    alt_end = points[-1]['altitude']
    alt_diff = alt_end - alt_start
    
    if alt_diff > 50:
        return "DECOLLO"
    elif alt_diff < -50:
        return "ATTERRAGGIO"
    return None

def determine_runway(points):
    """Determina pista utilizzata"""
    min_dist = float('inf')
    closest = None
    for p in points:
        dist = haversine(p['latitude'], p['longitude'], BGY_LAT, BGY_LON)
        if dist < min_dist:
            min_dist = dist
            closest = p
    
    if closest:
        lon = closest['longitude']
        if lon < 9.68:
            return "28", "approccio da Ovest (verso Bergamo)"
        elif lon > 9.72:
            return "10", "approccio da Est (verso Seriate)"
    return "ND", "dati insufficienti"

def calculate_noise(points):
    """Calcola rumore per centraline"""
    centraline = {
        'Orio al Serio Largo XXV Aprile': (45.66806, 9.69167),
        'Bergamo Colognola Via Linneo': (45.67639, 9.67083),
        'Bergamo Campagnola Via Quasimodo': (45.67917, 9.68194),
        'Azzano S. Paolo Via XXIV Maggio': (45.66111, 9.67222),
        'Bagnatica Via delle Groane': (45.65417, 9.78056),
        'Seriate Cassinone Via Basse': (45.65694, 9.76111),
        'Grassobbio Via Lombardia': (45.64722, 9.72222),
    }
    
    results = []
    for name, (lat, lon) in centraline.items():
        min_dist = float('inf')
        min_alt = float('inf')
        for p in points:
            dist = haversine(p['latitude'], p['longitude'], lat, lon)
            if dist < min_dist:
                min_dist = dist
                min_alt = p['altitude']
        
        if min_dist < 10:
            if min_alt < 300:
                rumore = 92 - (20 * math.log10(max(min_dist, 0.3)))
            elif min_alt < 1000:
                rumore = 87 - (20 * math.log10(max(min_dist, 0.3)))
            else:
                rumore = 78 - (20 * math.log10(max(min_dist, 0.3)))
            
            rumore = max(40, min(rumore, 100))
            valutazione = "ELEVATO" if rumore > 80 else "MEDIO" if rumore > 65 else "BASSO"
            
            results.append({
                'centralina': name,
                'distanza_km': round(min_dist, 2),
                'rumore_db': round(rumore, 1),
                'valutazione': valutazione
            })
    return sorted(results, key=lambda x: x['rumore_db'], reverse=True)

# ============================================================
# CARICAMENTO DATI
# ============================================================

def load_radar_data(date_str):
    """Carica dati radar"""
    filename = Path(DATA_DIR) / f"radar_{date_str}.csv"
    if not filename.exists():
        print(f"   File radar non trovato: {filename}")
        return []
    
    data = []
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lat = float(row['latitude']) if row['latitude'] else 0
                lon = float(row['longitude']) if row['longitude'] else 0
                
                # Correggi coordinate se invertite
                if 45.5 <= lat <= 45.8 and 9.5 <= lon <= 9.9:
                    pass
                elif 45.5 <= lon <= 45.8 and 9.5 <= lat <= 9.9:
                    lat, lon = lon, lat
                else:
                    continue
                
                data.append({
                    'timestamp': datetime.fromisoformat(row['timestamp']),
                    'callsign': row['callsign'].strip(),
                    'altitude': float(row['altitude_m']) if row['altitude_m'] else 0,
                    'latitude': lat,
                    'longitude': lon,
                    'origin_country': row['origin_country']
                })
            except Exception as e:
                continue
    return data

def load_sacbo_data(date_str):
    """Carica dati SACBO"""
    filename = Path(DATA_DIR) / f"sacbo_{date_str}.csv"
    if not filename.exists():
        print(f"   File SACBO non trovato: {filename}")
        return []
    
    data = []
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                data.append({
                    'timestamp': datetime.fromisoformat(row['timestamp']),
                    'tipo': row['tipo_volo'],
                    'numero_volo': row['numero_volo'].replace(' ', ''),
                    'destinazione': row['destinazione'].strip(),
                    'orario': row['orario_programmato'],
                    'stato': row['stato']
                })
            except Exception as e:
                continue
    return data

def extract_time(orario_str):
    """Estrae HH:MM dalla stringa orario"""
    if not orario_str:
        return None
    if len(orario_str) >= 5:
        return orario_str[:5]
    return None

# ============================================================
# FUNZIONE PRINCIPALE
# ============================================================

def generate_report(date_str):
    """Genera report completo"""
    
    # Crea directory report
    Path(REPORT_DIR).mkdir(exist_ok=True)
    
    print(f"\n" + "="*60)
    print(f"REPORT MONITORAGGIO BGY - {date_str[:4]}/{date_str[4:6]}/{date_str[6:8]}")
    print("="*60)
    
    # Carica dati
    radar_data = load_radar_data(date_str)
    sacbo_data = load_sacbo_data(date_str)
    
    print(f"   Radar: {len(radar_data)} rilevamenti")
    print(f"   SACBO: {len(sacbo_data)} voli")
    
    if not radar_data and not sacbo_data:
        print("\n[ERRORE] Nessun dato disponibile")
        return
    
    # ============================================================
    # ANALISI DATI RADAR
    # ============================================================
    
    # Raggruppa radar per callsign
    radar_flights = defaultdict(list)
    for d in radar_data:
        if d['callsign'] and d['callsign'] != 'N/A':
            radar_flights[d['callsign']].append(d)
    
    radar_movements = []
    for callsign, points in radar_flights.items():
        if len(points) < 2:
            continue
        
        movimento = determine_movement(points)
        if not movimento:
            continue
        
        pista, pista_desc = determine_runway(points)
        rumore = calculate_noise(points)
        
        punti_alt = [p['altitude'] for p in points]
        punti_vel = [p['altitude'] for p in points if p['altitude'] > 0]
        
        radar_movements.append({
            'callsign': callsign,
            'compagnia': get_airline_from_callsign(callsign),
            'modello': get_aircraft_model_from_callsign(callsign),
            'movimento': movimento,
            'pista': pista,
            'pista_desc': pista_desc,
            'orario': points[0]['timestamp'].strftime('%H:%M:%S'),
            'alt_max': round(max(punti_alt)),
            'rumore': rumore
        })
    
    # ============================================================
    # ANALISI DATI SACBO
    # ============================================================
    
    sacbo_movements = []
    for volo in sacbo_data:
        # Filtra solo voli con stato significativo
        stato = volo.get('stato', '')
        if stato in ['Decollato', 'Imbarco chiuso', 'Imbarco ultima chiamata', 'Imbarco in corso']:
            movimento = "DECOLLO" if volo['tipo'] == 'partenza' else "ATTERRAGGIO"
            orario = extract_time(volo['orario'])
            
            sacbo_movements.append({
                'callsign': volo['numero_volo'],
                'compagnia': get_airline_from_callsign(volo['numero_volo']),
                'modello': get_aircraft_model_from_callsign(volo['numero_volo']),
                'movimento': movimento,
                'orario': orario,
                'destinazione': volo['destinazione'],
                'stato': stato
            })
    
    # ============================================================
    # GENERA REPORT TXT
    # ============================================================
    
    txt_file = Path(REPORT_DIR) / f"report_completo_{date_str}.txt"
    
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("REPORT MONITORAGGIO AEROPORTO DI ORIO AL SERIO (BGY)\n")
        f.write(f"Data: {date_str[:4]}/{date_str[4:6]}/{date_str[6:8]}\n")
        f.write(f"Generato: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")
        
        # Sezione RADAR
        f.write("DATI RADAR (OPENSKY) - RILEVATI OGGETTIVAMENTE\n")
        f.write("-"*80 + "\n")
        if radar_movements:
            decolli = [m for m in radar_movements if m['movimento'] == 'DECOLLO']
            atterraggi = [m for m in radar_movements if m['movimento'] == 'ATTERRAGGIO']
            f.write(f"Totale: {len(radar_movements)} movimenti\n")
            f.write(f"  - Decolli: {len(decolli)}\n")
            f.write(f"  - Atterraggi: {len(atterraggi)}\n\n")
            
            for m in radar_movements:
                f.write(f"\n✈️ {m['callsign']} - {m['movimento']}\n")
                f.write(f"   Compagnia: {m['compagnia']}\n")
                f.write(f"   Modello: {m['modello']}\n")
                f.write(f"   Pista: {m['pista']} ({m['pista_desc']})\n")
                f.write(f"   Orario: {m['orario']}\n")
                f.write(f"   Altitudine max: {m['alt_max']} m\n")
                
                if m['rumore']:
                    f.write(f"   Rumore centraline:\n")
                    for r in m['rumore'][:3]:
                        f.write(f"     - {r['centralina']}: {r['rumore_db']} dB ({r['valutazione']})\n")
        else:
            f.write("NESSUN MOVIMENTO RILEVATO DAL RADAR\n")
        
        # Sezione SACBO
        f.write("\n" + "="*80 + "\n")
        f.write("DATI TABELLONE SACBO (UFFICIALI)\n")
        f.write("-"*80 + "\n")
        if sacbo_movements:
            decolli = [m for m in sacbo_movements if m['movimento'] == 'DECOLLO']
            atterraggi = [m for m in sacbo_movements if m['movimento'] == 'ATTERRAGGIO']
            f.write(f"Totale: {len(sacbo_movements)} movimenti\n")
            f.write(f"  - Decolli: {len(decolli)}\n")
            f.write(f"  - Atterraggi: {len(atterraggi)}\n\n")
            
            for m in sacbo_movements:
                f.write(f"\n{m['orario']} - {m['callsign']} - {m['movimento']}\n")
                f.write(f"   Compagnia: {m['compagnia']}\n")
                f.write(f"   Modello: {m['modello']}\n")
                f.write(f"   Destinazione: {m['destinazione']}\n")
                f.write(f"   Stato: {m['stato']}\n")
        else:
            f.write("NESSUN DATO SACBO DISPONIBILE\n")
        
        # Conclusioni
        f.write("\n" + "="*80 + "\n")
        f.write("CONCLUSIONI\n")
        f.write("-"*80 + "\n")
        f.write(f"Il radar OpenSky ha rilevato {len(radar_movements)} movimenti.\n")
        f.write(f"Il tabellone SACBO riporta {len(sacbo_movements)} movimenti.\n")
        if len(sacbo_movements) > len(radar_movements):
            f.write(f"\nDifferenza: {len(sacbo_movements) - len(radar_movements)} voli non rilevati dal radar.\n")
        f.write("="*80 + "\n")
    
    # ============================================================
    # GENERA REPORT CSV
    # ============================================================
    
    csv_file = Path(REPORT_DIR) / f"report_completo_{date_str}.csv"
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['fonte', 'callsign', 'compagnia', 'modello', 'movimento', 'pista', 'orario', 'destinazione', 'alt_max_m'])
        
        for m in radar_movements:
            writer.writerow(['RADAR', m['callsign'], m['compagnia'], m['modello'], m['movimento'], m['pista'], m['orario'], '', m['alt_max']])
        
        for m in sacbo_movements:
            writer.writerow(['SACBO', m['callsign'], m['compagnia'], m['modello'], m['movimento'], '', m.get('orario', ''), m.get('destinazione', ''), ''])
    
    print(f"\n[OK] Report generati:")
    print(f"   TXT: {txt_file}")
    print(f"   CSV: {csv_file}")
    print(f"\n   RADAR: {len(radar_movements)} movimenti")
    print(f"   SACBO: {len(sacbo_movements)} movimenti")

def main():
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        date_str = datetime.now().strftime("%Y%m%d")
    
    generate_report(date_str)

if __name__ == "__main__":
    main()