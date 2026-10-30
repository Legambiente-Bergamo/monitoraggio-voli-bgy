"""
bgy_tools/estrai_print_config.py
Genera bgy-print-config.json a partire da bgy_config/config_data.json > print.

Versione 1.0.1 — 29/10/2026
- Fix: usa os.path relativo alla root del progetto, non importa bgy_paths.
"""
import json
import os
import sys

# Root = directory da cui viene eseguito il comando (deve essere la root del progetto)
ROOT = os.getcwd()
CONFIG_PATH = os.path.join(ROOT, "bgy_config", "config_data.json")
OUT_DIR = os.path.join(ROOT, "bgy_data", "bgy_output", "bgy_web")
OUT_PATH = os.path.join(OUT_DIR, "bgy-print-config.json")


def main():
    if not os.path.exists(CONFIG_PATH):
        print(f"ERRORE: file non trovato: {CONFIG_PATH}")
        print("Assicurati di eseguire il comando dalla root del progetto.")
        sys.exit(1)

    with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
        config = json.load(f)

    print_section = config.get("print", {})
    if not print_section:
        print("ERRORE: sezione 'print' assente in config_data.json")
        sys.exit(1)

    # Costruisce l'output: enabled in testa, poi la sezione print
    output = {"enabled": True}
    output.update(print_section)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)

    size_kb = round(os.path.getsize(OUT_PATH) / 1024, 1)
    print(f"OK: {OUT_PATH} ({size_kb} KB)")
    print("Ora carica il file su WordPress in wp-content/uploads/")


if __name__ == "__main__":
    main()