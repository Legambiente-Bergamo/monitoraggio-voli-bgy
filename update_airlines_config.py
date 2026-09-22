"""
update_airlines_config.py - Aggiunge mapping compagnie mancanti.

Uso:
    py -3.12 update_airlines_config.py

Cosa fa:
1. Fa un backup di bgy_config/config_rules_airlines.json
2. Carica il JSON
3. Rileva la sezione delle compagnie (airlines / _airlines / _iata_to_icao / ecc.)
4. Aggiunge i mapping mancanti (senza sovrascrivere quelli esistenti)
5. Salva il file aggiornato
6. Stampa un riepilogo
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# ---------- CONFIGURAZIONE PERCORSI ----------
CONFIG_FILE = Path("bgy_config") / "config_rules_airlines.json"
BACKUP_SUFFIX = f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

# ---------- MAPPING DA AGGIUNGERE ----------
# Vengono aggiunti SOLO se il codice non è già presente.
NEW_MAPPINGS = {
    "ENT": {"icao": "ENT", "name": "Enter Air"},
    "EZS": {"icao": "EZS", "name": "easyJet Switzerland"},
    "FIA": {"icao": "FIA", "name": "Fly One"},
    "GAV": {"icao": "GAV", "name": "Global Reach Aviation"},
    "HBF": {"icao": "HBF", "name": "Privato (HB-FXE)"},
    "MAC": {"icao": "MAC", "name": "Malta Air"},
    "MAS": {"icao": "MAS", "name": "Privato (M-ASBA)"},
    "NL":  {"icao": "AEH", "name": "Amelia International"},
    "NO":  {"icao": "NOS", "name": "Neos"},
    "NP":  {"icao": "NIA", "name": "Nile Air"},
    "RK":  {"icao": "RUK", "name": "Ryanair UK"},
    "SRR": {"icao": "SRR", "name": "Star Air"},
    "V7":  {"icao": "VOE", "name": "Volotea"},
}

# Possibili nomi della sezione "compagnie" nel JSON
CANDIDATE_KEYS = [
    "airlines",
    "_airlines",
    "_airlines_map",
    "compagnie",
    "_compagnie",
    "companies",
]


def find_airlines_section(data):
    """Trova la sezione in cui inserire i mapping compagnie."""
    # 1. Cerca una sezione esplicita
    for key in CANDIDATE_KEYS:
        if key in data and isinstance(data[key], dict):
            return key

    # 2. Se non c'è, cerca se la root stessa è una mappa di compagnie
    #    (caso in cui il file sia piatto tipo {"FR": {...}, "U2": {...}})
    if data and all(isinstance(v, dict) for v in data.values()):
        # Verifica se almeno una entry ha "icao" o "name"
        sample = next(iter(data.values()))
        if "icao" in sample or "name" in sample:
            return "__ROOT__"

    # 3. Nessuna sezione trovata
    return None


def main():
    if not CONFIG_FILE.exists():
        print(f"❌ File non trovato: {CONFIG_FILE}")
        sys.exit(1)

    # --- Backup ---
    backup_path = CONFIG_FILE.with_suffix(CONFIG_FILE.suffix + BACKUP_SUFFIX)
    shutil.copy2(CONFIG_FILE, backup_path)
    print(f"✅ Backup creato: {backup_path}")

    # --- Carica JSON ---
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Errore parsing JSON: {e}")
        print(f"   Il file non è stato modificato. Backup disponibile in: {backup_path}")
        sys.exit(1)

    # --- Trova sezione ---
    section_key = find_airlines_section(data)
    if section_key is None:
        print("❌ Impossibile rilevare la sezione delle compagnie.")
        print("   Chiavi di primo livello trovate:")
        for k in data.keys():
            print(f"     - {k}")
        print("\n   Aggiungi manualmente la chiave 'airlines' o modifica CANDIDATE_KEYS nello script.")
        sys.exit(1)

    if section_key == "__ROOT__":
        target = data
        print("ℹ️  La root del file è la mappa delle compagnie (struttura piatta).")
    else:
        target = data[section_key]
        print(f"ℹ️  Sezione compagnie trovata: '{section_key}'")

    # --- Aggiungi mapping mancanti ---
    added = []
    skipped = []

    for code, entry in NEW_MAPPINGS.items():
        if code in target:
            skipped.append(code)
            continue
        target[code] = entry
        added.append(code)

    # --- Salva ---
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # --- Riepilogo ---
    print()
    print("=" * 50)
    print(f"✅ Mapping aggiunti ({len(added)}):")
    for code in added:
        print(f"   + {code:5s} → {NEW_MAPPINGS[code]['name']}")
    if skipped:
        print()
        print(f"⏭️  Mapping già presenti ({len(skipped)}):")
        for code in skipped:
            print(f"   = {code}")
    print("=" * 50)
    print(f"\n📁 File aggiornato: {CONFIG_FILE}")
    print(f"📁 Backup: {backup_path}")
    print()
    print("➡️  Prossimi passi:")
    print("   1. Riavvia la GUI per ricaricare le regole")
    print("   2. Verifica: py -3.12 -c \"from bgy_core import get_airline; print(get_airline('GAV 907'))\"")


if __name__ == "__main__":
    main()