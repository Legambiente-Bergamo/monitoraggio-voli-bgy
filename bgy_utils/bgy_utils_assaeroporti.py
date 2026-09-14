"""
bgy_utils_assaeroporti.py - Download e parsing dati Assaeroporti.
"""
import os
import requests
from datetime import datetime

from core.bgy_logger import get_logger
from core.bgy_paths import RAW_DIR

logger = get_logger("Assaeroporti")

# URL della pagina statistiche
ASSAEROPORTI_URL = "https://assaeroporti.com/statistiche/"


def download_assaeroporti_data(year=None):
    """
    Scarica i dati di traffico Assaeroporti per un anno.
    Nota: il sito pubblica file Excel mensili. Il download automatico
    richiede parsing HTML per trovare i link.
    """
    if not year:
        year = datetime.now().year - 1

    logger.info(f"📥 Download dati Assaeroporti {year}...")

    try:
        resp = requests.get(ASSAEROPORTI_URL, timeout=30)
        if resp.status_code != 200:
            logger.error(f"Errore HTTP: {resp.status_code}")
            return None

        # Salva HTML per parsing
        html_path = os.path.join(RAW_DIR, f"assaeroporti_{year}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(resp.text)
        logger.info(f"💾 HTML salvato: {html_path}")

        return html_path

    except Exception as e:
        logger.error(f"Errore download: {e}")
        return None


def get_bgy_official_stats(year=None):
    """
    Restituisce le statistiche ufficiali BGY per l'anno specificato.
    Nota: i dati vanno inseriti manualmente o parsati dal PDF/Excel.
    """
    # Dati noti (fonte: comunicati stampa SACBO/Assaeroporti)
    stats = {
        2024: {"passeggeri": 17300000, "movimenti": 120000, "cargo_ton": 23000},
        2025: {"passeggeri": 16900000, "movimenti": 115000, "cargo_ton": 24531},
    }
    return stats.get(year, {})


# Carica al primo import
logger.info("📊 Modulo Assaeroporti pronto")