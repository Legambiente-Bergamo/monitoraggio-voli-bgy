#!/usr/bin/env python3
# bgy_monthly_report.py - Report mensile statistico avanzato
# Versione con menu interattivo

import csv
import sys
import os
import json
import math
from datetime import datetime, timedelta, time
from pathlib import Path
from collections import defaultdict, Counter
from calendar import monthrange
import statistics

# Costanti
DATA_DIR = "dati"
REPORT_DIR = "report"
CONFIG_FILE = "config.txt"

# ============================================================
# FUNZIONI DI UTILITY
# ============================================================

def clear_screen():
    """Pulisce lo schermo"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(title):
    """Stampa intestazione formattata"""
    print("\n" + "="*80)
    print(f" {title}")
    print("="*80)

def print_menu():
    """Stampa il menu principale"""
    clear_screen()
    print_header("📊 SISTEMA DI ANALISI MENSILE - AEROPORTO DI ORIO AL SERIO (BGY)")
    print("\n")
    print("   ┌─────────────────────────────────────────────────────────────────┐")
    print("   │                    MENU PRINCIPALE                              │")
    print("   ├─────────────────────────────────────────────────────────────────┤")
    print("   │                                                                 │")
    print("   │   1. 📈 ANALISI COMPLETATA (tutti i dati disponibili)          │")
    print("   │   2. 📅 ANALISI PER MESE SPECIFICO                               │")
    print("   │   3. 📆 ANALISI PER ANNO SPECIFICO                               │")
    print("   │   4. 🔥 ANALISI DEL MESE PRECEDENTE (focus)                     │")
    print("   │   5. 📋 ELENCA MESI DISPONIBILI                                  │")
    print("   │   6. ❌ ESCI                                                     │")
    print("   │                                                                 │")
    print("   └─────────────────────────────────────────────────────────────────┘")
    print("\n")

def get_available_months():
    """Trova tutti i mesi per cui esistono dati radar o SACBO"""
    months = set()
    
    # Cerca file radar
    for f in Path(DATA_DIR).glob("radar_*.csv"):
        date_str = f.stem.replace("radar_", "")
        if len(date_str) == 8 and date_str.isdigit():
            months.add(date_str[:6])  # YYYYMM
    
    # Cerca file SACBO
    for f in Path(DATA_DIR).glob("sacbo_*.csv"):
        date_str = f.stem.replace("sacbo_", "")
        if len(date_str) == 8 and date_str.isdigit():
            months.add(date_str[:6])
    
    return sorted(months)

def list_available_months():
    """Mostra l'elenco dei mesi disponibili"""
    months = get_available_months()
    
    if not months:
        print("\n⚠️ Nessun dato disponibile nella cartella 'dati/'")
        return
    
    print_header("📋 MESI DISPONIBILI")
    print("\n")
    print("   ┌─────────┬─────────────────────────────────────┐")
    print("   │   Mese  │  Periodo                            │")
    print("   ├─────────┼─────────────────────────────────────┤")
    
    for m in months:
        year = m[:4]
        month = m[4:6]
        month_names = ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
                       'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre']
        month_name = month_names[int(month)-1]
        print(f"   │  {m}    │  {month_name} {year}                     │")
    
    print("   └─────────┴─────────────────────────────────────┘")
    print(f"\n   Totale: {len(months)} mesi disponibili\n")

def select_month():
    """Menu interattivo per selezione mese"""
    months = get_available_months()
    
    if not months:
        print("\n⚠️ Nessun dato disponibile!")
        return None
    
    print_header("📅 SELEZIONE MESE")
    print("\n")
    print("   ┌─────┬─────────────────────────────────────┐")
    print("   │  N° │  Mese                               │")
    print("   ├─────┼─────────────────────────────────────┤")
    
    month_names = ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
                   'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre']
    
    for i, m in enumerate(months, 1):
        year = m[:4]
        month = int(m[4:6])
        month_name = month_names[month-1]
        print(f"   │  {i:2} │  {month_name} {year} ({m})            │")
    
    print("   ├─────┼─────────────────────────────────────┤")
    print("   │  0  │  Torna al menu principale           │")
    print("   └─────┴─────────────────────────────────────┘")
    
    while True:
        try:
            choice = input("\n   👉 Seleziona il numero del mese: ").strip()
            if choice == '0':
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(months):
                return months[idx]
            else:
                print("   ⚠️ Scelta non valida. Riprova.")
        except ValueError:
            print("   ⚠️ Inserisci un numero valido.")

def select_year():
    """Menu interattivo per selezione anno"""
    months = get_available_months()
    
    if not months:
        print("\n⚠️ Nessun dato disponibile!")
        return None
    
    # Estrai anni unici
    years = sorted(set(m[:4] for m in months))
    
    print_header("📆 SELEZIONE ANNO")
    print("\n")
    print("   ┌─────┬──────────────┐")
    print("   │  N° │  Anno        │")
    print("   ├─────┼──────────────┤")
    
    for i, year in enumerate(years, 1):
        print(f"   │  {i:2} │  {year}              │")
    
    print("   ├─────┼──────────────┤")
    print("   │  0  │  Torna al menu principale │")
    print("   └─────┴──────────────┘")
    
    while True:
        try:
            choice = input("\n   👉 Seleziona il numero dell'anno: ").strip()
            if choice == '0':
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(years):
                return years[idx]
            else:
                print("   ⚠️ Scelta non valida. Riprova.")
        except ValueError:
            print("   ⚠️ Inserisci un numero valido.")

def load_config():
    """Carica la configurazione"""
    config = {'airlines': {}}
    reading = None
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line == 'COMPAGNIE:':
                    reading = 'airlines'
                    continue
                if reading and not line:
                    reading = None
                    continue
                if reading == 'airlines' and ',' in line:
                    parts = line.split(',')
                    if len(parts) >= 4:
                        prefix = parts[0].strip()
                        config['airlines'][prefix] = {
                            'nome': parts[1].strip(),
                            'tipo': parts[3].strip()
                        }
    except Exception as e:
        print(f"Errore caricamento config: {e}")
    return config

CONFIG = load_config()

def is_cargo(callsign):
    cargo_prefixes = ['DHK', 'FDX', 'UPS', 'BOX', 'BCS']
    prefix = ''.join([c for c in callsign if c.isalpha()])[:3]
    return prefix in cargo_prefixes

def get_airline_type(callsign):
    prefix = ''.join([c for c in callsign if c.isalpha()])[:3]
    if prefix in CONFIG['airlines']:
        tipo = CONFIG['airlines'][prefix]['tipo']
        if tipo == 'lowcost':
            return 'Passeggeri Low-Cost'
        elif tipo == 'commerciale':
            return 'Passeggeri Tradizionale'
        elif tipo == 'cargo':
            return 'Merci/Cargo'
        elif tipo == 'business':
            return 'Business/Jet'
    if is_cargo(callsign):
        return 'Merci/Cargo'
    return 'Passeggeri'

def parse_sacbo_time(time_str):
    if not time_str:
        return None
    if ':' in time_str:
        parts = time_str.split('|')
        if parts:
            time_part = parts[0].strip()
            if len(time_part) >= 5:
                return time_part[:5]
    return None

def is_night_time(time_str):
    if not time_str:
        return False
    try:
        h, m = map(int, time_str.split(':'))
        return h >= 23 or h < 6
    except:
        return False

# ============================================================
# CARICAMENTO DATI
# ============================================================

def load_radar_data_for_month(year, month):
    """Carica tutti i dati radar per un mese intero"""
    data = []
    _, last_day = monthrange(year, month)
    
    for day in range(1, last_day + 1):
        date_str = f"{year}{month:02d}{day:02d}"
        filename = Path(DATA_DIR) / f"radar_{date_str}.csv"
        
        if not filename.exists():
            continue
        
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    lat = float(row['latitude']) if row['latitude'] else 0
                    lon = float(row['longitude']) if row['longitude'] else 0
                    
                    if not (45.5 <= lat <= 45.8 and 9.5 <= lon <= 9.9):
                        continue
                    
                    data.append({
                        'data': date_str,
                        'timestamp': datetime.fromisoformat(row['timestamp']),
                        'callsign': row['callsign'].strip(),
                        'altitude': float(row['altitude_m']) if row['altitude_m'] else 0,
                        'velocity': float(row['velocity_kmh']) if row['velocity_kmh'] else 0,
                        'latitude': lat,
                        'longitude': lon,
                        'origin_country': row['origin_country']
                    })
                except:
                    continue
    return data

def load_sacbo_data_for_month(year, month):
    """Carica tutti i dati SACBO per un mese intero"""
    data = []
    _, last_day = monthrange(year, month)
    
    for day in range(1, last_day + 1):
        date_str = f"{year}{month:02d}{day:02d}"
        filename = Path(DATA_DIR) / f"sacbo_{date_str}.csv"
        
        if not filename.exists():
            continue
        
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    orario_str = parse_sacbo_time(row.get('orario_programmato', ''))
                    if not orario_str:
                        continue
                    
                    data.append({
                        'data': date_str,
                        'tipo': row['tipo_volo'],
                        'callsign': row['numero_volo'].replace(' ', ''),
                        'destinazione': row['destinazione'].strip(),
                        'orario': orario_str,
                        'stato': row['stato'],
                        'notte': is_night_time(orario_str)
                    })
                except:
                    continue
    return data

def classify_flight_from_radar(points):
    if len(points) < 2:
        return None, None
    
    points.sort(key=lambda x: x['timestamp'])
    alt_start = points[0]['altitude']
    alt_end = points[-1]['altitude']
    alt_diff = alt_end - alt_start
    
    if alt_diff > 50:
        return "DECOLLO", points[-1]['timestamp']
    elif alt_diff < -50:
        return "ATTERRAGGIO", points[-1]['timestamp']
    return None, None

def determine_runway_from_radar(points):
    min_dist = float('inf')
    closest = None
    bgy_lat, bgy_lon = 45.667, 9.700
    
    for p in points:
        dist = math.sqrt((p['latitude'] - bgy_lat)**2 + (p['longitude'] - bgy_lon)**2) * 111
        if dist < min_dist:
            min_dist = dist
            closest = p
    
    if closest:
        lon = closest['longitude']
        if lon < 9.68:
            return "28"
        elif lon > 9.72:
            return "10"
    return "ND"

# ============================================================
# ANALISI COMPLETA
# ============================================================

def analyze_month(year, month):
    """Analisi completa del mese"""
    
    print(f"\n{'='*80}")
    print(f"📊 ANALISI MENSILE: {year}/{month:02d}")
    print(f"{'='*80}\n")
    
    radar_data = load_radar_data_for_month(year, month)
    sacbo_data = load_sacbo_data_for_month(year, month)
    
    if not radar_data and not sacbo_data:
        print("⚠️ Nessun dato disponibile per il periodo selezionato")
        return
    
    print(f"📁 Dati caricati:")
    print(f"   - Radar: {len(radar_data)} rilevamenti")
    print(f"   - SACBO: {len(sacbo_data)} voli schedulati")
    
    # ANALISI RADAR
    radar_flights = defaultdict(list)
    for d in radar_data:
        radar_flights[(d['data'], d['callsign'])].append(d)
    
    radar_decolli = []
    radar_atterraggi = []
    radar_runways = []
    radar_night_counts = {'DECOLLO': 0, 'ATTERRAGGIO': 0}
    
    for (date, callsign), points in radar_flights.items():
        movimento, timestamp = classify_flight_from_radar(points)
        if movimento:
            runway = determine_runway_from_radar(points)
            radar_runways.append(runway)
            
            if movimento == 'DECOLLO':
                radar_decolli.append({'date': date, 'callsign': callsign, 'timestamp': timestamp, 'runway': runway})
                if timestamp.hour >= 23 or timestamp.hour < 6:
                    radar_night_counts['DECOLLO'] += 1
            else:
                radar_atterraggi.append({'date': date, 'callsign': callsign, 'timestamp': timestamp, 'runway': runway})
                if timestamp.hour >= 23 or timestamp.hour < 6:
                    radar_night_counts['ATTERRAGGIO'] += 1
    
    # ANALISI SACBO
    daily_sacbo = defaultdict(list)
    daily_decolli = defaultdict(int)
    daily_atterraggi = defaultdict(int)
    
    for volo in sacbo_data:
        daily_sacbo[volo['data']].append(volo)
        if volo['tipo'] == 'partenza':
            daily_decolli[volo['data']] += 1
        else:
            daily_atterraggi[volo['data']] += 1
    
    decolli_totali = sum(daily_decolli.values())
    atterraggi_totali = sum(daily_atterraggi.values())
    totale_giorni = len(daily_sacbo)
    
    night_decolli = 0
    night_atterraggi = 0
    for volo in sacbo_data:
        if volo['notte']:
            if volo['tipo'] == 'partenza':
                night_decolli += 1
            else:
                night_atterraggi += 1
    
    # Statistiche per notte
    decolli_per_notte = []
    atterraggi_per_notte = []
    
    for giorno, voli in daily_sacbo.items():
        notte_dec = sum(1 for v in voli if v['tipo'] == 'partenza' and v['notte'])
        notte_att = sum(1 for v in voli if v['tipo'] == 'arrivo' and v['notte'])
        if notte_dec > 0 or notte_att > 0:
            decolli_per_notte.append(notte_dec)
            atterraggi_per_notte.append(notte_att)
    
    # ROTTE
    route_counter = Counter()
    for volo in sacbo_data:
        dest = volo['destinazione'].strip()
        if dest and len(dest) < 50:
            route_counter[dest] += 1
    
    # DISTRIBUZIONE ORARIA
    hourly_count = defaultdict(int)
    for volo in sacbo_data:
        if volo['orario']:
            ora = volo['orario'][:2]
            hourly_count[ora] += 1
    
    # RITARDI
    ritardi = []
    for volo in sacbo_data:
        stato = volo.get('stato', '')
        if 'Ritardo' in stato or 'ritardo' in stato:
            ritardi.append(volo)
    
    # TIPOLOGIE
    tipos = defaultdict(int)
    for volo in sacbo_data:
        tipo = get_airline_type(volo['callsign'])
        if volo['notte']:
            tipos[f"Notturno - {tipo}"] += 1
        else:
            tipos[f"Diurno - {tipo}"] += 1
    
    merci_totali = sum(v for k, v in tipos.items() if 'Merci' in k)
    passeggeri_totali = sum(v for k, v in tipos.items() if 'Passeggeri' in k)
    
    # STAMPA RISULTATI
    print(f"\n📊 STATISTICHE RADAR:")
    print(f"   ├─ Decolli rilevati: {len(radar_decolli)}")
    print(f"   ├─ Atterraggi rilevati: {len(radar_atterraggi)}")
    print(f"   └─ Totale movimenti: {len(radar_decolli) + len(radar_atterraggi)}")
    
    print(f"\n📋 STATISTICHE SACBO:")
    print(f"   ├─ Decolli schedulati: {decolli_totali}")
    print(f"   ├─ Atterraggi schedulati: {atterraggi_totali}")
    print(f"   └─ Giorni con dati: {totale_giorni}")
    
    print(f"\n🌙 STATISTICHE NOTTURNE (23:00-06:00):")
    print(f"   ├─ Decolli notturni: {night_decolli}")
    print(f"   ├─ Atterraggi notturni: {night_atterraggi}")
    print(f"   └─ Totale movimenti notturni: {night_decolli + night_atterraggi}")
    
    if decolli_per_notte:
        print(f"\n📈 STATISTICHE DECOLLI NOTTURNI:")
        print(f"   ├─ Media: {statistics.mean(decolli_per_notte):.1f} per notte")
        print(f"   ├─ Max: {max(decolli_per_notte)}")
        print(f"   ├─ Min: {min(decolli_per_notte)}")
        print(f"   └─ Totale notti: {len(decolli_per_notte)}")
    
    if atterraggi_per_notte:
        print(f"\n📈 STATISTICHE ATTERRAGGI NOTTURNI:")
        print(f"   ├─ Media: {statistics.mean(atterraggi_per_notte):.1f} per notte")
        print(f"   ├─ Max: {max(atterraggi_per_notte)}")
        print(f"   ├─ Min: {min(atterraggi_per_notte)}")
        print(f"   └─ Totale notti: {len(atterraggi_per_notte)}")
    
    print(f"\n✈️ TOP 10 ROTTE:")
    for i, (dest, count) in enumerate(route_counter.most_common(10), 1):
        print(f"   {i:2}. {dest:<35} {count:>4} voli")
    
    print(f"\n⏱️ RITARDI:")
    print(f"   ├─ Totale voli in ritardo: {len(ritardi)}")
    if totale_giorni > 0:
        print(f"   └─ Media giornaliera: {len(ritardi)/totale_giorni:.1f}")
    
    print(f"\n📦 TIPOLOGIE VOLO:")
    print(f"   ├─ MERCI: {merci_totali} voli")
    print(f"   ├─ PASSEGGERI: {passeggeri_totali} voli")
    if passeggeri_totali > 0:
        print(f"   └─ Rapporto Merci/Passeggeri: {merci_totali/passeggeri_totali*100:.1f}%")
    
    # SALVA REPORT
    report = {
        'periodo': f"{year}/{month:02d}",
        'date': datetime.now().isoformat(),
        'radar': {
            'decolli': len(radar_decolli),
            'atterraggi': len(radar_atterraggi),
            'decolli_notturni': radar_night_counts['DECOLLO'],
            'atterraggi_notturni': radar_night_counts['ATTERRAGGIO']
        },
        'sacbo': {
            'decolli_totali': decolli_totali,
            'atterraggi_totali': atterraggi_totali,
            'decolli_notturni': night_decolli,
            'atterraggi_notturni': night_atterraggi,
            'media_decolli_notturni': statistics.mean(decolli_per_notte) if decolli_per_notte else 0,
            'media_atterraggi_notturni': statistics.mean(atterraggi_per_notte) if atterraggi_per_notte else 0,
            'ritardi_totali': len(ritardi),
            'merci_totali': merci_totali,
            'passeggeri_totali': passeggeri_totali,
            'rotte_top10': [(dest, count) for dest, count in route_counter.most_common(10)]
        }
    }
    
    json_file = Path(REPORT_DIR) / f"monthly_report_{year}{month:02d}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, default=str)
    
    txt_file = Path(REPORT_DIR) / f"monthly_report_{year}{month:02d}.txt"
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write(f"REPORT MENSILE BGY - {year}/{month:02d}\n")
        f.write(f"Generato: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write("="*80 + "\n\n")
        f.write(f"Decolli notturni: {night_decolli}\n")
        f.write(f"Atterraggi notturni: {night_atterraggi}\n")
        f.write(f"Ritardi: {len(ritardi)}\n")
        f.write(f"Merci: {merci_totali}\n")
        f.write(f"Passeggeri: {passeggeri_totali}\n")
    
    print(f"\n✅ Report salvati in: {REPORT_DIR}/")

def analyze_year(year):
    """Analisi di tutti i mesi di un anno"""
    months = get_available_months()
    year_months = [m for m in months if m.startswith(year)]
    
    if not year_months:
        print(f"\n⚠️ Nessun dato disponibile per l'anno {year}")
        return
    
    print_header(f"📆 ANALISI COMPLETA ANNO {year}")
    print(f"\n   Mesi disponibili: {len(year_months)}\n")
    
    total_decolli = 0
    total_atterraggi = 0
    total_ritardi = 0
    total_merci = 0
    total_passeggeri = 0
    
    for m in year_months:
        m_num = int(m[4:6])
        month_names = ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
                       'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre']
        
        radar_data = load_radar_data_for_month(int(year), m_num)
        sacbo_data = load_sacbo_data_for_month(int(year), m_num)
        
        # Calcoli rapidi
        night_dec = sum(1 for v in sacbo_data if v['tipo'] == 'partenza' and v['notte'])
        night_att = sum(1 for v in sacbo_data if v['tipo'] == 'arrivo' and v['notte'])
        ritardi = sum(1 for v in sacbo_data if 'Ritardo' in v.get('stato', ''))
        
        merci = sum(1 for v in sacbo_data if 'Merci' in get_airline_type(v['callsign']))
        passeggeri = sum(1 for v in sacbo_data if 'Passeggeri' in get_airline_type(v['callsign']))
        
        total_decolli += night_dec
        total_atterraggi += night_att
        total_ritardi += ritardi
        total_merci += merci
        total_passeggeri += passeggeri
        
        print(f"   📅 {month_names[m_num-1]} {year}:")
        print(f"      ├─ Decolli notturni: {night_dec}")
        print(f"      ├─ Atterraggi notturni: {night_att}")
        print(f"      ├─ Ritardi: {ritardi}")
        print(f"      └─ Merci/Passeggeri: {merci}/{passeggeri}")
        print()
    
    print("="*80)
    print(f"📊 TOTALE ANNO {year}:")
    print(f"   ├─ Decolli notturni: {total_decolli}")
    print(f"   ├─ Atterraggi notturni: {total_atterraggi}")
    print(f"   ├─ Ritardi: {total_ritardi}")
    print(f"   ├─ Merci: {total_merci}")
    print(f"   └─ Passeggeri: {total_passeggeri}")
    print("="*80)

def analyze_historical():
    """Analisi completa di tutti i dati disponibili"""
    months = get_available_months()
    
    if not months:
        print("\n⚠️ Nessun dato disponibile!")
        return
    
    print_header("📚 ANALISI COMPLETATA DI TUTTI I DATI")
    print(f"\n   Totale mesi disponibili: {len(months)}\n")
    
    total_decolli = 0
    total_atterraggi = 0
    total_ritardi = 0
    total_merci = 0
    total_passeggeri = 0
    all_night_counts = []
    
    month_names = ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
                   'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre']
    
    for m in months:
        year = int(m[:4])
        month = int(m[4:6])
        
        sacbo_data = load_sacbo_data_for_month(year, month)
        
        night_dec = sum(1 for v in sacbo_data if v['tipo'] == 'partenza' and v['notte'])
        night_att = sum(1 for v in sacbo_data if v['tipo'] == 'arrivo' and v['notte'])
        ritardi = sum(1 for v in sacbo_data if 'Ritardo' in v.get('stato', ''))
        
        merci = sum(1 for v in sacbo_data if 'Merci' in get_airline_type(v['callsign']))
        passeggeri = sum(1 for v in sacbo_data if 'Passeggeri' in get_airline_type(v['callsign']))
        
        total_decolli += night_dec
        total_atterraggi += night_att
        total_ritardi += ritardi
        total_merci += merci
        total_passeggeri += passeggeri
        
        if night_dec + night_att > 0:
            all_night_counts.append(night_dec + night_att)
        
        print(f"   📅 {month_names[month-1]} {year}:")
        print(f"      ├─ Movimenti notturni: {night_dec + night_att}")
        print(f"      ├─ Ritardi: {ritardi}")
        print(f"      └─ Merci/Passeggeri: {merci}/{passeggeri}")
        print()
    
    print("="*80)
    print(f"📊 STATISTICHE COMPLESSIVE:")
    print(f"   ├─ Totale movimenti notturni: {total_decolli + total_atterraggi}")
    print(f"   ├─ Decolli notturni: {total_decolli}")
    print(f"   ├─ Atterraggi notturni: {total_atterraggi}")
    print(f"   ├─ Ritardi totali: {total_ritardi}")
    print(f"   ├─ Merci totali: {total_merci}")
    print(f"   ├─ Passeggeri totali: {total_passeggeri}")
    if all_night_counts:
        print(f"   ├─ Media movimenti/notte: {statistics.mean(all_night_counts):.1f}")
        print(f"   ├─ Max movimenti/notte: {max(all_night_counts)}")
        print(f"   └─ Min movimenti/notte: {min(all_night_counts)}")
    print("="*80)

def analyze_last_month():
    """Analizza il mese precedente"""
    today = datetime.now()
    last_month = today.replace(day=1) - timedelta(days=1)
    year = last_month.year
    month = last_month.month
    
    print_header(f"🔥 ANALISI FOCUS SUL MESE PRECEDENTE: {year}/{month:02d}")
    analyze_month(year, month)

# ============================================================
# MAIN CON MENU
# ============================================================

def main():
    while True:
        print_menu()
        
        choice = input("   👉 Scegli un'opzione (1-6): ").strip()
        
        if choice == '1':
            analyze_historical()
            input("\n   Premi INVIO per tornare al menu...")
        
        elif choice == '2':
            selected = select_month()
            if selected:
                year = int(selected[:4])
                month = int(selected[4:6])
                analyze_month(year, month)
                input("\n   Premi INVIO per tornare al menu...")
        
        elif choice == '3':
            selected_year = select_year()
            if selected_year:
                analyze_year(selected_year)
                input("\n   Premi INVIO per tornare al menu...")
        
        elif choice == '4':
            analyze_last_month()
            input("\n   Premi INVIO per tornare al menu...")
        
        elif choice == '5':
            list_available_months()
            input("\n   Premi INVIO per tornare al menu...")
        
        elif choice == '6':
            print("\n   👋 Grazie per aver usato il sistema di analisi BGY!")
            print("   Arrivederci!\n")
            break
        
        else:
            print("\n   ⚠️ Opzione non valida. Scegli 1-6.")
            input("\n   Premi INVIO per continuare...")

if __name__ == "__main__":
    main()