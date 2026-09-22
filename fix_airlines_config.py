"""
fix_airlines_config.py - Corregge e completa config_rules_airlines.json.

Cosa fa:
1. Backup del file (con timestamp)
2. Carica il JSON
3. Rimuove eventuali entry placeholder ("Compagnia XXX")
4. Aggiunge/corregge i mapping per i 13 codici identificati
5. Salva
6. Stampa un report dettagliato

Uso:
    py -3.12 fix_airlines_config.py
"""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

CONFIG_FILE = Path("bgy_config") / "config_rules_airlines.json"

# Mapping definitivi (source of truth per questa operazione)
FIXED_MAPPINGS = {
    # Codici con nome noto
    "ENT":  "Enter Air",
    "EZS":  "easyJet Switzerland",
    "FIA":  "Fly One",
    "GAV":  "Global Reach Aviation",
    "HBF":  "Privato (HB-FXE)",
    "MAC":  "Malta Air",
    "MAS":  "Privato (M-ASBA)",
    "NL":   "Amelia International",
    "NO":   "Neos",
    "NP":   "Nile Air",
    "RK":   "Ryanair UK",
    "SRR":  "Star Air",
    "V7":   "Volotea",
}


def main():
    if not CONFIG_FILE.exists():
        print(f"❌ File non trovato: {CONFIG_FILE}")
        sys.exit(1)

    # --- Backup ---
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = CONFIG_FILE.with_suffix(CONFIG_FILE.suffix + f".bak_{ts}")
    shutil.copy2(CONFIG_FILE, backup_path)
    print(f"✅ Backup creato: {backup_path}")

    # --- Carica ---
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"📄 Chiavi di primo livello: {len(data)}")

    # --- Statistiche iniziali ---
    placeholders = [k for k, v in data.items()
                    if isinstance(v, str) and v.startswith("Compagnia ")]
    print(f"🔍 Placeholder trovati ({len(placeholders)}): "
          f"{', '.join(sorted(placeholders)) if placeholders else 'nessuno'}")

    # --- Rimuovi tutti i placeholder ---
    removed = []
    for k in placeholders:
        del data[k]
        removed.append(k)
    if removed:
        print(f"🗑️  Rimossi {len(removed)} placeholder")

    # --- Aggiungi/correggi i mapping fissi ---
    added = []
    corrected = []
    for code, name in FIXED_MAPPINGS.items():
        old = data.get(code)
        if old is None:
            data[code] = name
            added.append(code)
        elif old != name:
            data[code] = name
            corrected.append((code, old, name))

    # --- Salva ---
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # --- Report finale ---
    print()
    print("=" * 60)
    print(f"✅ Mapping aggiunti ({len(added)}):")
    for code in added:
        print(f"   + {code:5s} → {FIXED_MAPPINGS[code]}")

    if corrected:
        print()
        print(f"🔧 Mapping corretti ({len(corrected)}):")
        for code, old, new in corrected:
            print(f"   ~ {code:5s} : {old!r} → {new!r}")

    if removed:
        print()
        print(f"🗑️  Placeholder rimossi ({len(removed)}):")
        for code in removed:
            print(f"   - {code}")

    print("=" * 60)
    print(f"\n📁 File aggiornato: {CONFIG_FILE}")
    print(f"📁 Backup: {backup_path}")


if __name__ == "__main__":
    main()