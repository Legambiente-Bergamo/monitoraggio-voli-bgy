"""
bgy_migrate_to_2.5.py - Migrazione struttura 2.5
- Rinomina cartelle con prefisso bgy_
- Aggiorna import nei file .py
- Riscrive bgy_core/bgy_paths.py e .gitignore
Eseguire UNA SOLA VOLTA nella root del progetto (Monitoraggio BGY 2.5).
"""
import os
import re
import sys
import json
from datetime import datetime

ROOT = os.path.abspath(os.path.dirname(__file__))
LOG = []

def log(msg):
    LOG.append(msg)
    print(msg)

# ---------------------------------------------------------------------------
# 1. CONTROLLI PRELIMINARI
# ---------------------------------------------------------------------------

def check_root():
    if not os.path.exists(os.path.join(ROOT, "bgy_gui.py")):
        log("❌ bgy_gui.py non trovato nella root. Sei nella cartella giusta?")
        sys.exit(1)
    if not os.path.exists(os.path.join(ROOT, "bgy_core")) \
            and not os.path.exists(os.path.join(ROOT, "core")):
        log("❌ Né core/ né bgy_core/ trovati. Migrazione già fatta o cartella sbagliata.")
        sys.exit(1)
    log(f"✅ Root: {ROOT}")

# ---------------------------------------------------------------------------
# 2. RINOMINA CARTELLE
# ---------------------------------------------------------------------------

FOLDER_RENAMES = [
    ("core",                 "bgy_core"),
    ("scanners",             "bgy_scanners"),
    ("exporters",            "bgy_exporters"),
    ("config",               "bgy_config"),
    ("bgy_data/raw",         "bgy_data/bgy_raw"),
    ("bgy_data/bgy_reports", "bgy_data/bgy_output"),
    ("bgy_data/charts",      "bgy_data/bgy_charts"),
    ("bgy_data/logs",        "bgy_data/bgy_logs"),
]

OUTPUT_SUBFOLDER_RENAMES = [
    ("bgy_csv", "csv"),
    ("bgy_xlsx", "xlsx"),
    ("bgy_pdf", "pdf"),
    ("bgy_docx", "docx"),
    ("bgy_html", "html"),
]

LOG_SUBFOLDER_RENAMES = [
    ("bgy_archive", "archive"),
]

def rename_folder(src_rel, dst_rel):
    src = os.path.join(ROOT, src_rel.replace("/", os.sep))
    dst = os.path.join(ROOT, dst_rel.replace("/", os.sep))
    if os.path.exists(dst):
        log(f"⏭️  Già rinominata: {src_rel} → {dst_rel}")
        return True
    if not os.path.exists(src):
        log(f"⚠️  Sorgente assente: {src_rel} (skip)")
        return False
    try:
        os.rename(src, dst)
        log(f"✅ {src_rel} → {dst_rel}")
        return True
    except Exception as e:
        log(f"❌ Errore rinomina {src_rel} → {dst_rel}: {e}")
        return False

def do_folder_renames():
    log("\n--- Rinomina cartelle principali ---")
    for src, dst in FOLDER_RENAMES:
        rename_folder(src, dst)

    log("\n--- Rinomina sottocartelle di bgy_output ---")
    for new_name, old_name in OUTPUT_SUBFOLDER_RENAMES:
        rename_folder(f"bgy_data/bgy_output/{old_name}",
                      f"bgy_data/bgy_output/{new_name}")

    log("\n--- Rinomina sottocartelle di bgy_logs ---")
    for new_name, old_name in LOG_SUBFOLDER_RENAMES:
        rename_folder(f"bgy_data/bgy_logs/{old_name}",
                      f"bgy_data/bgy_logs/{new_name}")

# ---------------------------------------------------------------------------
# 3. AGGIORNA IMPORT NEI .py
# ---------------------------------------------------------------------------

IMPORT_REPLACEMENTS = [
    (re.compile(r'\bfrom core\b'),      'from bgy_core'),
    (re.compile(r'\bimport core\b'),    'import bgy_core'),
    (re.compile(r'\bfrom scanners\b'),  'from bgy_scanners'),
    (re.compile(r'\bimport scanners\b'),'import bgy_scanners'),
    (re.compile(r'\bfrom exporters\b'), 'from bgy_exporters'),
    (re.compile(r'\bimport exporters\b'),'import bgy_exporters'),
]

# Cartelle da scandire (post-rename)
SCAN_DIRS = ["bgy_core", "bgy_scanners", "bgy_exporters",
             "bgy_reports", "bgy_gui", "bgy_utils"]

def update_imports_in_file(path):
    with open(path, "r", encoding="utf-8") as f:
        original = f.read()
    updated = original
    for pattern, repl in IMPORT_REPLACEMENTS:
        updated = pattern.sub(repl, updated)
    if updated != original:
        with open(path, "w", encoding="utf-8") as f:
            f.write(updated)
        return True
    return False

def do_import_rewrite():
    log("\n--- Aggiornamento import ---")
    count = 0
    # File .py nella root
    for f in os.listdir(ROOT):
        if f.endswith(".py"):
            path = os.path.join(ROOT, f)
            if update_imports_in_file(path):
                log(f"✅ {f}")
                count += 1
    # File .py nelle sottocartelle
    for d in SCAN_DIRS:
        folder = os.path.join(ROOT, d)
        if not os.path.isdir(folder):
            continue
        for f in os.listdir(folder):
            if f.endswith(".py"):
                path = os.path.join(folder, f)
                if update_imports_in_file(path):
                    log(f"✅ {d}/{f}")
                    count += 1
    log(f"📊 File aggiornati: {count}")

# ---------------------------------------------------------------------------
# 4. RISCRITTURA bgy_paths.py
# ---------------------------------------------------------------------------

BGY_PATHS_CONTENT = '''"""
bgy_core/bgy_paths.py - Gestione centralizzata dei percorsi.
Versione 2.5 - Struttura con prefisso bgy_
"""
import os

CURRENT_FILE = os.path.abspath(__file__)
CORE_DIR = os.path.dirname(CURRENT_FILE)          # bgy_core/
PROJECT_ROOT = os.path.dirname(CORE_DIR)          # Monitoraggio BGY 2.5/

# --- Dati ---
DATA_DIR = os.path.join(PROJECT_ROOT, "bgy_data")

RAW_DIR = os.path.join(DATA_DIR, "bgy_raw")
OUTPUT_DIR = os.path.join(DATA_DIR, "bgy_output")
CHARTS_DIR = os.path.join(DATA_DIR, "bgy_charts")
LOGS_DIR = os.path.join(DATA_DIR, "bgy_logs")

OUTPUT_CSV_DIR = os.path.join(OUTPUT_DIR, "bgy_csv")
OUTPUT_XLSX_DIR = os.path.join(OUTPUT_DIR, "bgy_xlsx")
OUTPUT_PDF_DIR = os.path.join(OUTPUT_DIR, "bgy_pdf")
OUTPUT_DOCX_DIR = os.path.join(OUTPUT_DIR, "bgy_docx")
OUTPUT_HTML_DIR = os.path.join(OUTPUT_DIR, "bgy_html")

# --- Alias retrocompatibili (da rimuovere in v2.6) ---
REPORTS_DIR = OUTPUT_DIR
REPORTS_CSV_DIR = OUTPUT_CSV_DIR
REPORTS_XLSX_DIR = OUTPUT_XLSX_DIR
REPORTS_PDF_DIR = OUTPUT_PDF_DIR
REPORTS_DOCX_DIR = OUTPUT_DOCX_DIR
REPORTS_HTML_DIR = OUTPUT_HTML_DIR

# --- Config ---
CONFIG_DIR = os.path.join(PROJECT_ROOT, "bgy_config")

CONFIG_DATA = os.path.join(CONFIG_DIR, "config_data.json")
CONFIG_MAIL = os.path.join(CONFIG_DIR, "config_mail.json")
CONFIG_OPENSKY = os.path.join(CONFIG_DIR, "config_opensky.json")
CONFIG_GITHUB = os.path.join(CONFIG_DIR, "config_github.json")
RULES_AIRLINES = os.path.join(CONFIG_DIR, "config_rules_airlines.json")
RULES_COUNTRIES = os.path.join(CONFIG_DIR, "config_rules_countries.json")
RULES_AIRCRAFT_MODELS = os.path.join(CONFIG_DIR, "config_rules_aircraft_models.json")
RULES_NOISE_IMPACT = os.path.join(CONFIG_DIR, "config_noise_impact.json")


def ensure_directories():
    """Crea tutte le directory necessarie se non esistono."""
    dirs = [
        DATA_DIR, RAW_DIR, OUTPUT_DIR, CHARTS_DIR, LOGS_DIR,
        OUTPUT_CSV_DIR, OUTPUT_XLSX_DIR, OUTPUT_PDF_DIR,
        OUTPUT_DOCX_DIR, OUTPUT_HTML_DIR,
        CONFIG_DIR,
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


if __name__ == "__main__":
    ensure_directories()
    print("✅ Directory create.")
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
'''

def rewrite_bgy_paths():
    log("\n--- Riscrittura bgy_paths.py ---")
    path = os.path.join(ROOT, "bgy_core", "bgy_paths.py")
    if not os.path.exists(os.path.dirname(path)):
        log(f"❌ Cartella bgy_core/ non trovata. Rinomina fallita?")
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(BGY_PATHS_CONTENT)
    log(f"✅ bgy_paths.py riscritto")

# ---------------------------------------------------------------------------
# 5. RISCRITTURA .gitignore
# ---------------------------------------------------------------------------

GITIGNORE_CONTENT = """# Byte-compiled
__pycache__/
*.py[cod]
*$py.class

# Virtual environments
venv/
env/
.venv/

# Credenziali (MAI sincronizzare)
bgy_config/config_mail.json
bgy_config/config_opensky.json
bgy_config/config_github.json

# Output generati
bgy_data/bgy_output/
bgy_data/bgy_charts/
bgy_data/bgy_logs/

# Backup locali
backup_*/
backup_scripts_*/

# OS
Thumbs.db
.DS_Store
desktop.ini

# IDE
.vscode/
.idea/
*.swp
"""

def rewrite_gitignore():
    log("\n--- Riscrittura .gitignore ---")
    path = os.path.join(ROOT, ".gitignore")
    with open(path, "w", encoding="utf-8") as f:
        f.write(GITIGNORE_CONTENT)
    log(f"✅ .gitignore riscritto")

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    log("=" * 60)
    log("MIGRAZIONE STRUTTURA BGY 2.5")
    log(f"Avvio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)

    check_root()
    do_folder_renames()
    do_import_rewrite()
    rewrite_bgy_paths()
    rewrite_gitignore()

    log("\n" + "=" * 60)
    log("MIGRAZIONE COMPLETATA")
    log("=" * 60)
    log("\nProssimi passi:")
    log("1. Apri i file in bgy_core/, bgy_scanners/, bgy_exporters/")
    log("   e verifica che gli import puntino a bgy_core., bgy_scanners., bgy_exporters.")
    log("2. Avvia la GUI: py -3.12 bgy_gui.py")
    log("3. Verifica un ciclo completo: scansione diurna, notturna, report, sync GitHub")
    log("4. Solo dopo, su Produzione:")
    log("   - chiudi la suite")
    log("   - copia la cartella nuova (o fai la stessa migrazione)")
    log("   - riavvia")
    log("5. Quando tutto funziona, cancella bgy_migrate_to_2.5.py")

    with open(os.path.join(ROOT, "bgy_migrate_to_2.5.log"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(LOG))
    log(f"\n📄 Log salvato in bgy_migrate_to_2.5.log")


if __name__ == "__main__":
    main()