"""
bgy_scheduler.py - Pianificatore ed Orchestratore automatico.
Versione 2.5.7
- Lock file per impedire doppio avvio
- Radar notturno: SOLO tra le 23:00 e le 05:59
- Sync DB: recupero automatico degli ultimi 8 giorni
- Quality check (F11e) integrato nel job giornaliero
- Statistiche movimenti giorno/notte (F18b) nell'email di stato
"""
import os
import sys
import time
import threading
import subprocess as sp
import pandas as pd
from datetime import datetime, timedelta
import schedule

from bgy_core import get_logger, config_manager
from bgy_core.bgy_paths import LOGS_DIR, RAW_DIR
from bgy_core.bgy_github_sync import sync_to_github
from bgy_core.bgy_mailer import send_daily_status
from bgy_core.bgy_dates import is_night_time
from bgy_reports import (generate_daily_report, generate_nightly_report,
                         send_monthly_report)
from bgy_scanners import run_day_scan, run_night_scan

logger = get_logger("Scheduler")

os.makedirs(LOGS_DIR, exist_ok=True)

_scheduler_lock = threading.Lock()
_scheduler_started = False

SCHEDULER_LOCK_FILE = os.path.join(LOGS_DIR, "scheduler.lock")


# -----------------------------------------------------------------------------
# LOCK FILE
# -----------------------------------------------------------------------------

def _is_pid_alive(pid):
    if sys.platform != "win32":
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
    try:
        result = sp.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True, timeout=5
        )
        output = (result.stdout or "").strip()
        return str(pid) in output and "No tasks" not in output
    except Exception:
        return False


def _read_lock_pid():
    if not os.path.exists(SCHEDULER_LOCK_FILE):
        return None
    try:
        with open(SCHEDULER_LOCK_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return int(content) if content else None
    except (ValueError, IOError):
        return None


def _write_lock_pid(pid):
    try:
        with open(SCHEDULER_LOCK_FILE, "w", encoding="utf-8") as f:
            f.write(str(pid))
        return True
    except Exception as e:
        logger.error(f"Errore scrittura lock file: {e}")
        return False


def acquire_scheduler_lock():
    my_pid = os.getpid()
    existing_pid = _read_lock_pid()

    if existing_pid is not None:
        if _is_pid_alive(existing_pid):
            logger.warning(
                f"⚠️ Un altro scheduler è già in esecuzione (PID {existing_pid}). "
                f"Questo processo (PID {my_pid}) esce."
            )
            return False
        else:
            logger.info(
                f"🔓 Lock stale trovato (PID {existing_pid} non più attivo). "
                f"Lo sostituisco con il mio PID ({my_pid})."
            )

    if not _write_lock_pid(my_pid):
        return False

    logger.info(f"🔒 Lock scheduler acquisito (PID {my_pid})")
    return True


# -----------------------------------------------------------------------------
# UTILITY
# -----------------------------------------------------------------------------
def _get_scheduler_start_time(target_date_str):
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    for days_back in range(0, 8):
        check_date = (target_date - timedelta(days=days_back)).strftime("%Y-%m-%d")
        log_file = os.path.join(LOGS_DIR, f"bgy_app_{check_date}.log")
        if not os.path.exists(log_file):
            continue
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "SCHEDULER BGY - CONFIGURAZIONE" in line:
                        ts = line.split(" - ")[0].strip()
                        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S,%f")
        except Exception:
            continue
    return None


def _classifica_scansione(expected_time, scan_date, scheduler_start):
    scan_date_norm = scan_date
    scan_date_clean = scan_date.replace("-", "")
    hhmm_old = expected_time.replace(":", "")
    hhmm_new = expected_time.replace(":", "-")
    candidates = [
        os.path.join(RAW_DIR, f"scan_{scan_date_norm}_{hhmm_new}.csv"),
        os.path.join(RAW_DIR, f"scan_{scan_date_clean}_{hhmm_old}.csv"),
    ]
    for fp in candidates:
        if os.path.exists(fp):
            return "eseguita", None
    if scheduler_start is not None:
        try:
            exp_dt = datetime.strptime(f"{scan_date} {expected_time}", "%Y-%m-%d %H:%M")
            if exp_dt < scheduler_start:
                return "saltata", scheduler_start.strftime("%d/%m %H:%M")
        except Exception:
            pass
    return "mancante", None


# -----------------------------------------------------------------------------
# CHECK DI PROCESSO
# -----------------------------------------------------------------------------

def check_sacbo_acquisition(date_str):
    config = config_manager.get_data_config()
    expected_times = config.get("scan_schedules", ["00:00", "06:00", "12:00", "18:00"])
    scheduler_start = _get_scheduler_start_time(date_str)
    eseguite, saltate, mancanti = [], [], []
    for t in expected_times:
        stato, info = _classifica_scansione(t, date_str, scheduler_start)
        if stato == "eseguita":
            eseguite.append(t)
        elif stato == "saltata":
            saltate.append((t, info))
        else:
            mancanti.append(t)
    totale = len(expected_times)
    parti = [f"Eseguite {len(eseguite)}/{totale} scansioni diurne"]
    if saltate:
        dettagli = ", ".join([f"{t} (sistema spento fino a {avvio})" for t, avvio in saltate])
        parti.append(f"saltate {len(saltate)}: {dettagli}")
    if mancanti:
        parti.append(f"MANCANTI {len(mancanti)}: {', '.join(mancanti)}")
    msg = ". ".join(parti)
    return (len(mancanti) == 0), msg


def _find_radar_file(date_str):
    for name in (f"radar_{date_str}.csv", f"bgy_night_flights_{date_str}.csv"):
        p = os.path.join(RAW_DIR, name)
        if os.path.exists(p):
            return p
    return None


def check_night_acquisition(date_str):
    config = config_manager.get_data_config()
    night_times = config.get("sacbo_night_scans", ["23:00", "02:00", "05:00"])
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    next_day = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
    scheduler_start = _get_scheduler_start_time(date_str)
    eseguite, saltate, mancanti = [], [], []
    for t in night_times:
        hh = int(t.split(":")[0])
        scan_date = date_str if hh >= 12 else next_day
        stato, info = _classifica_scansione(t, scan_date, scheduler_start)
        if stato == "eseguita":
            eseguite.append(t)
        elif stato == "saltata":
            saltate.append((t, info))
        else:
            mancanti.append(t)
    radar_file = _find_radar_file(date_str)
    radar_ok = False
    radar_msg = ""
    if radar_file:
        try:
            df = pd.read_csv(radar_file)
            if len(df) > 0:
                radar_ok = True
                radar_msg = f"radar OK ({len(df)} rilevamenti)"
            else:
                radar_msg = "file radar vuoto"
        except Exception as e:
            radar_msg = f"errore lettura radar: {e}"
    else:
        radar_msg = "file radar assente"
    totale = len(night_times)
    parti = [f"Scansioni SACBO notturne: {len(eseguite)}/{totale}"]
    if saltate:
        dettagli = ", ".join([f"{t} (sistema spento fino a {avvio})" for t, avvio in saltate])
        parti.append(f"saltate {len(saltate)}: {dettagli}")
    if mancanti:
        parti.append(f"MANCANTI {len(mancanti)}: {', '.join(mancanti)}")
    parti.append(radar_msg)
    msg = ". ".join(parti)
    return (len(mancanti) == 0 and radar_ok), msg


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
    now = datetime.now()
    if not is_night_time(now):
        return
    run_night_scan(check_night_window=True)


def job_daily():
    logger.info("=" * 60)
    logger.info("📊 Avvio routine giornaliera...")
    logger.info("=" * 60)

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    sacbo_acq_ok, sacbo_acq_msg = check_sacbo_acquisition(yesterday)
    logger.info(f"{'✅' if sacbo_acq_ok else '❌'} Acquisizione SACBO diurna ({yesterday}): {sacbo_acq_msg}")

    daily_path, daily_msg = generate_daily_report(yesterday)
    daily_ok = daily_path is not None and os.path.exists(daily_path)
    logger.info(f"{'✅' if daily_ok else '❌'} Elaborazione SACBO ({yesterday}): {daily_msg}")

    night_acq_ok, night_acq_msg = check_night_acquisition(yesterday)
    logger.info(f"{'✅' if night_acq_ok else '❌'} Acquisizione notturna ({yesterday}): {night_acq_msg}")

    nightly_path, nightly_msg = generate_nightly_report(yesterday)
    nightly_ok = nightly_path is not None and os.path.exists(nightly_path)
    logger.info(f"{'✅' if nightly_ok else '❌'} Arricchimento notturno ({yesterday}): {nightly_msg}")

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

    # --- Sync DB: recupero ultimi 8 giorni ---
    logger.info("-" * 60)
    logger.info("🗄️  Avvio sincronizzazione Database (ultimi 8 giorni)...")
    db_ok = False
    db_msg = "Non tentato"
    try:
        from bgy_core.bgy_db_migrate import sync_date
        oggi = datetime.now().date()
        total_imported_all = 0
        total_errors_all = 0
        for i in range(0, 8):
            d = (oggi - timedelta(days=i)).strftime("%Y-%m-%d")
            result = sync_date(d)
            if result is not None:
                total_imported_all += sum(r["imported"] for r in result.values())
                total_errors_all += sum(r["errors"] for r in result.values())
        if total_errors_all == 0:
            db_ok = True
            db_msg = f"Sync DB OK ({total_imported_all} file importati negli ultimi 8 giorni)"
        else:
            db_msg = f"Sync DB con {total_errors_all} errori"
        logger.info(f"{'✅' if db_ok else '⚠️'} {db_msg}")
    except Exception as e:
        db_msg = f"Eccezione: {e}"
        logger.error(f"❌ Errore sync DB: {e}")

    # --- Quality check (F11e) ---
    logger.info("-" * 60)
    logger.info("🔍 Avvio quality check (ultimi 7 giorni)...")
    qc_ok = False
    qc_msg = "Non tentato"
    try:
        from bgy_core.bgy_db_migrate import run_quality_check
        qc_result = run_quality_check(days=7)
        qc_errori = qc_result["riepilogo"]["errori"]
        qc_warnings = qc_result["riepilogo"]["warning"]
        qc_ok = qc_errori == 0
        qc_msg = qc_result["testo_email"]
        logger.info(f"{'✅' if qc_ok else '⚠️'} Quality check: "
                    f"{qc_result['riepilogo']['ok']} OK, "
                    f"{qc_warnings} warning, {qc_errori} errori")
    except Exception as e:
        qc_msg = f"Errore quality check: {e}"
        logger.error(f"❌ {qc_msg}")

    # --- Statistiche movimenti (F18b) ---
    logger.info("-" * 60)
    logger.info("📊 Raccolta statistiche movimenti...")
    stats_data = {"daily": None, "nightly": None}
    try:
        from bgy_core.bgy_db_migrate import get_daily_stats, get_nightly_stats
        stats_data["daily"] = get_daily_stats(yesterday)
        stats_data["nightly"] = get_nightly_stats(yesterday)
        logger.info(f"✅ Statistiche raccolte: "
                    f"giorno={stats_data['daily']['totale']} mov, "
                    f"notte={stats_data['nightly']['totale']} mov")
    except Exception as e:
        logger.error(f"❌ Errore raccolta statistiche: {e}")

    # Riepilogo check
    checks = {
        'sacbo_acquisition': (sacbo_acq_ok, sacbo_acq_msg),
        'sacbo_processing': (daily_ok, daily_msg),
        'night_acquisition': (night_acq_ok, night_acq_msg),
        'night_enrichment': (nightly_ok, nightly_msg),
        'github_sync': (sync_ok, sync_msg),
        'db_sync': (db_ok, db_msg),
        'quality_check': (qc_ok, qc_msg),
    }

    overall_success = all(ok for ok, _ in checks.values())

    logger.info("-" * 60)
    logger.info(f"📋 ESITO COMPLESSIVO: {'✅ TUTTO OK' if overall_success else '❌ PROBLEMI RILEVATI'}")
    logger.info("-" * 60)

    send_daily_status(overall_success, "", checks=checks, stats=stats_data)

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
            logger.warning("⚠️ Scheduler già avviato in questo processo, ignoro richiesta duplicata.")
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
    logger.info(f"📡 Scansione RADAR ogni {interval} minuti, SOLO 23:00-05:59")

    report_time = config.get("daily_report_time", "06:30")
    schedule.every().day.at(report_time).do(job_daily)
    logger.info(f"📊 Report + sync GitHub + sync DB + quality check + email alle {report_time}")

    logger.info("=" * 50)
    logger.info("✅ Scheduler configurato e in esecuzione...")
    logger.info("=" * 50)


def run_scheduler_loop():
    if not acquire_scheduler_lock():
        logger.warning("🛑 Scheduler non avviato: un'altra istanza è già in esecuzione.")
        sys.exit(0)

    setup_scheduler()
    now = datetime.now()
    if is_night_time(now):
        logger.info("🌙 Avvio scansione radar immediata all'avvio...")
        job_radar_night_scan()
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    run_scheduler_loop()