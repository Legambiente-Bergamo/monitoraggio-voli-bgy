"""
add_missing_airlines.py - Aggiunge le compagnie note rimosse per errore.

Uso:
    py -3.12 add_missing_airlines.py
"""
import json
import shutil
from datetime import datetime
from pathlib import Path

CONFIG_FILE = Path("bgy_config") / "config_rules_airlines.json"

# Codici identificati come compagnie aeree reali
MISSING_AIRLINES = {
    "BQ": "Sky Alps",
    "AP": "Albastar",
    "E5": "Air Arabia Egypt",
    "A9": "Georgian Airways",
    "BZ": "Blue Bird Airways",
    "DY": "Norwegian Air Shuttle",
    "VR": "Cabo Verde Airlines",
    "3F": "FlyOne",
    "MT": "Malta Air",
    # H7, OCN, VND, EFW, VJH, IVL, CMA: da identificare in seguito
}

# Codici da NON ri-aggiungere (sentinel/special)
SKIP_CODES = {"N/D", "UNK"}


def main():
    if not CONFIG_FILE.exists():
        print(f"❌ File non trovato: {CONFIG_FILE}")
        return

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = CONFIG_FILE.with_suffix(CONFIG_FILE.suffix + f".bak_{ts}")
    shutil.copy2(CONFIG_FILE, backup_path)
    print(f"✅ Backup creato: {backup_path}")

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    added = []
    skipped = []
    for code, name in MISSING_AIRLINES.items():
        if code in data and not str(data[code]).startswith("Compagnia "):
            skipped.append((code, data[code]))
            continue
        data[code] = name
        added.append((code, name))

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print()
    print("=" * 60)
    print(f"✅ Aggiunti ({len(added)}):")
    for code, name in added:
        print(f"   + {code:5s} → {name}")
    if skipped:
        print()
        print(f"⏭️  Già presenti ({len(skipped)}):")
        for code, val in skipped:
            print(f"   = {code:5s} → {val}")
    print("=" * 60)


if __name__ == "__main__":
    main()