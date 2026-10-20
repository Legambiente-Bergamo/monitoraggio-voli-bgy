"""
bgy_scheduler.py - Pianificatore ed Orchestratore automatico.
Versione 2.8.14

Novità v2.8.14 (20/10/2026):
- Radar misto: 20 secondi di notte, 2 minuti di giorno.
  Il job viene schedulato ogni 20 secondi, ma job_radar_scan() 
  salta l'esecuzione di giorno se non sono passati almeno 120 secondi.

Novità v2.8.13:
- Radar solo notturno: job_radar_scan() esce subito se non è is_night_time.
- Frequenza notturna portata a 20 secondi.

Novità v2.8.12 (INFRA-16):
- Aggiunto thread di heartbeat.
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

_scheduler_lock = threading.Lock()
_scheduler_started = False
_last_day_radar_run = None

SCHEDULER_LOCK_FILE = os.path.join(LOGS_DIR, "scheduler.lock")
HEARTBEAT_FILE = os.path.join(LOGS_DIR, "scheduler_heartbeat.txt")
SCANNER_STATUS_FILE = os.path.join(LOGS_DIR, "scanner_day_status.json")
SCREENSHOTS_DIR = os.path.join(os.path.dirname(LOGS_DIR), "bgy_screenshots")
RECOVERY_STATE_FILE = os.path.join(LOGS_DIR, "recovery_state.json")
AVIONIO_DIR = os.path.join(os.path.dirname(LOGS_DIR), "bgy_avionio")
BACKUP_LOG_FILE = os.path.join(LOGS_DIR, "backup.log")

PREFERRED_SCREENSHOT_HOUR = "23-00"
RECOVERY_DELAY_SEC = 300
RECOVERY_MIN_GAP_MIN = 60
RECOVERY_MAX_AGE_DAYS = 7
BACKUP_MAX_AGE_HOURS = 36

WARNING_ONLY_CHECKS = {'avionio_confronto', 'backup'}


def _heartbeat_loop():
    """Scrive il timestamp corrente nel file di heartbeat ogni 60 secondi."""
    while True:
        try:
            with open(HEARTBEAT_FILE, "w", encoding="utf-8") as f:
                f.write(datetime.now().isoformat())
        except Exception as e:
            logger.error(f"Errore scrittura heartbeat: {e}")
        time.sleep(60)


def _cfg_avionio():
    try:
        cfg = config_manager.get_data_config()
        return cfg.get("avionio", {}) or {}
    except Exception:
        return {}

def _cfg_web_export():
    try:
        cfg = config_manager.get_data_config()
        return cfg.get("web_export", {}) or {}
    except Exception:
        return {}

def _is_pid_alive(pid):
    if sys.platform != "win32":
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
    try:
        result = sp.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, timeout=5)
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
            logger.warning(f"⚠️ Un altro scheduler è già in esecuzione (PID {existing_pid}). Esco.")
            return False
        else:
            logger.info(f"🔓 Lock stale trovato (PID {existing_pid}). Lo sostituisco.")
    if not _write_lock_pid(my_pid): return False
    logger.info(f"🔒 Lock scheduler acquisito (PID {my_pid})")
    return True

def _run_avionio_scan():
    try:
        from bgy_scanners.bgy_scanner_alt import run_scan_alt
        results = run_scan_alt("both")
        logger.info(f"✅ Avionio scan: {results.get('arrivals', {}).get('count', 0)} arrivi, {results.get('departures', {}).get('count', 0)} partenze")
        return True
    except Exception as e:
        logger.error(f"❌ Errore Avionio scan: {e}")
        return False

def _run_avionio_comparison(trigger=""):
    try:
        from bgy_tools.confronto_sacbo_avionio import run_confronto_summary
        ok, msg = run_confronto_summary()
        logger.info(f"{'✅' if ok else '⚠️'} Confronto Avionio [{trigger}]: {msg.split(chr(10))[0]}")
        return ok, msg
    except Exception as e:
        return True, f"Errore confronto: {str(e)[:80]}"

def _run_avionio_import_db():
    try:
        from bgy_core.bgy_db_migrate import import_avionio_scan_to_db
        ok, msg = import_avionio_scan_to_db()
        if ok: logger.info(f"✅ Avionio import DB: {msg}")
        else: logger.warning(f"⚠️ Avionio import DB: {msg}")
        return ok, msg
    except Exception as e:
        logger.error(f"❌ Errore import Avionio DB: {e}")
        return False, str(e)

def _run_avionio_after_scan(trigger):
    cfg = _cfg_avionio()
    if not cfg.get("enabled", True) or not cfg.get("run_at_every_scan", True): return
    _run_avionio_scan()
    if cfg.get("import_to_db", False): _run_avionio_import_db()
    _run_avionio_comparison(trigger=trigger)

def cleanup_old_avionio(days=7):
    try:
        from bgy_scanners.bgy_scanner_alt import cleanup_old_files
        return cleanup_old_files(days=days)
    except Exception as e:
        return 0

def job_web_export():
    web_cfg = _cfg_web_export()
    days = int(web_cfg.get("days_default", 90))
    
    try:
        from bgy_core.bgy_export_web import export_and_publish
        ok_night, msg = export_and_publish(days=days)
        logger.info(f"{'✅' if ok_night else '❌'} Web export notturno: {msg}")
    except Exception as e: logger.error(f"❌ Web export notturno: {e}")
    
    try:
        from bgy_core.bgy_export_web import export_delays_and_publish
        ok_delays, msg = export_delays_and_publish(days=days)
        logger.info(f"{'✅' if ok_delays else '❌'} Web export ritardi: {msg}")
    except Exception as e: logger.error(f"❌ Web export ritardi: {e}")
    
    try:
        from bgy_core.bgy_disclaimer import export_and_publish_disclaimer
        ok_disc, msg = export_and_publish_disclaimer()
        logger.info(f"{'✅' if ok_disc else '❌'} Web export disclaimer: {msg}")
    except Exception as e: logger.error(f"❌ Web export disclaimer: {e}")

def _run_sync_backup_check():
    try:
        from bgy_tools.verify_sync import check_all
        return check_all()
    except Exception:
        return None

def _check_config_load_status():
    try: errors = config_manager.get_load_errors()
    except Exception as e: return False, str(e)
    if not errors: return True, "OK"
    return False, "\n".join([f"{e.get('file')} [{e.get('timestamp')}]: {e.get('message')}" for e in errors])

def _load_recovery_state():
    if not os.path.exists(RECOVERY_STATE_FILE): return {"attempted": []}
    try:
        with open(RECOVERY_STATE_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {"attempted": []}

def _save_recovery_state(state):
    try:
        with open(RECOVERY_STATE_FILE, "w", encoding="utf-8") as f: json.dump(state, f, indent=2)
    except: pass

def _cleanup_recovery_state(state):
    cutoff = (datetime.now() - timedelta(days=RECOVERY_MAX_AGE_DAYS)).strftime("%Y-%m-%d")
    state["attempted"] = [s for s in state.get("attempted", []) if s[:10] >= cutoff]
    return state

def _all_scheduled_slots():
    config = config_manager.get_data_config()
    slots = list(config.get("scan_schedules", ["02:00", "06:00", "10:00", "14:00", "18:00", "22:00"]))
    if config.get("sacbo_night_scan_enabled", True): slots += list(config.get("sacbo_night_scans", ["23:00", "02:00", "05:00"]))
    return slots

def _parse_scan_filename_dt(filename):
    base = filename.replace(".csv", "")
    m = re.match(r'^scan_(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})$', base)
    if m: return datetime.strptime(f"{m.group(1)} {m.group(2)}:{m.group(3)}", "%Y-%m-%d %H:%M")
    m = re.match(r'^scan_(\d{8})_(\d{4})$', base)
    if m: return datetime.strptime(f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:8]} {m.group(2)[:2]}:{m.group(2)[2:]}", "%Y-%m-%d %H:%M")
    return None

def _latest_scan_file_dt():
    if not os.path.isdir(RAW_DIR): return None
    candidates = [_parse_scan_filename_dt(f) for f in os.listdir(RAW_DIR) if f.startswith("scan_") and f.endswith(".csv")]
    valid = [c for c in candidates if c]
    return max(valid) if valid else None

def _last_expected_scan_time(now):
    slots = _all_scheduled_slots(); today = now.date(); yesterday = today - timedelta(days=1)
    candidates = []
    for sched in slots:
        try:
            hh, mm = map(int, sched.split(":"))
            for day in (yesterday, today):
                dt = datetime.combine(day, datetime.min.time().replace(hour=hh, minute=mm))
                if dt <= now: candidates.append(dt)
        except: continue
    return max(candidates) if candidates else None

def _next_scheduled_scan_time(now):
    slots = _all_scheduled_slots(); candidates = []
    for sched in slots:
        try:
            hh, mm = map(int, sched.split(":"))
            dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            candidates.append(dt if dt > now else dt + timedelta(days=1))
        except: continue
    return min(candidates) if candidates else None

def _detect_missed_scan(now):
    last_expected = _last_expected_scan_time(now)
    if not last_expected: return None
    last_actual = _latest_scan_file_dt()
    if last_actual is None or last_actual < last_expected:
        return last_expected.strftime("%Y-%m-%d %H:%M")
    return None

def _recovery_tag(slot_key): return f"recovery_{slot_key.replace(' ', '_').replace(':', '')}"

def _schedule_recovery(slot_key):
    if not slot_key: return False
    state = _load_recovery_state()
    if slot_key in state.get("attempted", []): return False
    now = datetime.now(); next_sched = _next_scheduled_scan_time(now)
    if next_sched and (next_sched - now).total_seconds() / 60 < RECOVERY_MIN_GAP_MIN: return False
    
    tag = _recovery_tag(slot_key)
    schedule.every(RECOVERY_DELAY_SEC).seconds.do(job_recovery_scan, slot_key=slot_key).tag(tag)
    state.setdefault("attempted", []).append(slot_key)
    _save_recovery_state(_cleanup_recovery_state(state))
    return True

def _check_and_schedule_recovery(trigger="unknown"):
    missed_slot = _detect_missed_scan(datetime.now())
    if missed_slot: _schedule_recovery(missed_slot)

def _get_scheduler_start_time(target_date_str):
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    for days_back in range(0, 8):
        check_date = (target_date - timedelta(days=days_back)).strftime("%Y-%m-%d")
        log_file = os.path.join(LOGS_DIR, f"bgy_app_{check_date}.log")
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "SCHEDULER BGY - CONFIGURAZIONE" in line:
                        return datetime.strptime(line.split(" - ")[0].strip(), "%Y-%m-%d %H:%M:%S,%f")
    return None

def _read_fonte_scan_from_csv(filepath):
    try:
        with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
            for row in __import__("csv").DictReader(f):
                fonte = (row.get("fonte_scan") or "").strip().lower()
                return fonte if fonte in ("sacbo", "avionio") else "sacbo"
    except: pass
    return "sacbo"

def _classifica_scansione(expected_time, scan_date, scheduler_start):
    candidates = [
        os.path.join(RAW_DIR, f"scan_{scan_date}_{expected_time.replace(':', '-')}.csv"),
        os.path.join(RAW_DIR, f"scan_{scan_date.replace('-', '')}_{expected_time.replace(':', '')}.csv"),
    ]
    for fp in candidates:
        if os.path.exists(fp): return "eseguita", _read_fonte_scan_from_csv(fp)
    if scheduler_start:
        try:
            if datetime.strptime(f"{scan_date} {expected_time}", "%Y-%m-%d %H:%M") < scheduler_start:
                return "saltata", scheduler_start.strftime("%d/%m %H:%M")
        except: pass
    return "mancante", None

def check_sacbo_acquisition(date_str):
    config = config_manager.get_data_config()
    expected_times = config.get("scan_schedules", ["02:00", "06:00", "10:00", "14:00", "18:00", "22:00"])
    scheduler_start = _get_scheduler_start_time(date_str)
    eseguite, saltate, mancanti = [], [], []
    fonti = {"sacbo": 0, "avionio": 0}
    for t in expected_times:
        stato, info = _classifica_scansione(t, date_str, scheduler_start)
        if stato == "eseguita":
            eseguite.append(t)
            if info in fonti: fonti[info] += 1
        elif stato == "saltata": saltate.append((t, info))
        else: mancanti.append(t)
    msg = f"Eseguite {len(eseguite)}/{len(expected_times)} scansioni diurne."
    if saltate: msg += f" Saltate {len(saltate)}."
    if mancanti: msg += f" MANCANTI {len(mancanti)}: {', '.join(mancanti)}."
    return (len(mancanti) == 0), msg

def _find_radar_file(date_str):
    for name in (f"radar_{date_str}.csv", f"bgy_night_flights_{date_str}.csv"):
        if os.path.exists(os.path.join(RAW_DIR, name)): return os.path.join(RAW_DIR, name)
    return None

def check_night_acquisition(date_str):
    config = config_manager.get_data_config()
    night_times = config.get("sacbo_night_scans", ["23:00", "02:00", "05:00"])
    date_obj = datetime.strptime(date_str, "%Y-%m-%d"); next_day = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
    scheduler_start = _get_scheduler_start_time(date_str)
    eseguite, saltate, mancanti = [], [], []
    for t in night_times:
        scan_date = date_str if int(t.split(":")[0]) >= 12 else next_day
        stato, info = _classifica_scansione(t, scan_date, scheduler_start)
        if stato == "eseguita": eseguite.append(t)
        elif stato == "saltata": saltate.append((t, info))
        else: mancanti.append(t)
    radar_ok = False; radar_msg = "file radar assente"
    radar_file = _find_radar_file(date_str)
    if radar_file:
        try:
            if len(pd.read_csv(radar_file)) > 0: radar_ok = True; radar_msg = "radar OK"
        except: pass
    msg = f"Scansioni notturne: {len(eseguite)}/{len(night_times)}. {radar_msg}."
    if mancanti: msg += f" MANCANTI: {', '.join(mancanti)}."
    return (len(mancanti) == 0 and radar_ok), msg

def check_scanner_day_status():
    if not os.path.exists(SCANNER_STATUS_FILE): return True, "Nessuna scansione"
    try:
        with open(SCANNER_STATUS_FILE, "r", encoding="utf-8") as f: data = json.load(f)
    except: return True, "Impossibile leggere status"
    ts = data.get("timestamp", "?"); n_d = int(data.get("n_decolli", 0)); n_a = int(data.get("n_arrivi", 0))
    if data.get("fonte_scan") == "avionio": return True, f"⚠️ OK da Avionio ({n_d} D + {n_a} A)"
    if data.get("challenge_superato") and n_d > 0 and n_a > 0: return True, f"OK ({n_d} D + {n_a} A) — {ts}"
    return False, f"⚠️ Ultima scansione ({ts}): D={n_d}, A={n_a}"

def check_backup():
    if not os.path.exists(BACKUP_LOG_FILE): return False, "Nessun log backup"
    last_success = None
    with open(BACKUP_LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "Backup completato con successo" in line: last_success = line.split(" - ")[0].strip()
    if not last_success: return False, "Nessun backup OK"
    try:
        success_dt = datetime.strptime(last_success, "%Y-%m-%d %H:%M:%S")
        age_hours = (datetime.now() - success_dt).total_seconds() / 3600
        if age_hours > BACKUP_MAX_AGE_HOURS: return False, f"Ultimo backup OK: {last_success} ({age_hours:.1f}h fa)"
        return True, f"Backup OK: {last_success} ({age_hours:.1f}h fa)"
    except: return False, "Errore parsing timestamp"

def _get_session_screenshots(session_date):
    if not os.path.isdir(SCREENSHOTS_DIR): return None, None
    def _find(prefix, tm):
        for dv in [session_date, session_date.replace("-", "")]:
            for t in [tm, tm.replace("-", "")]:
                c = os.path.join(SCREENSHOTS_DIR, f"{prefix}_{dv}_{t}.png")
                if os.path.exists(c): return c
        return None
    dep = _find("board_dep", "23-00"); arr = _find("board_arr", "23-00")
    return dep, arr

def job_scan(slot=None):
    logger.info(f"📡 Scansione SACBO diurna... (slot {slot})")
    try:
        if run_day_scan() is not None:
            logger.info(f"✅ Scansione diurna {slot} completata")
            _run_avionio_after_scan(trigger=f"scan_{slot}")
        else: _schedule_recovery(f"{datetime.now().strftime('%Y-%m-%d')} {slot}")
    except Exception as e: logger.error(f"❌ Eccezione scansione diurna: {e}")

def job_sacbo_night_scan(slot=None):
    if not config_manager.get_data_config().get("sacbo_night_scan_enabled", True): return
    logger.info(f"🌙 Scansione SACBO notturna... (slot {slot})")
    try:
        if run_day_scan() is not None:
            logger.info(f"✅ Scansione notturna {slot} completata")
            _run_avionio_after_scan(trigger=f"night_{slot}")
        else: _schedule_recovery(f"{night_session_date(datetime.now())} {slot}")
    except Exception as e: logger.error(f"❌ Eccezione scansione notturna: {e}")

def job_recovery_scan(slot_key=None):
    if not slot_key: return
    schedule.clear(_recovery_tag(slot_key))
    try: run_day_scan(is_recovery=True, recovered_slot=slot_key)
    except Exception as e: logger.error(f"❌ Errore recupero: {e}")

def job_radar_scan():
    """
    v2.8.14: Esegue il radar con logica mista.
    - Di notte: esegue sempre (la schedule chiama ogni 20 secondi).
    - Di giorno: esegue solo se sono passati almeno 120 secondi dall'ultima esecuzione.
    """
    global _last_day_radar_run
    try:
        now = datetime.now()
        if is_night_time(now):
            run_radar_scan()
        else:
            if _last_day_radar_run is None or (now - _last_day_radar_run).total_seconds() >= 120:
                _last_day_radar_run = now
                run_radar_scan()
    except Exception as e: logger.error(f"❌ Eccezione scansione radar: {e}")

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
    
    try:
        sync_ok, sync_msg = sync_to_github()
        logger.info(f"{'✅' if sync_ok else '⚠️'} Sync GitHub: {sync_msg}")
    except Exception as e: sync_ok = False; sync_msg = str(e)
    
    try:
        from bgy_core.bgy_db_migrate import sync_date
        oggi = datetime.now().date(); total_imported_all = 0; total_errors_all = 0
        for i in range(0, 8):
            d = (oggi - timedelta(days=i)).strftime("%Y-%m-%d")
            result = sync_date(d)
            if result:
                total_imported_all += sum(r["imported"] for r in result.values())
                total_errors_all += sum(r["errors"] for r in result.values())
        db_ok = (total_errors_all == 0); db_msg = f"Sync DB OK ({total_imported_all} file)"
    except Exception as e: db_ok = False; db_msg = str(e)
    
    try:
        from bgy_core.bgy_db_migrate import run_quality_check
        qc_result = run_quality_check(days=7)
        qc_ok = (qc_result["riepilogo"]["errori"] == 0)
        qc_msg = qc_result["testo_email"]
        night_import_failed = any(c.get("id") == 10 and not c.get("ok") for c in qc_result.get("checks", []))
    except Exception as e: qc_ok = False; qc_msg = str(e); night_import_failed = False

    try:
        from bgy_core.bgy_db_migrate import check_unresolved_airlines
        ua_ok, ua_msg = check_unresolved_airlines(days_threshold=30)
    except Exception as e: ua_ok = True; ua_msg = str(e)

    sc_ok, sc_msg = check_scanner_day_status()
    
    av_ok = True; av_msg = "Non tentato"
    if _cfg_avionio().get("enabled", True):
        _run_avionio_scan(); av_ok, av_msg = _run_avionio_comparison(trigger="daily")
    
    stats_data = {"nightly": None}; non_classified_flights = []
    try:
        from bgy_core.bgy_db_migrate import get_nightly_stats, get_non_classified_flights
        stats_data["nightly"] = get_nightly_stats(yesterday)
        non_classified_flights = get_non_classified_flights(yesterday)
    except: pass

    dep_shot, arr_shot = _get_session_screenshots(yesterday)
    screenshot_paths = [p for p in (dep_shot, arr_shot) if p]

    try:
        from bgy_core import bgy_db_service
        status, status_msg = bgy_db_service.get_service_status()
        db_svc_ok = (status == "Running" and bgy_db_service.is_db_reachable()[0])
        db_svc_msg = f"OK ({status})" if db_svc_ok else f"KO ({status})"
    except Exception as e: db_svc_ok = True; db_svc_msg = str(e)

    bk_ok, bk_msg = check_backup()
    sync_backup_check = _run_sync_backup_check()

    checks = {
        'config_load': (cfg_ok, cfg_msg),
        'sacbo_acquisition': (sacbo_ok, sacbo_msg),
        'sacbo_processing': (daily_ok, daily_msg),
        'night_acquisition': (night_ok, night_msg),
        'night_enrichment': (nightly_ok, nightly_msg),
        'h24_enrichment': (h24_ok, h24_msg),
        'github_sync': (sync_ok, sync_msg),
        'db_sync': (db_ok, db_msg),
        'quality_check': (qc_ok, qc_msg),
        'unresolved_airlines': (ua_ok, ua_msg),
        'scanner_day_status': (sc_ok, sc_msg),
        'avionio_confronto': (av_ok, av_msg),
        'db_service': (db_svc_ok, db_svc_msg),
        'backup': (bk_ok, bk_msg),
    }

    overall_success = all(ok for k, (ok, _) in checks.items() if k not in WARNING_ONLY_CHECKS)

    send_daily_status(
        overall_success, "",
        checks=checks, stats=stats_data, screenshot_paths=screenshot_paths,
        night_import_failed=night_import_failed,
        non_classified_flights=non_classified_flights,
        sync_backup_check=sync_backup_check,
    )

    job_web_export()

    try:
        av_cfg = _cfg_avionio()
        n_av = cleanup_old_avionio(days=int(av_cfg.get("retention_days", 7)))
        logger.info(f"✅ Rimossi {n_av} file Avionio vecchi")
    except Exception as e: logger.error(f"❌ Errore pulizia Avionio: {e}")

    if datetime.now().day == 1:
        send_monthly_report()

def setup_scheduler():
    global _scheduler_started
    with _scheduler_lock:
        if _scheduler_started: return
        _scheduler_started = True

    schedule.clear()
    config = config_manager.get_data_config()

    for t in config.get("scan_schedules", ["02:00", "06:00", "10:00", "14:00", "18:00", "22:00"]):
        schedule.every().day.at(t).do(job_scan, slot=t)
    if config.get("sacbo_night_scan_enabled", True):
        for t in config.get("sacbo_night_scans", ["23:00", "02:00", "05:00"]):
            schedule.every().day.at(t).do(job_sacbo_night_scan, slot=t)

    # v2.8.14: Imposta la pianificazione radar base ogni 20 secondi.
    # La differenziazione notte/giorno è gestita dentro job_radar_scan().
    night_interval_sec = int(config.get("night_scan_interval_seconds", 20))
    schedule.every(night_interval_sec).seconds.do(job_radar_scan)
    
    schedule.every().day.at(config.get("daily_report_time", "07:30")).do(job_daily)

def run_scheduler_loop():
    if not acquire_scheduler_lock(): sys.exit(0)
    
    threading.Thread(target=_heartbeat_loop, daemon=True).start()
    logger.info("💓 Heartbeat thread avviato.")
    
    setup_scheduler()
    try: _check_and_schedule_recovery("startup")
    except: pass
    try: job_radar_scan()
    except: pass
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    run_scheduler_loop()