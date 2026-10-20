"""
bgy_scheduler.py - Pianificatore ed Orchestratore automatico.
Versione 2.8.11

Novità v2.8.11 (RADAR-08, 20/10/2026):
- job_daily() chiama enrich_runways() per arricchire le piste N/D
  usando le tracce radar locali, prima del sync DB e dell'invio email.

Novità v2.8.10 (MAIL-05, 19/10/2026):
- job_daily() chiama send_h24_alert() se generate_h24_report() fallisce.
...
"""
import os
import sys
import json
import re
import time
import threading
import subprocess as sp
import pandas as pd
from datetime import datetime, timedelta
import schedule

from bgy_core import get_logger, config_manager
from bgy_core.bgy_paths import LOGS_DIR, RAW_DIR
from bgy_core.bgy_github_sync import sync_to_github
from bgy_core.bgy_mailer import send_daily_status, send_h24_alert
from bgy_core.bgy_dates import is_night_time, night_session_date
from bgy_reports import (generate_daily_report, generate_nightly_report,
                         send_monthly_report, generate_h24_report)
from bgy_scanners import run_day_scan, run_radar_scan
from bgy_tools.radar_trace_enricher import enrich_runways

logger = get_logger("Scheduler")

os.makedirs(LOGS_DIR, exist_ok=True)

# ... [tutte le altre variabili globali e funzioni rimangono identiche] ...

def job_daily():
    logger.info("📊 Avvio routine giornaliera...")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    cfg_ok, cfg_msg = _check_config_load_status()
    logger.info(f"{'✅' if cfg_ok else '⚠️'} Config load: {cfg_msg}")
    
    sacbo_ok, sacbo_msg = check_sacbo_acquisition(yesterday)
    daily_path, daily_msg = generate_daily_report(yesterday)
    daily_ok = daily_path is not None and os.path.exists(daily_path)
    logger.info(f"{'✅' if daily_ok else '❌'} Report diurno: {daily_msg}")
    
    night_ok, night_msg = check_night_acquisition(yesterday)
    nightly_path, nightly_msg = generate_nightly_report(yesterday)
    nightly_ok = nightly_path is not None and os.path.exists(nightly_path)
    logger.info(f"{'✅' if nightly_ok else '❌'} Report notturno: {nightly_msg}")

    # RADAR-08: Arricchimento piste
    if nightly_ok:
        try:
            enrich_ok, enrich_msg = enrich_runways(yesterday)
            logger.info(f"{'✅' if enrich_ok else '⚠️'} Arricchimento piste: {enrich_msg}")
        except Exception as e:
            logger.error(f"❌ Errore arricchimento piste: {e}")

    h24_path, h24_msg = generate_h24_report(yesterday)
    h24_ok = h24_path is not None and os.path.exists(h24_path)
    logger.info(f"{'✅' if h24_ok else '❌'} Report H24: {h24_msg}")

    if not h24_ok:
        try:
            send_h24_alert(reason=h24_msg)
        except Exception as e:
            logger.error(f"❌ Impossibile inviare H24 alert: {e}")
    
    # ... [il resto del codice rimane identico] ...