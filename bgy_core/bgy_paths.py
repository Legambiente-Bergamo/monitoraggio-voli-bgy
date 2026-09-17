"""
bgy_core/bgy_paths.py - Gestione centralizzata dei percorsi.
Versione 2.5.0 - struttura con prefisso bgy_
"""
import os

CURRENT_FILE = os.path.abspath(__file__)
CORE_DIR = os.path.dirname(CURRENT_FILE)
PROJECT_ROOT = os.path.dirname(CORE_DIR)

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

# --- Alias retrocompatibili ---
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
CONFIG_ASSAEROPORTI = os.path.join(CONFIG_DIR, "config_assaeroporti.json")
CONFIG_ALERT_MESSAGES = os.path.join(CONFIG_DIR, "config_alert_messages.json")
CONFIG_DATABASE = os.path.join(CONFIG_DIR, "config_database.json")
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
    print(f"CONFIG_DIR: {CONFIG_DIR}")
    print(f"CONFIG_DATABASE: {CONFIG_DATABASE}")