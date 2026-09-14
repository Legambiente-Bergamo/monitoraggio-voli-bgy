"""
bgy_scheduler.py - Pianificatore ed Orchestratore automatico.
Finestra notturna: 23:00 - 05:59
v2.3.8: sync GitHub PRIMA dell'email + 5° check nella mail
"""
import os
import sys
import time
import threading
import pandas as pd
from datetime import datetime, timedelta
import schedule

from core import get_logger, config_manager
from core.bgy_paths import LOGS_DIR, RAW_DIR
from core.bgy_github_sync import sync_to_github
from bgy_utils.bgy_utils_mailer import send_daily_status
from bgy_reports import generate_daily_report, generate_nightly_report, send_monthly_report
from scanners import run_day_scan, run_night_scan

logger = get_logger("Scheduler")

os.makedirs(LOGS_DIR, exist_ok=True)

_scheduler_lock = threading.Lock()
_scheduler_started = False


# -----------------------------------------------------------------------------
# CHECK DI PROCESSO
# -----------------------------------------------------------------------------

def check_sacbo_acquisition(date_str):
    """Verifica che le scansioni SACBO previste per la data siano state eseguite."""
    date_clean = date_str.replace("-", "")
    config = config_manager.get_data_config()
    expected_times = config.get("scan_schedules", ["00:00", "06:00", "12:00", "18:00"])

    now = datetime.now()
    is_today = (date_str == now.strftime("%Y-%m-%d"))
    now_minutes = now.hour * 60 + now.minute

    due_times = []
    for t in expected_times:
        try:
            hh, mm = t.split(":")
            exp_min = int(hh) * 60 + int(mm)
        except Exception:
            continue
        if not is_today or exp_min <= now_minutes:
            due_times.append(t)

    if not due_times:
        return True, f"Nessuna scansione ancora dovuta (prossima: {expected_times[0]})"

    scan_files = [f for f in os.listdir(RAW_DIR)
                  if f.startswith(f"scan_{date_clean}_") and f.endswith(".csv")]

    if not scan_files:
        return False, f"Nessuna scansione SACBO trovata per il {date_str}"

    actual_minutes = []
    for f in scan_files:
        try:
            parts = f.replace(".csv", "").split("_")
            hhmm = parts[2]
            actual_minutes.append(int(hhmm[:2]) * 60 + int(hhmm[2:]))
        except Exception:
            continue

    missing = []
    for expected in due_times:
        try:
            hh, mm = expected.split(":")
            exp_min = int(hh) * 60 + int(mm)
        except Exception:
            continue
        if not any(abs(exp_min - am) <= 60 for am in actual_minutes):
            missing.append(expected)

    total = len(due_times)
    found = total - len(missing)
    if not missing:
        return True, f"Tutte le {total} scansioni dovute eseguite ({found}/{total})"
    return False, f"Eseguite {found}/{total} scansioni. Mancanti: {', '.join(missing)}"


def check_night_acquisition(date_str):
    """Verifica che esistano dati radar notturni per la data."""
    filepath = os.path.join(RAW_DIR, f"bgy_night_flights_{date_str}.csv")
    if not os.path.exists(filepath):
        return False, f"Nessun file radar per la notte del {date_str}"

    try:
        df = pd.read_csv(filepath)
        if len(df) == 0:
            return False, "File radar presente ma vuoto"
        return True, f"Trovati {len(df)} rilevamenti radar"
    except Exception as e:
        return False, f"Errore lettura file radar: {e}"


# -----------------------------------------------------------------------------
# JOB
# -----------------------------------------------------------------------------

def job_scan():
    logger.info("📡 Avvio scansione SACBO diurna...")
    run_day_scan()


def job_sacbo_night_scan():
    config = config_manager.get_data_config()
    if config.get("sacbo_night_scan_enabled", True):
        logger.info("🌙 Avvio scansione SACBO notturna...")
        run_day_scan()
    else:
        logger.info("🌙 Scansioni SACBO notturne disabilitate")


def job_radar_night_scan():
    run_night_scan(check_night_window=True)


def job_daily():
    logger.info("=" * 60)
    logger.info("📊 Avvio routine giornaliera...")
    logger.info("=" * 60)

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # 1. Verifica acquisizione SACBO
    sacbo_acq_ok, sacbo_acq_msg = check_sacbo_acquisition(yesterday)
    logger.info(f"{'✅' if sacbo_acq_ok else '❌'} Acquisizione SACBO ({yesterday}): {sacbo_acq_msg}")

    # 2. Elaborazione report giornaliero
    daily_path, daily_msg = generate_daily_report()
    daily_ok = daily_path is not None and os.path.exists(daily_path)
    logger.info(f"{'✅' if daily_ok else '❌'} Elaborazione SACBO: {daily_msg}")

    # 3. Verifica acquisizione notturna
    night_acq_ok, night_acq_msg = check_night_acquisition(yesterday)
    logger.info(f"{'✅' if night_acq_ok else '❌'} Acquisizione notturna ({yesterday}): {night_acq_msg}")

    # 4. Arricchimento report notturno
    nightly_path, nightly_msg = generate_nightly_report(yesterday)
    nightly_ok = nightly_path is not None and os.path.exists(nightly_path)
    logger.info(f"{'✅' if nightly_ok else '❌'} Arricchimento notturno: {nightly_msg}")

    # 5. SYNC GITHUB (PRIMA dell'email)
    logger.info("-" * 60)
    logger.info("📤 Avvio sincronizzazione GitHub...")
    try:
        sync_ok, sync_msg = sync_to_github()
        if sync_ok:
            logger.info(f"✅ Sync GitHub: {sync_msg}")
        else:
            logger.warning(f"⚠️ Sync GitHub fallito: {sync_msg}")
    except Exception as e:
        sync_ok = False
        sync_msg = f"Eccezione: {e}"
        logger.error(f"❌ Errore sync GitHub: {e}")

    # 6. Riepilogo check (5 check ora)
    checks = {
        'sacbo_acquisition': (sacbo_acq_ok, sacbo_acq_msg),
        'sacbo_processing': (daily_ok, daily_msg),
        'night_acquisition': (night_acq_ok, night_acq_msg),
        'night_enrichment': (nightly_ok, nightly_msg),
        'github_sync': (sync_ok, sync_msg),
    }

    overall_success = all(ok for ok, _ in checks.values())

    logger.info("-" * 60)
    logger.info(f"📋 ESITO COMPLESSIVO: {'✅ TUTTO OK' if overall_success else '❌ PROBLEMI RILEVATI'}")
    logger.info("-" * 60)

    # 7. Invio email di stato (con 5 check)
    send_daily_status(overall_success, "", checks=checks)

    # 8. Report mensile (primo del mese)
    if datetime.now().day == 1:
        logger.info("📈 Primo del mese: generazione report mensile...")
        send_monthly_report()


# -----------------------------------------------------------------------------
# SCHEDULER
# -----------------------------------------------------------------------------

def setup_scheduler():
    global _scheduler_started

    with _scheduler_lock:
        if _scheduler_started:
            logger.warning("⚠️ Scheduler già avviato, ignoro richiesta duplicata.")
            return
        _scheduler_started = True

    schedule.clear()

    config = config_manager.get_data_config()

    logger.info("=" * 50)
    logger.info("⏰ SCHEDULER BGY - CONFIGURAZIONE")
    logger.info("=" * 50)

    for t in config.get("scan_schedules", ["00:00", "06:00", "12:00", "18:00"]):
        schedule.every().day.at(t).do(job_scan)
        logger.info(f"📡 Scansione SACBO diurna alle {t}")

    if config.get("sacbo_night_scan_enabled", True):
        for t in config.get("sacbo_night_scans", ["23:00", "02:00", "05:00"]):
            schedule.every().day.at(t).do(job_sacbo_night_scan)
            logger.info(f"🌙 Scansione SACBO notturna alle {t}")

    interval = config.get("night_scan_interval_minutes", 2)
    schedule.every(interval).minutes.do(job_radar_night_scan)
    logger.info(f"📡 Scansione RADAR ogni {interval} minuti (23:00-05:59)")

    report_time = config.get("daily_report_time", "06:30")
    schedule.every().day.at(report_time).do(job_daily)
    logger.info(f"📊 Report + sync GitHub + email alle {report_time}")

    logger.info("=" * 50)
    logger.info("✅ Scheduler configurato e in esecuzione...")
    logger.info("=" * 50)


def run_scheduler_loop():
    """Loop principale dello scheduler (da eseguire in un thread)."""
    setup_scheduler()

    now = datetime.now()
    if now.hour >= 23 or now.hour < 6:
        logger.info("🌙 Avvio scansione radar immediata all'avvio...")
        job_radar_night_scan()

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    run_scheduler_loop()