"""
bgy_scheduler.py - Pianificatore ed Orchestratore automatico.
Versione 2.6.6
- Lock file per impedire doppio avvio
- Radar notturno: SOLO tra le 23:00 e le 05:59
- Sync DB: recupero automatico degli ultimi 8 giorni
- Quality check (F11e) integrato nel job giornaliero
- Statistiche movimenti giorno/notte (F18b) nell'email di stato
- Verifica compagnie da risolvere (F14) nell'email di stato
- Diagnostica scanner diurno Cloudflare (F14b) nell'email di stato
- Screenshot tabellone allegati all'email + rotazione 7 giorni (F14c)
- Recupero automatico scansioni mancate (v2.6.2)
- Confronto incrociato Avionio (v2.6.4)

Novità v2.6.6 (check 11 servizio DB):
- Aggiunto check 11 "Servizio Database" nell'email di stato 06:30.
- Verifica stato servizio PostgreSQL e raggiungibilità DB.

Novità v2.6.5 (statistiche puntualità):
- Raccolta statistiche di puntualità via get_daily_delay_stats().
- Passaggio a send_daily_status(stats={daily, nightly, delay}).

Novità v2.6.4 (Avionio):
- Esegue scanner Avionio + confronto dopo ogni scansione SACBO
  (se avionio.run_at_every_scan=true, prima settimana).
- Al job 06:30 esegue comunque Avionio + confronto come check 10.
- Check 10 'avionio_confronto' è warning-only: non fa diventare l'email ❌.
- Cleanup cartella bgy_avionio/ a 7 giorni in coda al job_daily.
- Configurazione in config_data.json sezione 'avionio'.

Novità v2.6.3:
- Bump per compatibilità con bgy_db_migrate v2.6.5.

Novità v2.6.2:
- Recupero automatico scansioni mancate.

Novità v2.6.1:
- Fix selezione screenshot: ora vengono presi quelli delle 23:00.
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
from bgy_scanners import run_day_scan, run_night_scan

logger = get_logger("Scheduler")

os.makedirs(LOGS_DIR, exist_ok=True)

_scheduler_lock = threading.Lock()
_scheduler_started = False

SCHEDULER_LOCK_FILE = os.path.join(LOGS_DIR, "scheduler.lock")
SCANNER_STATUS_FILE = os.path.join(LOGS_DIR, "scanner_day_status.json")
SCREENSHOTS_DIR = os.path.join(os.path.dirname(LOGS_DIR), "bgy_screenshots")
RECOVERY_STATE_FILE = os.path.join(LOGS_DIR, "recovery_state.json")
AVIONIO_DIR = os.path.join(os.path.dirname(LOGS_DIR), "bgy_avionio")

PREFERRED_SCREENSHOT_HOUR = "23-00"

RECOVERY_DELAY_SEC = 300
RECOVERY_MIN_GAP_MIN = 60
RECOVERY_MAX_AGE_DAYS = 7

# Check warning-only (non contano in overall_success)
WARNING_ONLY_CHECKS = {'avionio_confronto'}


def _cfg_avionio():
    try:
        cfg = config_manager.get_data_config()
        return cfg.get("avionio", {}) or {}
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
# AVIONIO (v2.6.4)
# -----------------------------------------------------------------------------

def _run_avionio_scan():
    """Esegue lo scanner Avionio (arrivals + departures)."""
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
    """Esegue il confronto SACBO vs Avionio. Ritorna (ok, msg)."""
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
    """Esegue Avionio scan + confronto dopo una scansione SACBO."""
    cfg = _cfg_avionio()
    if not cfg.get("enabled", True):
        return
    if not cfg.get("run_at_every_scan", True):
        return

    _run_avionio_scan()
    _run_avionio_comparison(trigger=trigger)


def cleanup_old_avionio(days=7):
    """Rimuove i file Avionio più vecchi di N giorni."""
    try:
        from bgy_scanners.bgy_scanner_alt import cleanup_old_files
        return cleanup_old_files(days=days)
    except Exception as e:
        logger.error(f"Errore cleanup Avionio: {e}")
        return 0


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
    expected_times = config.get("scan_schedules", ["02:00", "06:00", "10:00", "14:00", "18:00", "22:00"])
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

    if is_recovery:
        suffix = (f" — 🔄 Recupero di {recovered_slot}"
                  if recovered_slot else " — 🔄 Recupero")
    else:
        suffix = f" — ultima scansione {ts}"

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

    logger.info("-" * 60)
    logger.info("📊 Raccolta statistiche movimenti...")
    stats_data = {"daily": None, "nightly": None, "delay": None}
    try:
        from bgy_core.bgy_db_migrate import (get_daily_stats, get_nightly_stats,
                                              get_daily_delay_stats)
        stats_data["daily"] = get_daily_stats(yesterday)
        stats_data["nightly"] = get_nightly_stats(yesterday)
        stats_data["delay"] = get_daily_delay_stats(yesterday)
        d = stats_data["delay"]
        logger.info(f"✅ Statistiche raccolte: "
                    f"giorno={stats_data['daily']['totale']} mov, "
                    f"notte={stats_data['nightly']['totale']} mov, "
                    f"ritardi={d['in_ritardo']}, "
                    f"cancellati={d['cancellati_count']}")
    except Exception as e:
        logger.error(f"❌ Errore raccolta statistiche: {e}")

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

    logger.info("-" * 60)
    logger.info("🗄️  Verifica servizio Database...")
    db_svc_ok = True
    db_svc_msg = "Non tentato"
    try:
        from bgy_core import bgy_db_service
        status, status_msg = bgy_db_service.get_service_status()
        db_ok, db_msg = bgy_db_service.is_db_reachable()
        db_svc_ok = (status == "Running" and db_ok)
        if db_svc_ok:
            db_svc_msg = f"OK ({status}, DB raggiungibile)"
        else:
            db_svc_msg = (f"Servizio: {status}\n"
                          f"DB raggiungibile: {db_ok}\n"
                          f"Dettaglio: {db_msg[:100]}")
        logger.info(f"{'✅' if db_svc_ok else '⚠️'} {db_svc_msg}")
    except Exception as e:
        db_svc_msg = f"Errore verifica servizio DB: {e}"
        logger.error(f"❌ {db_svc_msg}")

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
    }

    overall_success = all(
        ok for k, (ok, _) in checks.items()
        if k not in WARNING_ONLY_CHECKS
    )

    logger.info("-" * 60)
    logger.info(f"📋 ESITO COMPLESSIVO: {'✅ TUTTO OK' if overall_success else '❌ PROBLEMI RILEVATI'}")
    logger.info("-" * 60)

    send_daily_status(overall_success, "", checks=checks, stats=stats_data,
                      screenshot_paths=screenshot_paths)

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

    interval = config.get("night_scan_interval_minutes", 2)
    schedule.every(interval).minutes.do(job_radar_night_scan)
    logger.info(f"📡 Scansione RADAR ogni {interval} minuti, SOLO 23:00-05:59")

    report_time = config.get("daily_report_time", "06:30")
    schedule.every().day.at(report_time).do(job_daily)
    logger.info(f"📊 Report + sync + quality + compagnie + diagnostica "
                f"+ Avionio + screenshot + email alle {report_time}")

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

    now = datetime.now()
    if is_night_time(now):
        logger.info("🌙 Avvio scansione radar immediata all'avvio...")
        job_radar_night_scan()
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    run_scheduler_loop()