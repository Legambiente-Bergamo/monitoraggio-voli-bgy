"""
bgy_tools/update_aircraft_dict.py
Scarica il database ufficiale degli aerei (OpenSky) e aggiorna il dizionario locale.
"""
import os
import sys
import csv
import json
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bgy_core.bgy_paths import DATA_DIR

URL = "https://opensky-network.org/datasets/metadata/aircraftDatabase.csv"
OUTPUT_FILE = os.path.join(DATA_DIR, "aircraft_dictionary.json")

def update_dictionary():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Download database OpenSky...")
    try:
        r = requests.get(URL, timeout=60)
        r.raise_for_status()
    except Exception as e:
        print(f"ERRORE download: {e}")
        return False

    print("Elaborazione in corso...")
    dictionary = {}
    lines = r.text.splitlines()
    reader = csv.DictReader(lines)
    
    for row in reader:
        icao24 = row.get("icao24", "").strip().lower()
        model = row.get("model", "").strip()
        if icao24 and model:
            dictionary[icao24] = model
            
    print(f"Trovati {len(dictionary)} modelli univoci.")
    
    payload = {
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_aircraft": len(dictionary),
        "data": dictionary
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
        
    print(f"Dizionario salvato in {OUTPUT_FILE}")
    return True

if __name__ == "__main__":
    update_dictionary()