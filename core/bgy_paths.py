"""
core/bgy_paths.py - Gestione centralizzata dei percorsi per la suite BGY.
"""
import os

# Percorso base: risali di due livelli dalla cartella core/
# core/bgy_paths.py -> bgy_core/ -> Monitoraggio BGY 2.0/
CURRENT_FILE = os.path.abspath(__file__)
CORE_DIR = os.path.dirname(CURRENT_FILE)  # bgy_core/core/
PROJECT_ROOT = os.path.dirname(CORE_DIR)  # bgy_core/

# Directory principali
DATA_DIR = os.path.join(PROJECT_ROOT, "bgy_data")

# Sottodirectory dei dati
RAW_DIR = os.path.join(DATA_DIR, "raw")
REPORTS_DIR = os.path.join(DATA_DIR, "bgy_reports")
CHARTS_DIR = os.path.join(DATA_DIR, "charts")
LOGS_DIR = os.path.join(DATA_DIR, "logs")

# Sottodirectory dei report
REPORTS_CSV_DIR = os.path.join(REPORTS_DIR, "csv")
REPORTS_XLSX_DIR = os.path.join(REPORTS_DIR, "xlsx")
REPORTS_PDF_DIR = os.path.join(REPORTS_DIR, "pdf")
REPORTS_DOCX_DIR = os.path.join(REPORTS_DIR, "docx")
REPORTS_HTML_DIR = os.path.join(REPORTS_DIR, "html")

# Directory config (NEL CORSO DI bgy_core, non in core!)
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")

# File JSON di configurazione
CONFIG_DATA = os.path.join(CONFIG_DIR, "config_data.json")
CONFIG_MAIL = os.path.join(CONFIG_DIR, "config_mail.json")
CONFIG_OPENSKY = os.path.join(CONFIG_DIR, "config_opensky.json")
RULES_AIRLINES = os.path.join(CONFIG_DIR, "config_rules_airlines.json")
RULES_COUNTRIES = os.path.join(CONFIG_DIR, "config_rules_countries.json")
RULES_AIRCRAFT_MODELS = os.path.join(CONFIG_DIR, "config_rules_aircraft_models.json")
RULES_NOISE_IMPACT = os.path.join(CONFIG_DIR, "config_noise_impact.json")


def ensure_directories():
    """Crea tutte le directory necessarie se non esistono."""
    dirs = [
        DATA_DIR, RAW_DIR, REPORTS_DIR, CHARTS_DIR, LOGS_DIR,
        REPORTS_CSV_DIR, REPORTS_XLSX_DIR, REPORTS_PDF_DIR,
        REPORTS_DOCX_DIR, REPORTS_HTML_DIR, CONFIG_DIR
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


if __name__ == "__main__":
    ensure_directories()
    print("✅ Tutte le directory sono state create.")
    print(f"📁 PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"📁 CONFIG_DIR: {CONFIG_DIR}")
    print(f"📁 CONFIG_MAIL: {CONFIG_MAIL}")