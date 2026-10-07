"""
bgy_scheduler.py - Pianificatore ed Orchestratore automatico.
Versione 2.8.3

Novità v2.8.3 (INFRA-02, 07/10/2026):
- job_daily() ora chiama bgy_tools.verify_sync.check_all() e passa il
  risultato a send_daily_status(sync_backup_check=...).
- La nuova sezione "📊 STATO SYNC E BACKUP" appare nell'email delle 06:30
  con: stato GitHub, backup DB (Google Drive), backup locale (HD esterno).
- Se verify_sync.check_all() fallisce, la mail parte comunque: la sezione
  viene omessa con un warning nel log.

Novità v2.8.2 (radar 1 min di notte):
- job_radar_scan(): intervallo adattivo. In fascia notturna (23:00-06:00)
  esegue ogni minuto; di giorno esegue solo ai minuti pari.
- setup_scheduler(): legge night_scan_interval_minutes (default 1) e
  day_scan_interval_minutes (default 2).
- Import: aggiunta is_night_time.

Novità v2.8.1 (F17 WordPress): job_daily() chiama export_and_publish().
Novità v2.8.0 (email semplificata + non classificati).
Novità v2.7.3: night_import_failed dal check 10.
Novità v2.7.2: check_sacbo_acquisition() conta scansioni Avionio.

- Lock file per impedire doppio avvio
- Radar h24 multi-fonte (adsb.lol -> adsb.fi -> airplanes.live -> OpenSky)
- Sync DB: recupero automatico degli ultimi 8 giorni
- Quality check (F11e) integrato nel job giornaliero
- Email di stato con: problemi check + movimenti notte + voli non classificati
- Verifica compagnie da risolvere (F14)
- Diagnostica scanner diurno Cloudflare (F14b)
- Screenshot tabellone allegati all'email + rotazione 7 giorni (F14c)
- Recupero automatico scansioni mancate (v2.6.2)
- Confronto incrociato Avionio (v2.6.4)
- Check 11 servizio DB (v2.6.6)
- Radar h24 (v2.7.0)
- Check 12 backup DB (v2.7.1)
- Avviso scansioni da fonte alternativa Avionio (v2.7.2)
- Passaggio flag night_import_failed al mailer (v2.7.3)
- Esportazione dati web F17 (v2.8.1)
- Sync e backup check nell'email del mattino (v2.8.3)
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
from bgy_core.bgy_mailer import send_daily_status
from bgy_core.bgy_dates import is_night_time, night_session_date
from bgy_reports import (generate_daily_report, generate_nightly_report,
                         send_monthly_report)
from bgy_scanners import run_day_scan, run_radar_scan

logger = get_logger("Scheduler")

os.makedirs(LOGS_DIR, exist_ok=True)

_scheduler_lock = threading.Lock()
_scheduler_started = False

SCHEDULER_LOCK_FILE = os.path.join(LOGS_DIR, "scheduler.lock")
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
# AVIONIO
# -----------------------------------------------------------------------------

def _run_avionio_scan():
    try:
        from bgy_scanners.bgy_scanner_alt import run_scan_alt
        results = run_scan_alt("both")
        n_arr = results.get("arrivals", {}).get("count", 0)
        n_dep = results.get("departures", {}).get("count", 0)
        logger.info(f"✅ Avionio scan: {n_arr} arrivi, {n_dep} partenze")
        return True
    except Exception as e:
        logger.error(f"❌ Errore Avionio scan: {e}")
        return False


def _run_avionio_comparison(trigger=""):
    try:
        from bgy_tools.confronto_sacbo_avionio import run_confronto_summary
        ok, msg = run_confronto_summary()
        first = msg.split("\n")[0]
        logger.info(f"{'✅' if ok else '⚠️'} Confronto Avionio [{trigger}]: {first}")
        return ok, msg
    except Exception as e:
        logger.error(f"❌ Errore confronto Avionio: {e}")
        return True, f"Errore confronto: {str(e)[:80]}"


def _run_avionio_after_scan(trigger):
    cfg = _cfg_avionio()
    if not cfg.get("enabled", True):
        return
    if not cfg.get("run_at_every_scan", True):
        return
    _run_avionio_scan()
    _run_avionio_comparison(trigger=trigger)


def cleanup_old_avionio(days=7):
    try:
        from bgy_scanners.bgy_scanner_alt import cleanup_old_files
        return cleanup_old_files(days=days)
    except Exception as e:
        logger.error(f"Errore cleanup Avionio: {e}")
        return 0


# -----------------------------------------------------------------------------
# WEB EXPORT (F17)
# -----------------------------------------------------------------------------

def job_web_export():
    """
    Rigenera il JSON aggregato (bgy-data.csv) e lo pubblica su WordPress.
    F17 - Opzione A: JSON statico su Media Library, niente DB esposto.

    Non influenza l'esito complessivo del job giornaliero: se fallisce,
    viene loggato un errore ma il job prosegue.
    """
    logger.info("-" * 60)
    logger.info("🌐 Esportazione dati web (F17)...")

    web_cfg = _cfg_web_export()
    days = int(web_cfg.get("days_default", 90))

    try:
        from bgy_core.bgy_export_web import export_and_publish
        ok, msg = export_and_publish(days=days)
        if ok:
            logger.info(f"✅ Web export: {msg}")
        else:
            logger.error(f"❌ Web export: {msg}")
        return ok, msg
    except Exception as e:
        msg = f"Eccezione: {e}"
        logger.error(f"❌ Web export: {msg}")
        return False, msg


# -----------------------------------------------------------------------------
# SYNC / BACKUP CHECK (v2.8.3)
# -----------------------------------------------------------------------------

def _run_sync_backup_check():
    """
    v2.8.3: esegue bgy_tools.verify_sync.check_all() e ritorna il dict
    oppure None in caso di errore. Non blocca il job giornaliero.
    """
    try:
        from bgy_tools.verify_sync import check_all
        result = check_all()
        if result.get("overall_ok"):
            logger.info("✅ Sync/Backup: tutto OK")
        else:
            g = result.get("github", {}).get("status", "?")
            b = result.get("backup_db", {}).get("status", "?")
            bl = result.get("backup_local", {}).get("status", "?")
            logger.warning(f"⚠️ Sync/Backup: problemi "
                            f"(github={g}, backup_db={b}, backup_local={bl})")
        return result
    except Exception as e:
        logger.error(f"❌ Errore verify_sync.check_all: {e}")
        return None


# -----------------------------------------------------------------------------
# RECOVERY STATE
# -----------------------------------------------------------------------------

def _load_recovery_state():
    if not os.path.exists(RECOVERY_STATE_FILE):
        return {"attempted": []}
    try:
        with open(RECOVERY_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "attempted" not in data:
            data["attempted"] = []
        return data
    except Exception:
        return {"attempted": []}


def _save_recovery_state(state):
    try:
        os.makedirs(os.path.dirname(RECOVERY_STATE_FILE), exist_ok=True)
        with open(RECOVERY_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Errore salvataggio recovery state: {e}")


def _cleanup_recovery_state(state):
    cutoff = (datetime.now() - timedelta(days=RECOVERY_MAX_AGE_DAYS)).strftime("%Y-%m-%d")
    attempted = state.get("attempted", [])
    state["attempted"] = [s for s in attempted if s[:10] >= cutoff]
    return state


# -----------------------------------------------------------------------------
# SCAN SLOTS
# -----------------------------------------------------------------------------

def _all_scheduled_slots():
    config = config_manager.get_data_config()
    slots = list(config.get("scan_schedules", ["02:00", "06:00", "10:00", "14:00", "18:00", "22:00"]))
    if config.get("sacbo_night_scan_enabled", True):
        slots += list(config.get("sacbo_night_scans", ["23:00", "02:00", "05:00"]))
    return slots


def _parse_scan_filename_dt(filename):
    base = filename.replace(".csv", "")
    m = re.match(r'^scan_(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})$', base)
    if m:
        try:
            return datetime.strptime(
                f"{m.group(1)} {m.group(2)}:{m.group(3)}", "%Y-%m-%d %H:%M"
            )
        except Exception:
            return None
    m = re.match(r'^scan_(\d{8})_(\d{4})$', base)
    if m:
        try:
            ymd = m.group(1)
            hhmm = m.group(2)
            return datetime.strptime(
                f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]} {hhmm[:2]}:{hhmm[2:]}",
                "%Y-%m-%d %H:%M"
            )
        except Exception:
            return None
    return None


def _latest_scan_file_dt():
    if not os.path.isdir(RAW_DIR):
        return None
    candidates = []
    for f in os.listdir(RAW_DIR):
        if not (f.startswith("scan_") and f.endswith(".csv")):
            continue
        dt = _parse_scan_filename_dt(f)
        if dt:
            candidates.append(dt)
    return max(candidates) if candidates else None


def _last_expected_scan_time(now):
    slots = _all_scheduled_slots()
    today = now.date()
    yesterday = today - timedelta(days=1)
    candidates = []
    for sched in slots:
        try:
            hh, mm = map(int, sched.split(":"))
            for day in (yesterday, today):
                dt = datetime.combine(
                    day, datetime.min.time().replace(hour=hh, minute=mm)
                )
                if dt <= now:
                    candidates.append(dt)
        except Exception:
            continue
    return max(candidates) if candidates else None


def _next_scheduled_scan_time(now):
    slots = _all_scheduled_slots()
    candidates = []
    for sched in slots:
        try:
            hh, mm = map(int, sched.split(":"))
            dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if dt > now:
                candidates.append(dt)
            else:
                candidates.append(dt + timedelta(days=1))
        except Exception:
            continue
    return min(candidates) if candidates else None


def _detect_missed_scan(now):
    last_expected = _last_expected_scan_time(now)
    if not last_expected:
        return None
    last_actual = _latest_scan_file_dt()
    if last_actual is None:
        return last_expected.strftime("%Y-%m-%d %H:%M")
    if last_actual >= last_expected:
        return None
    return last_expected.strftime("%Y-%m-%d %H:%M")


# -----------------------------------------------------------------------------
# RECOVERY SCHEDULING
# -----------------------------------------------------------------------------

def _recovery_tag(slot_key):
    return f"recovery_{slot_key.replace(' ', '_').replace(':', '')}"


def _schedule_recovery(slot_key):
    if not slot_key:
        return False
    state = _load_recovery_state()
    if slot_key in state.get("attempted", []):
        logger.info(f"⏭️ Recupero {slot_key} già tentato, skip")
        return False

    now = datetime.now()
    next_sched = _next_scheduled_scan_time(now)
    if next_sched:
        gap_min = (next_sched - now).total_seconds() / 60
        if gap_min < RECOVERY_MIN_GAP_MIN:
            logger.info(
                f"⏭️ Recupero {slot_key} saltato: "
                f"prossima scansione tra {int(gap_min)} min "
                f"(< {RECOVERY_MIN_GAP_MIN} min)"
            )
            return False

    tag = _recovery_tag(slot_key)
    schedule.every(RECOVERY_DELAY_SEC).seconds.do(
        job_recovery_scan, slot_key=slot_key
    ).tag(tag)

    state.setdefault("attempted", []).append(slot_key)
    state = _cleanup_recovery_state(state)
    _save_recovery_state(state)

    logger.info(f"🔄 Recupero pianificato per slot {slot_key} tra {RECOVERY_DELAY_SEC}s")
    return True


def _check_and_schedule_recovery(trigger="unknown"):
    now = datetime.now()
    missed_slot = _detect_missed_scan(now)
    if not missed_slot:
        logger.info(f"✅ Nessuna scansione mancante da recuperare (trigger: {trigger})")
        return
    logger.info(f"🔍 Scansione mancante rilevata: {missed_slot} (trigger: {trigger})")
    _schedule_recovery(missed_slot)


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


def _read_fonte_scan_from_csv(filepath):
    try:
        with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
            reader = __import__("csv").DictReader(f)
            for row in reader:
                fonte = (row.get("fonte_scan") or "").strip().lower()
                if fonte in ("sacbo", "avionio"):
                    return fonte
                return "sacbo"
    except Exception:
        pass
    return "sacbo"


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
            fonte = _read_fonte_scan_from_csv(fp)
            return "eseguita", fonte
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
    expected_times = config.get("scan_schedules", ["02:00", "06:00", "10:00", "14:00", "18:00", "22:00"])
    scheduler_start = _get_scheduler_start_time(date_str)
    eseguite, saltate, mancanti = [], [], []
    fonti = {"sacbo": 0, "avionio": 0}

    for t in expected_times:
        stato, info = _classifica_scansione(t, date_str, scheduler_start)
        if stato == "eseguita":
            eseguite.append(t)
            if info in ("sacbo", "avionio"):
                fonti[info] += 1
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

    n_avionio = fonti.get("avionio", 0)
    if n_avionio > 0:
        parti.append(
            f"⚠️ {n_avionio} scansioni su {len(eseguite)} da fonte "
            f"alternativa (Avionio) — copertura parziale"
        )

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
    fonti = {"sacbo": 0, "avionio": 0}

    for t in night_times:
        hh = int(t.split(":")[0])
        scan_date = date_str if hh >= 12 else next_day
        stato, info = _classifica_scansione(t, scan_date, scheduler_start)
        if stato == "eseguita":
            eseguite.append(t)
            if info in ("sacbo", "avionio"):
                fonti[info] += 1
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

    n_avionio = fonti.get("avionio", 0)
    if n_avionio > 0:
        parti.append(f"⚠️ {n_avionio} scansioni notturne da Avionio")

    msg = ". ".join(parti)
    return (len(mancanti) == 0 and radar_ok), msg


def check_scanner_day_status():
    if not os.path.exists(SCANNER_STATUS_FILE):
        return True, "Nessuna scansione registrata"
    try:
        with open(SCANNER_STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return True, f"Impossibile leggere status: {str(e)[:60]}"

    ts = data.get("timestamp", "?")
    challenge = data.get("challenge_superato", False)
    clicked = data.get("tab_arrivi_cliccato", False)
    changed = data.get("body_arrivi_cambiato", False)
    n_d = int(data.get("n_decolli", 0))
    n_a = int(data.get("n_arrivi", 0))
    is_recovery = bool(data.get("is_recovery", False))
    recovered_slot = data.get("recovered_slot")
    fonte = data.get("fonte_scan", "sacbo")
    fallback_attivato = bool(data.get("fallback_attivato", False))

    if is_recovery:
        suffix = (f" — 🔄 Recupero di {recovered_slot}"
                  if recovered_slot else " — 🔄 Recupero")
    else:
        suffix = f" — ultima scansione {ts}"

    if fonte == "avionio":
        return True, (f"⚠️ OK da FONTE ALTERNATIVA (Avionio) "
                      f"({n_d} D + {n_a} A){suffix}")

    if challenge and clicked and changed and n_d > 0 and n_a > 0:
        return True, f"OK ({n_d} D + {n_a} A){suffix}"

    problemi = []
    if not challenge:
        problemi.append("Challenge Cloudflare non superato")
    elif not clicked:
        problemi.append("Tab 'Arrivi' non cliccabile")
    elif not changed:
        problemi.append("Click su 'Arrivi' eseguito ma contenuto non cambiato")
    if n_a == 0:
        problemi.append(f"Nessun arrivo estratto (D={n_d}, A={n_a})")
    if n_d == 0:
        problemi.append(f"Nessun decollo estratto (D={n_d}, A={n_a})")

    dettaglio = " | ".join(problemi) if problemi else "Stato scanner non chiaro"
    msg = (
        f"⚠️ Ultima scansione ({ts}){suffix}: {dettaglio}\n"
        f"   D={n_d}, A={n_a}\n"
        f"   → Esegui: py -3.12 -m bgy_tools.test_sacbo_stealth"
    )
    return False, msg


def check_backup():
    if not os.path.exists(BACKUP_LOG_FILE):
        return False, "Nessun log di backup trovato"

    last_success = None
    try:
        with open(BACKUP_LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "Backup completato con successo" in line:
                    parts = line.split(" - ", 1)
                    if parts:
                        last_success = parts[0].strip()
    except Exception as e:
        return False, f"Errore lettura log backup: {str(e)[:80]}"

    if not last_success:
        return False, "Nessun backup completato con successo nel log"

    try:
        success_dt = datetime.strptime(last_success, "%Y-%m-%d %H:%M:%S")
        age_hours = (datetime.now() - success_dt).total_seconds() / 3600
        if age_hours > BACKUP_MAX_AGE_HOURS:
            return False, (f"Ultimo backup OK: {last_success} "
                           f"({age_hours:.1f}h fa, soglia {BACKUP_MAX_AGE_HOURS}h)")
        return True, f"Backup OK: {last_success} ({age_hours:.1f}h fa)"
    except Exception as e:
        return False, f"Errore parsing timestamp backup: {str(e)[:80]}"


# -----------------------------------------------------------------------------
# SCREENSHOT
# -----------------------------------------------------------------------------

def _get_session_screenshots(session_date):
    if not os.path.isdir(SCREENSHOTS_DIR):
        return None, None

    def _find_by_suffix(prefix, date_str, scan_time):
        if not date_str:
            return None
        date_variants = [date_str]
        if "-" in date_str:
            date_variants.append(date_str.replace("-", ""))
        for dv in date_variants:
            for tm in [scan_time, scan_time.replace("-", "")]:
                candidate = os.path.join(SCREENSHOTS_DIR, f"{prefix}_{dv}_{tm}.png")
                if os.path.exists(candidate):
                    return candidate
        return None

    dep_23 = _find_by_suffix("board_dep", session_date, "23-00")
    arr_23 = _find_by_suffix("board_arr", session_date, "23-00")

    if dep_23 and arr_23:
        logger.info(f"📸 Screenshot 23:00 trovati per {session_date}")
        return dep_23, arr_23

    logger.warning(
        f"⚠️ Screenshot 23:00 non trovati per {session_date} "
        f"(dep={'ok' if dep_23 else 'mancante'}, "
        f"arr={'ok' if arr_23 else 'mancante'}). Fallback al più recente."
    )

    dep_candidates, arr_candidates = [], []
    try:
        for f in os.listdir(SCREENSHOTS_DIR):
            if not f.endswith(".png"):
                continue
            full = os.path.join(SCREENSHOTS_DIR, f)
            try:
                mtime = os.path.getmtime(full)
                if f.startswith("board_dep_"):
                    dep_candidates.append((mtime, full))
                elif f.startswith("board_arr_"):
                    arr_candidates.append((mtime, full))
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Errore scansione screenshots: {e}")
        return dep_23, arr_23

    dep = max(dep_candidates, key=lambda x: x[0])[1] if dep_candidates else dep_23
    arr = max(arr_candidates, key=lambda x: x[0])[1] if arr_candidates else arr_23
    return dep, arr


def cleanup_old_screenshots(days=7):
    if not os.path.isdir(SCREENSHOTS_DIR):
        return 0, 0
    cutoff = datetime.now() - timedelta(days=days)
    n_removed = 0
    n_errors = 0
    try:
        for f in os.listdir(SCREENSHOTS_DIR):
            if not f.endswith(".png"):
                continue
            full = os.path.join(SCREENSHOTS_DIR, f)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(full))
                if mtime < cutoff:
                    os.remove(full)
                    n_removed += 1
            except Exception as e:
                logger.warning(f"Errore rimozione screenshot {f}: {e}")
                n_errors += 1
    except Exception as e:
        logger.error(f"Errore pulizia screenshots: {e}")
        return 0, 1
    return n_removed, n_errors


# -----------------------------------------------------------------------------
# JOB
# -----------------------------------------------------------------------------

def job_scan(slot=None):
    logger.info(f"📡 Avvio scansione SACBO diurna... (slot {slot})")
    success = False
    try:
        result = run_day_scan()
        success = result is not None
    except Exception as e:
        logger.error(f"❌ Eccezione scansione diurna (slot {slot}): {e}")

    if success:
        logger.info(f"✅ Scansione diurna {slot} completata")
        _run_avionio_after_scan(trigger=f"scan_{slot}")
    else:
        logger.warning(f"⚠️ Scansione diurna {slot} fallita, pianifico recupero")
        now = datetime.now()
        slot_key = f"{now.strftime('%Y-%m-%d')} {slot}" if slot else None
        _schedule_recovery(slot_key)


def job_sacbo_night_scan(slot=None):
    config = config_manager.get_data_config()
    if not config.get("sacbo_night_scan_enabled", True):
        logger.info("🌙 Scansioni SACBO notturne disabilitate")
        return

    logger.info(f"🌙 Avvio scansione SACBO notturna... (slot {slot})")
    success = False
    try:
        result = run_day_scan()
        success = result is not None
    except Exception as e:
        logger.error(f"❌ Eccezione scansione notturna (slot {slot}): {e}")

    if success:
        logger.info(f"✅ Scansione notturna {slot} completata")
        _run_avionio_after_scan(trigger=f"night_{slot}")
    else:
        logger.warning(f"⚠️ Scansione notturna {slot} fallita, pianifico recupero")
        now = datetime.now()
        session_date = night_session_date(now)
        slot_key = f"{session_date} {slot}" if slot else None
        _schedule_recovery(slot_key)


def job_recovery_scan(slot_key=None):
    if not slot_key:
        logger.warning("⚠️ Recupero senza slot_key, abort")
        return

    tag = _recovery_tag(slot_key)
    schedule.clear(tag)

    logger.info(f"🔄 Esecuzione recupero scansione {slot_key}")
    try:
        run_day_scan(is_recovery=True, recovered_slot=slot_key)
        logger.info(f"✅ Recupero {slot_key} completato")
    except Exception as e:
        logger.error(f"❌ Errore recupero {slot_key}: {e}")


def job_radar_scan():
    """
    Scansione radar h24 ad intervallo adattivo.

    v2.8.2: la scansione è schedulata ogni 1 minuto, ma:
    - In fascia notturna (23:00-06:00): esegue ogni minuto
    - In fascia diurna: esegue solo ai minuti pari (0, 2, 4, ...)
      per mantenere l'intervallo effettivo di 2 minuti
    """
    try:
        now = datetime.now()
        is_night = is_night_time(now)
        if not is_night and (now.minute % 2 != 0):
            logger.debug(f"⏭️ Radar skip (diurno, minuto {now.minute} dispari)")
            return
        run_radar_scan()
    except Exception as e:
        logger.error(f"❌ Eccezione scansione radar: {e}")


def job_daily():
    logger.info("=" * 60)
    logger.info("📊 Avvio routine giornaliera...")
    logger.info("=" * 60)

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # --- 1. Acquisizione SACBO diurna ---
    sacbo_acq_ok, sacbo_acq_msg = check_sacbo_acquisition(yesterday)
    logger.info(f"{'✅' if sacbo_acq_ok else '❌'} Acquisizione SACBO diurna ({yesterday}): {sacbo_acq_msg}")

    # --- 2. Elaborazione report diurno ---
    daily_path, daily_msg = generate_daily_report(yesterday)
    daily_ok = daily_path is not None and os.path.exists(daily_path)
    logger.info(f"{'✅' if daily_ok else '❌'} Elaborazione SACBO ({yesterday}): {daily_msg}")

    # --- 3. Acquisizione notturna ---
    night_acq_ok, night_acq_msg = check_night_acquisition(yesterday)
    logger.info(f"{'✅' if night_acq_ok else '❌'} Acquisizione notturna ({yesterday}): {night_acq_msg}")

    # --- 4. Arricchimento notturno ---
    nightly_path, nightly_msg = generate_nightly_report(yesterday)
    nightly_ok = nightly_path is not None and os.path.exists(nightly_path)
    logger.info(f"{'✅' if nightly_ok else '❌'} Arricchimento notturno ({yesterday}): {nightly_msg}")

    # --- 5. Sync GitHub ---
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

    # --- 6. Sync Database ---
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

    # --- 7. Quality check ---
    logger.info("-" * 60)
    logger.info("🔍 Avvio quality check (ultimi 7 giorni)...")
    qc_ok = False
    qc_msg = "Non tentato"
    night_import_failed = False
    try:
        from bgy_core.bgy_db_migrate import run_quality_check
        qc_result = run_quality_check(days=7)
        qc_errori = qc_result["riepilogo"]["errori"]
        qc_warnings = qc_result["riepilogo"]["warning"]
        qc_ok = qc_errori == 0
        qc_msg = qc_result["testo_email"]
        for check in qc_result.get("checks", []):
            if check.get("id") == 10 and not check.get("ok", True):
                night_import_failed = True
                break
        logger.info(f"{'✅' if qc_ok else '⚠️'} Quality check: "
                    f"{qc_result['riepilogo']['ok']} OK, "
                    f"{qc_warnings} warning, {qc_errori} errori")
        if night_import_failed:
            logger.warning("⚠️ Rilevato errore di coerenza CSV vs DB: "
                           "l'import notturno potrebbe essere incompleto")
    except Exception as e:
        qc_msg = f"Errore quality check: {e}"
        logger.error(f"❌ {qc_msg}")

    # --- 8. Compagnie da risolvere ---
    logger.info("-" * 60)
    logger.info("🏢 Verifica compagnie da risolvere...")
    ua_ok = True
    ua_msg = "Non tentato"
    try:
        from bgy_core.bgy_db_migrate import check_unresolved_airlines
        data_cfg = config_manager.get_data_config()
        threshold = int(
            data_cfg.get("notifications", {}).get("unresolved_airlines_days", 30)
        )
        ua_ok, ua_msg = check_unresolved_airlines(days_threshold=threshold)
        first_line = ua_msg.split(chr(10))[0]
        logger.info(f"{'✅' if ua_ok else '⚠️'} {first_line}")
    except Exception as e:
        ua_msg = f"Errore verifica compagnie: {e}"
        logger.error(f"❌ {ua_msg}")

    # --- 9. Diagnostica scanner diurno ---
    logger.info("-" * 60)
    logger.info("🩺 Diagnostica scanner diurno...")
    sc_ok = True
    sc_msg = "Non tentato"
    try:
        sc_ok, sc_msg = check_scanner_day_status()
        first_line = sc_msg.split(chr(10))[0]
        logger.info(f"{'✅' if sc_ok else '⚠️'} {first_line}")
    except Exception as e:
        sc_msg = f"Errore diagnostica scanner: {e}"
        logger.error(f"❌ {sc_msg}")

    # --- 10. Confronto Avionio ---
    logger.info("-" * 60)
    logger.info("🔍 Confronto incrociato Avionio...")
    av_ok = True
    av_msg = "Non tentato"
    try:
        av_cfg = _cfg_avionio()
        if av_cfg.get("enabled", True):
            _run_avionio_scan()
            av_ok, av_msg = _run_avionio_comparison(trigger="daily")
            first_line = av_msg.split(chr(10))[0]
            logger.info(f"{'✅' if av_ok else '⚠️'} {first_line}")
        else:
            av_msg = "Avionio disabilitato in config"
            logger.info(f"⏭️ {av_msg}")
    except Exception as e:
        av_msg = f"Errore confronto Avionio: {e}"
        logger.error(f"❌ {av_msg}")

    # --- 11. Statistiche notturne + voli non classificati ---
    logger.info("-" * 60)
    logger.info("📊 Raccolta statistiche notturne...")
    stats_data = {"nightly": None}
    non_classified_flights = []
    try:
        from bgy_core.bgy_db_migrate import (get_nightly_stats,
                                              get_non_classified_flights)
        stats_data["nightly"] = get_nightly_stats(yesterday)
        non_classified_flights = get_non_classified_flights(yesterday)
        n_night = stats_data["nightly"]["totale"] if stats_data["nightly"] else 0
        logger.info(f"✅ Statistiche raccolte: notte={n_night} mov, "
                    f"non classificati={len(non_classified_flights)}")
    except Exception as e:
        logger.error(f"❌ Errore raccolta statistiche: {e}")

    # --- 12. Screenshot tabellone ---
    logger.info("-" * 60)
    logger.info(f"📸 Raccolta screenshot tabellone (sessione {yesterday}, 23:00)...")
    screenshot_paths = []
    try:
        dep_shot, arr_shot = _get_session_screenshots(yesterday)
        if dep_shot:
            screenshot_paths.append(dep_shot)
        if arr_shot:
            screenshot_paths.append(arr_shot)
        logger.info(f"✅ Screenshot trovati: {len(screenshot_paths)} "
                    f"(dep={'sì' if dep_shot else 'no'}, "
                    f"arr={'sì' if arr_shot else 'no'})")
    except Exception as e:
        logger.error(f"❌ Errore raccolta screenshot: {e}")

    # --- 13. Verifica servizio Database ---
    logger.info("-" * 60)
    logger.info("🗄️  Verifica servizio Database...")
    db_svc_ok = True
    db_svc_msg = "Non tentato"
    try:
        from bgy_core import bgy_db_service
        status, status_msg = bgy_db_service.get_service_status()
        db_ok2, db_msg2 = bgy_db_service.is_db_reachable()
        db_svc_ok = (status == "Running" and db_ok2)
        if db_svc_ok:
            db_svc_msg = f"OK ({status}, DB raggiungibile)"
        else:
            db_svc_msg = (f"Servizio: {status}\n"
                          f"DB raggiungibile: {db_ok2}\n"
                          f"Dettaglio: {db_msg2[:100]}")
        logger.info(f"{'✅' if db_svc_ok else '⚠️'} {db_svc_msg}")
    except Exception as e:
        db_svc_msg = f"Errore verifica servizio DB: {e}"
        logger.error(f"❌ {db_svc_msg}")

    # --- 14. Verifica backup DB ---
    logger.info("-" * 60)
    logger.info("💾 Verifica backup DB...")
    bk_ok = True
    bk_msg = "Non tentato"
    try:
        bk_ok, bk_msg = check_backup()
        logger.info(f"{'✅' if bk_ok else '❌'} {bk_msg}")
    except Exception as e:
        bk_msg = f"Errore verifica backup: {e}"
        logger.error(f"❌ {bk_msg}")

    # --- 15. Sync/Backup check (INFRA-02, v2.8.3) ---
    logger.info("-" * 60)
    logger.info("📊 Verifica sync GitHub + stato backup...")
    sync_backup_check = _run_sync_backup_check()
    if sync_backup_check is not None:
        g_status = sync_backup_check.get("github", {}).get("status", "?")
        b_status = sync_backup_check.get("backup_db", {}).get("status", "?")
        bl_status = sync_backup_check.get("backup_local", {}).get("status", "?")
        logger.info(f"✅ Sync/Backup: github={g_status}, "
                    f"backup_db={b_status}, backup_local={bl_status}")

    # --- Riepilogo check ---
    checks = {
        'sacbo_acquisition': (sacbo_acq_ok, sacbo_acq_msg),
        'sacbo_processing': (daily_ok, daily_msg),
        'night_acquisition': (night_acq_ok, night_acq_msg),
        'night_enrichment': (nightly_ok, nightly_msg),
        'github_sync': (sync_ok, sync_msg),
        'db_sync': (db_ok, db_msg),
        'quality_check': (qc_ok, qc_msg),
        'unresolved_airlines': (ua_ok, ua_msg),
        'scanner_day_status': (sc_ok, sc_msg),
        'avionio_confronto': (av_ok, av_msg),
        'db_service': (db_svc_ok, db_svc_msg),
        'backup': (bk_ok, bk_msg),
    }

    overall_success = all(
        ok for k, (ok, _) in checks.items()
        if k not in WARNING_ONLY_CHECKS
    )

    logger.info("-" * 60)
    logger.info(f"📋 ESITO COMPLESSIVO: {'✅ TUTTO OK' if overall_success else '❌ PROBLEMI RILEVATI'}")
    logger.info("-" * 60)

    # --- Invio email ---
    send_daily_status(
        overall_success, "",
        checks=checks,
        stats=stats_data,
        screenshot_paths=screenshot_paths,
        night_import_failed=night_import_failed,
        non_classified_flights=non_classified_flights,
        sync_backup_check=sync_backup_check,
    )

    # --- 16. Esportazione dati web (F17) ---
    job_web_export()

    # --- Pulizie ---
    logger.info("-" * 60)
    logger.info("🧹 Pulizia screenshot vecchi (>7 giorni)...")
    try:
        n_rem, n_err = cleanup_old_screenshots(days=7)
        logger.info(f"✅ Rimossi {n_rem} screenshot vecchi ({n_err} errori)")
    except Exception as e:
        logger.error(f"❌ Errore pulizia screenshot: {e}")

    logger.info("🧹 Pulizia file Avionio vecchi (>7 giorni)...")
    try:
        av_cfg = _cfg_avionio()
        days_ret = int(av_cfg.get("retention_days", 7))
        n_av = cleanup_old_avionio(days=days_ret)
        logger.info(f"✅ Rimossi {n_av} file Avionio vecchi")
    except Exception as e:
        logger.error(f"❌ Errore pulizia Avionio: {e}")

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

    for t in config.get("scan_schedules", ["02:00", "06:00", "10:00", "14:00", "18:00", "22:00"]):
        schedule.every().day.at(t).do(job_scan, slot=t)
        logger.info(f"📡 Scansione SACBO diurna alle {t}")

    if config.get("sacbo_night_scan_enabled", True):
        for t in config.get("sacbo_night_scans", ["23:00", "02:00", "05:00"]):
            schedule.every().day.at(t).do(job_sacbo_night_scan, slot=t)
            logger.info(f"🌙 Scansione SACBO notturna alle {t}")

    # v2.8.2: intervallo adattivo. Il job viene schedulato ogni 1 minuto,
    # ma job_radar_scan() filtra i minuti dispari diurni per mantenere 2 min.
    night_interval = int(config.get("night_scan_interval_minutes", 1))
    day_interval = int(config.get("day_scan_interval_minutes", 2))
    base_interval = min(night_interval, day_interval)

    if base_interval < 1:
        base_interval = 1
        logger.warning(f"⚠️ Intervallo radar base non valido, forzo a 1 min")

    schedule.every(base_interval).minutes.do(job_radar_scan)
    logger.info(f"📡 Scansione RADAR ogni {night_interval} min (notte 23:00-06:00) / "
                f"{day_interval} min (giorno) - schedule base: {base_interval} min")

    report_time = config.get("daily_report_time", "06:30")
    schedule.every().day.at(report_time).do(job_daily)
    logger.info(f"📊 Report + sync + quality + compagnie + diagnostica "
                f"+ Avionio + screenshot + backup + email + web export alle {report_time}")

    logger.info("=" * 50)
    logger.info("✅ Scheduler configurato e in esecuzione...")
    logger.info("=" * 50)


def run_scheduler_loop():
    if not acquire_scheduler_lock():
        logger.warning("🛑 Scheduler non avviato: un'altra istanza è già in esecuzione.")
        sys.exit(0)

    setup_scheduler()

    try:
        _check_and_schedule_recovery("startup")
    except Exception as e:
        logger.error(f"Errore check recovery startup: {e}")

    logger.info("📡 Avvio scansione radar immediata all'avvio...")
    try:
        job_radar_scan()
    except Exception as e:
        logger.error(f"Errore scansione radar iniziale: {e}")

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    run_scheduler_loop()