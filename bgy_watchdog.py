"""
bgy_watchdog.py - Watchdog per il controllo anomalie BGY Monitoring Suite.
Versione 2.6.0

- Doppio check prima di riavviare lo scheduler (evita falsi positivi)
- Messaggi di alert letti da bgy_config/config_alert_messages.json

Novità v2.6.0 (radar h24):
- check_radar() riscritto per funzionare h24: il file radar_YYYY-MM-DD.csv
  deve essere aggiornato ogni radar_stale_min minuti (default 10),
  indipendentemente dalla fascia oraria.
- Grace period all'avvio: se lo scheduler è partito da meno di
  radar_missing_grace_min minuti (default 15), il file radar mancante
  non genera allarme.
- check_opensky() ora cerca "[ScannerRadar]" invece di "[ScannerNight]".
- check_scheduler() ora verifica la freschezza del log sia di
  "[Scheduler]" che di "[ScannerRadar]", h24.
- Rimosso il check "Fuori dalla finestra notturna" da check_radar().

Novità v2.5.6 (F11e-2 - Database service):
- Aggiunto check 5 "database".

Novità v2.5.5 (fix falsi positivi SACBO stale).

Novità v2.5.4 (radar grace period notturno — superato da v2.6.0).

Novità v2.5.3 (filtro righe [Watchdog] e [Mailer] in check_opensky).
"""
import os
import sys
import json
import subprocess as sp
import time
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import RAW_DIR, LOGS_DIR, PROJECT_ROOT
from bgy_core.bgy_mailer import send_alert
from bgy_core.bgy_dates import is_night_time, night_session_date, radar_filename
from bgy_core.bgy_config_manager import config_manager
from bgy_core import bgy_db_service

logger = get_logger("Watchdog")

STATE_FILE = os.path.join(LOGS_DIR, "watchdog_state.json")
DB_STATE_FILE = os.path.join(LOGS_DIR, "db_service_state.json")
SCHEDULER_SCRIPT = os.path.join(PROJECT_ROOT, "bgy_scheduler.py")

SCHEDULER_DOUBLE_CHECK_DELAY_SEC = 3
DEFAULT_SCAN_SCHEDULES = ["02:00", "06:00", "10:00", "14:00", "18:00", "22:00"]

# Radar h24: se il file non è aggiornato da più di X minuti, è un problema.
DEFAULT_RADAR_STALE_MIN = 10
DEFAULT_RADAR_MISSING_GRACE_MIN = 15


def _cfg():
    return config_manager.get_watchdog_config()


def _db_cfg():
    try:
        cfg = config_manager.get_data_config()
        return cfg.get("database_service", {}) or {}
    except Exception:
        return {}


def _msg(key, **kwargs):
    messages = config_manager.get_alert_messages()
    entry = messages.get(key)
    if not entry:
        return None, None
    subject = entry.get("subject", "")
    body = entry.get("body", "")
    try:
        body = body.format(**kwargs) if kwargs else body
    except Exception as e:
        logger.warning(f"Errore formattazione messaggio '{key}': {e}")
    return subject, body


def _send_alert(key, **kwargs):
    subject, body = _msg(key, **kwargs)
    if not subject:
        subject = f"BGY - {key}"
        body = kwargs.get("fallback_body", "")
    return send_alert(key, subject, body)


# =============================================================================
# STATO
# =============================================================================

def _load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=os.path.dirname(STATE_FILE),
            prefix=".watchdog_state_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, STATE_FILE)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            raise
    except Exception as e:
        logger.error(f"Errore salvataggio stato watchdog: {e}")


def _load_db_state():
    if not os.path.exists(DB_STATE_FILE):
        return {"down_since": None, "restart_attempts": 0}
    try:
        with open(DB_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"down_since": None, "restart_attempts": 0}


def _save_db_state(state):
    try:
        os.makedirs(os.path.dirname(DB_STATE_FILE), exist_ok=True)
        with open(DB_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Errore salvataggio stato DB: {e}")


# =============================================================================
# UTILITY
# =============================================================================

def _get_scheduler_start_time(now):
    for days_back in range(0, 8):
        check_date = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")
        log_file = os.path.join(LOGS_DIR, f"bgy_app_{check_date}.log")
        if not os.path.exists(log_file):
            continue
        try:
            last_ts = None
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "SCHEDULER BGY - CONFIGURAZIONE" in line:
                        ts_str = line.split(" - ")[0].strip()
                        try:
                            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S,%f")
                            if last_ts is None or dt > last_ts:
                                last_ts = dt
                        except Exception:
                            continue
            if last_ts is not None:
                return last_ts
        except Exception:
            continue
    return None


def _last_expected_scan_time(now, scan_schedules):
    today = now.date()
    candidates_today = []
    for sched in scan_schedules:
        try:
            hh, mm = map(int, sched.split(":"))
            dt = datetime.combine(
                today, datetime.min.time().replace(hour=hh, minute=mm)
            )
            if dt <= now:
                candidates_today.append(dt)
        except Exception:
            continue
    if candidates_today:
        return max(candidates_today)

    yesterday = today - timedelta(days=1)
    latest_yesterday = None
    for sched in scan_schedules:
        try:
            hh, mm = map(int, sched.split(":"))
            dt = datetime.combine(
                yesterday, datetime.min.time().replace(hour=hh, minute=mm)
            )
            if latest_yesterday is None or dt > latest_yesterday:
                latest_yesterday = dt
        except Exception:
            continue
    return latest_yesterday


def _is_radar_recently_active(now, window_sec=300, min_hits=1):
    """Verifica se lo scanner radar ha girato di recente (log fresco)."""
    log_file = os.path.join(LOGS_DIR, f"bgy_app_{now.strftime('%Y-%m-%d')}.log")
    if not os.path.exists(log_file):
        return False
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-300:]
        recent = 0
        for line in lines:
            if "ScannerRadar" not in line:
                continue
            if "Avvio scansione" not in line and "File salvato" not in line:
                continue
            try:
                ts_str = line.split(" - ")[0].strip()
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S,%f")
                if (now - ts).total_seconds() < window_sec:
                    recent += 1
            except Exception:
                continue
        return recent >= min_hits
    except Exception:
        return False


# =============================================================================
# CHECK 1 - SACBO
# =============================================================================

def check_sacbo():
    cfg = _cfg()
    max_age = cfg.get("sacbo_max_age_hours", 7)

    data_cfg = config_manager.get_data_config()
    scan_schedules = data_cfg.get("scan_schedules", DEFAULT_SCAN_SCHEDULES)

    try:
        if not os.path.isdir(RAW_DIR):
            return False, f"Cartella RAW non trovata: {RAW_DIR}"

        scan_files = [
            os.path.join(RAW_DIR, f)
            for f in os.listdir(RAW_DIR)
            if f.startswith("scan_") and f.endswith(".csv")
        ]
        if not scan_files:
            msg = "Nessuna scansione SACBO trovata in RAW"
            _send_alert("sacbo_missing")
            return False, msg

        latest = max(scan_files, key=os.path.getmtime)
        latest_dt = datetime.fromtimestamp(os.path.getmtime(latest))
        age_hours = (datetime.now() - latest_dt).total_seconds() / 3600

        if age_hours <= max_age:
            msg = (f"Ultima scansione: {os.path.basename(latest)} "
                   f"({age_hours:.1f}h fa)")
            return True, msg

        now = datetime.now()
        last_expected = _last_expected_scan_time(now, scan_schedules)

        if last_expected is None:
            msg = (f"Ultima scansione SACBO: {os.path.basename(latest)} "
                   f"({age_hours:.1f}h fa)")
            _send_alert("sacbo_stale",
                        ultimo_file=os.path.basename(latest),
                        eta_ore=f"{age_hours:.1f}",
                        soglia_ore=max_age)
            return False, msg

        if latest_dt >= last_expected:
            msg = (f"Ultima scansione: {os.path.basename(latest)} "
                   f"({age_hours:.1f}h fa, entro il ciclo atteso)")
            return True, msg

        scheduler_start = _get_scheduler_start_time(now)

        if scheduler_start is not None and last_expected < scheduler_start:
            msg = (f"Scansione {last_expected.strftime('%H:%M')} saltata "
                   f"(sistema avviato alle {scheduler_start.strftime('%H:%M')})")
            return True, msg

        msg = (f"Ultima scansione SACBO: {os.path.basename(latest)} "
               f"({age_hours:.1f}h fa). "
               f"Scansione attesa {last_expected.strftime('%H:%M')} mancante")
        _send_alert("sacbo_stale",
                    ultimo_file=os.path.basename(latest),
                    eta_ore=f"{age_hours:.1f}",
                    soglia_ore=max_age)
        return False, msg

    except Exception as e:
        return False, f"Errore check SACBO: {e}"


# =============================================================================
# CHECK 2 - RADAR (h24)
# =============================================================================

def check_radar():
    """
    Verifica la freschezza del file radar h24.

    Logica:
      1. Cerca radar_YYYY-MM-DD.csv (o il vecchio nome).
      2. Se non esiste:
         a. Se lo scheduler è partito da meno di grace_min, OK.
         b. Altrimenti, allarme radar_missing.
      3. Se esiste ma è fermo da più di radar_stale_min:
         a. Se lo scanner radar è ancora attivo nel log, OK (nessun aereo).
         b. Altrimenti, allarme radar_stale.
    """
    cfg = _cfg()
    radar_stale = int(cfg.get("radar_stale_min", DEFAULT_RADAR_STALE_MIN))
    grace_min = int(cfg.get("radar_missing_grace_min", DEFAULT_RADAR_MISSING_GRACE_MIN))
    log_window = int(cfg.get("scheduler_log_window_sec", 300))

    try:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")

        # File atteso (h24: giorno solare)
        radar_file = os.path.join(RAW_DIR, f"radar_{today}.csv")
        old_file = os.path.join(RAW_DIR, f"bgy_night_flights_{today}.csv")

        if not os.path.exists(radar_file):
            if os.path.exists(old_file):
                radar_file = old_file
            else:
                # Grace period all'avvio
                scheduler_start = _get_scheduler_start_time(now)
                if scheduler_start is not None:
                    minutes_since_start = (now - scheduler_start).total_seconds() / 60
                    if minutes_since_start < grace_min:
                        return True, (f"Radar non ancora creato "
                                      f"({int(minutes_since_start)} min dall'avvio, "
                                      f"grace period {grace_min} min)")

                msg = f"File radar mancante per oggi ({today})"
                _send_alert("radar_missing",
                            sessione=today,
                            file_atteso=f"radar_{today}.csv")
                return False, msg

        mtime = datetime.fromtimestamp(os.path.getmtime(radar_file))
        elapsed_min = (now - mtime).total_seconds() / 60

        if elapsed_min <= radar_stale:
            return True, f"Radar aggiornato {int(elapsed_min)} min fa"

        # File stale. Verifica se lo scanner è ancora attivo.
        if _is_radar_recently_active(now, log_window):
            logger.info(
                f"ℹ️  Radar fermo da {int(elapsed_min)} min ma scanner attivo "
                f"(nessun aereo nell'area) — nessuna notifica inviata"
            )
            return True, (f"Radar fermo da {int(elapsed_min)} min "
                          f"ma scanner attivo (nessun aereo nell'area)")

        msg = (f"Radar fermo da {int(elapsed_min)} min e scanner non attivo")
        _send_alert("radar_stale",
                    minuti_fermo=int(elapsed_min),
                    ultimo_aggiornamento=mtime.strftime("%Y-%m-%d %H:%M"))
        return False, msg

    except Exception as e:
        return False, f"Errore check radar: {e}"


# =============================================================================
# CHECK 3 - OPENSKY
# =============================================================================

def check_opensky():
    cfg = _cfg()
    threshold = cfg.get("opensky_error_threshold", 5)
    log_lines = cfg.get("opensky_log_lines", 500)
    window_min = cfg.get("opensky_error_window_min", 15)
    data_cfg = config_manager.get_data_config()
    radar_interval = data_cfg.get("night_scan_interval_minutes", 2)

    try:
        log_file = os.path.join(
            LOGS_DIR, f"bgy_app_{datetime.now().strftime('%Y-%m-%d')}.log"
        )
        if not os.path.exists(log_file):
            return True, "Nessun log di oggi (nessun errore)"

        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-log_lines:]

        now = datetime.now()
        cutoff = now - timedelta(minutes=window_min)
        errors_429 = 0

        for line in lines:
            if "[Watchdog]" in line or "[Mailer]" in line:
                continue
            if "OpenSky" not in line and "[ScannerRadar]" not in line:
                continue
            if "429" not in line:
                continue
            if "Rilevati" in line and "errori 429" in line:
                continue
            try:
                ts_str = line.split(" - ")[0].strip()
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S,%f")
            except (ValueError, IndexError):
                continue
            if ts >= cutoff:
                errors_429 += 1

        if errors_429 >= threshold:
            msg = (f"Rilevati {errors_429} errori 429 negli ultimi "
                   f"{window_min} min")
            _send_alert("opensky_429",
                        finestra_min=window_min,
                        errori=errors_429,
                        soglia=threshold,
                        intervallo=radar_interval)
            return False, msg
        return True, (f"Errori 429 recenti ({window_min}min): {errors_429} "
                      f"(sotto soglia)")
    except Exception as e:
        return False, f"Errore check OpenSky: {e}"


# =============================================================================
# CHECK 4 - SCHEDULER
# =============================================================================

def check_scheduler():
    """
    Verifica che lo scheduler sia attivo.

    Con il radar h24, lo scheduler scrive nel log almeno ogni 2 minuti
    (ScannerRadar). Quindi il log non dovrebbe mai essere fermo per più
    di 15 minuti, indipendentemente dall'ora.
    """
    cfg = _cfg()
    log_stale = cfg.get("scheduler_log_stale_min", 15)
    try:
        running = _is_scheduler_process_running()

        if not running:
            logger.info(
                f"Scheduler non attivo al primo check, "
                f"verifica tra {SCHEDULER_DOUBLE_CHECK_DELAY_SEC}s..."
            )
            time.sleep(SCHEDULER_DOUBLE_CHECK_DELAY_SEC)
            running = _is_scheduler_process_running()
            if running:
                logger.info("Scheduler rilevato al secondo check, nessun riavvio.")
                return True, "Scheduler attivo (rilevato al secondo check)"

        if not running:
            logger.warning("Scheduler non attivo (doppio check), tentativo di riavvio...")
            restarted = _restart_scheduler()
            if restarted:
                msg = "Scheduler non attivo: riavviato"
                _send_alert("scheduler_restart",
                            ora_riavvio=datetime.now().strftime("%Y-%m-%d %H:%M"))
                return False, msg
            msg = "Scheduler non attivo e riavvio fallito"
            _send_alert("scheduler_dead",
                        ora=datetime.now().strftime("%Y-%m-%d %H:%M"))
            return False, msg

        # Scheduler attivo: verifica freschezza del log (h24)
        stale_min = _scheduler_log_age_min()
        if stale_min is not None and stale_min > log_stale:
            logger.warning(
                f"Scheduler attivo ma log fermo da {int(stale_min)} min, riavvio..."
            )
            restarted = _restart_scheduler(force=True)
            if restarted:
                msg = (f"Scheduler bloccato (log fermo da {int(stale_min)} min): riavviato")
                _send_alert("scheduler_blocked",
                            minuti_fermi=int(stale_min),
                            soglia=log_stale)
                return False, msg
            msg = (f"Scheduler bloccato (log fermo da {int(stale_min)} min) "
                   f"e riavvio fallito")
            _send_alert("scheduler_blocked_fail",
                        minuti_fermi=int(stale_min),
                        soglia=log_stale)
            return False, msg

        return True, "Scheduler attivo"
    except Exception as e:
        return False, f"Errore check scheduler: {e}"


def _is_scheduler_process_running():
    if sys.platform != "win32":
        return False
    try:
        ps_cmd = (
            "Get-WmiObject Win32_Process -Filter "
            "\"Name='python.exe' OR Name='pythonw.exe'\" | "
            "Where-Object { $_.CommandLine -like '*bgy_scheduler*' } | "
            "Select-Object -ExpandProperty ProcessId"
        )
        result = sp.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=15
        )
        return len((result.stdout or "").strip()) > 0
    except Exception as e:
        logger.error(f"Errore verifica processo scheduler: {e}")
        return False


def _scheduler_log_age_min():
    """
    Minuti dall'ultima riga di log che dimostri attività dello scheduler.
    Cerca [Scheduler] e [ScannerRadar] (radar h24 scrive ogni 2 min).
    """
    now = datetime.now()
    for days_back in (0, 1):
        check_date = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")
        log_file = os.path.join(LOGS_DIR, f"bgy_app_{check_date}.log")
        if not os.path.exists(log_file):
            continue
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()[-800:]
            latest_ts = None
            for line in lines:
                if "[Scheduler]" not in line and "[ScannerRadar]" not in line:
                    continue
                try:
                    ts_str = line.split(" - ")[0].strip()
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S,%f")
                    if latest_ts is None or ts > latest_ts:
                        latest_ts = ts
                except Exception:
                    continue
            if latest_ts is not None:
                return (now - latest_ts).total_seconds() / 60
        except Exception:
            continue
    return None


def _restart_scheduler(force=False):
    try:
        if force:
            _kill_all_scheduler_processes()
            time.sleep(2)
        if not os.path.exists(SCHEDULER_SCRIPT):
            logger.error(f"Scheduler non trovato: {SCHEDULER_SCRIPT}")
            return False
        creationflags = sp.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        sp.Popen(
            [sys.executable, SCHEDULER_SCRIPT],
            stdout=sp.DEVNULL, stderr=sp.DEVNULL,
            creationflags=creationflags, cwd=PROJECT_ROOT
        )
        logger.info("Scheduler riavviato")
        return True
    except Exception as e:
        logger.error(f"Errore riavvio scheduler: {e}")
        return False


def _kill_all_scheduler_processes():
    if sys.platform != "win32":
        return
    try:
        ps_cmd = (
            "Get-WmiObject Win32_Process -Filter "
            "\"Name='python.exe' OR Name='pythonw.exe'\" | "
            "Where-Object { $_.CommandLine -like '*bgy_scheduler*' } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
            "-ErrorAction SilentlyContinue }"
        )
        sp.run(["powershell", "-NoProfile", "-Command", ps_cmd],
               capture_output=True, timeout=15)
    except Exception as e:
        logger.error(f"Errore kill scheduler: {e}")


# =============================================================================
# CHECK 5 - DATABASE SERVICE
# =============================================================================

def check_database():
    """Verifica stato servizio PostgreSQL e raggiungibilità DB."""
    cfg = _db_cfg()
    if not cfg.get("enabled", True):
        return True, "Check DB disabilitato in config"

    threshold_min = int(cfg.get("down_alert_threshold_min", 15))
    auto_restart = bool(cfg.get("auto_restart_enabled", True))

    try:
        status, status_msg = bgy_db_service.get_service_status()
        db_ok, db_msg = bgy_db_service.is_db_reachable()

        now = datetime.now()
        state = _load_db_state()

        if status == "Running" and db_ok:
            if state.get("down_since"):
                logger.info(f"✅ DB tornato OK (era down da {state['down_since']})")
                state["down_since"] = None
                state["restart_attempts"] = 0
                _save_db_state(state)
            return True, f"DB OK ({status}, raggiungibile)"

        if not state.get("down_since"):
            state["down_since"] = now.isoformat()
            state["restart_attempts"] = 0
            _save_db_state(state)
            logger.warning(f"⚠️  DB down rilevato: {status_msg} | {db_msg}")

        try:
            down_since = datetime.fromisoformat(state["down_since"])
            down_min = (now - down_since).total_seconds() / 60
        except Exception:
            down_min = 0

        if down_min < threshold_min:
            return False, (f"DB down da {int(down_min)} min "
                           f"(soglia alert {threshold_min} min)")

        logger.error(f"❌ DB down da {int(down_min)} min — superata soglia {threshold_min} min")

        restart_msg = ""
        restart_ok = False

        if auto_restart:
            attempts = int(state.get("restart_attempts", 0))
            max_attempts = int(cfg.get("max_restart_attempts", 3))
            if attempts < max_attempts:
                logger.info(f"🔄 Tentativo riavvio {attempts + 1}/{max_attempts}...")
                restart_ok, restart_msg = bgy_service_restart()
                state["restart_attempts"] = attempts + 1
                _save_db_state(state)

                if restart_ok:
                    state["down_since"] = None
                    state["restart_attempts"] = 0
                    _save_db_state(state)
                    _send_alert("db_restarted",
                                down_min=int(down_min),
                                dettagli=restart_msg)
                    return True, f"DB riavviato con successo dopo {int(down_min)} min down"
            else:
                restart_msg = f"Numero massimo di tentativi ({max_attempts}) raggiunto"

        if auto_restart and not restart_ok:
            if "Privilegi amministrativi" in restart_msg or "admin" in restart_msg.lower():
                _send_alert("db_down_no_admin",
                            down_min=int(down_min),
                            status=status,
                            db_msg=db_msg[:100])
            else:
                _send_alert("db_down_restart_failed",
                            down_min=int(down_min),
                            status=status,
                            restart_msg=restart_msg[:100])
        else:
            _send_alert("db_down",
                        down_min=int(down_min),
                        status=status,
                        db_msg=db_msg[:100])

        return False, (f"DB down da {int(down_min)} min: "
                       f"status={status}, restart={'ok' if restart_ok else 'ko'}")

    except Exception as e:
        logger.error(f"Errore check_database: {e}")
        return False, f"Errore check DB: {str(e)[:100]}"


def bgy_service_restart():
    try:
        return bgy_db_service.restart_service()
    except Exception as e:
        return False, f"Eccezione restart: {str(e)[:80]}"


# =============================================================================
# RUN CHECK
# =============================================================================

def run_check(manual=False):
    cfg = _cfg()
    interval = cfg.get("check_interval_sec", 300)
    logger.info(f"Avvio check watchdog (manual={manual})")
    now = datetime.now()
    results = {}

    for name, fn in (("sacbo", check_sacbo),
                     ("radar", check_radar),
                     ("opensky", check_opensky),
                     ("scheduler", check_scheduler),
                     ("database", check_database)):
        try:
            ok, msg = fn()
            results[name] = {"ok": ok, "msg": msg}
            logger.info(f"{'✅' if ok else '❌'} {name.upper()}: {msg}")
        except Exception as e:
            results[name] = {"ok": False, "msg": f"Eccezione: {e}"}
            logger.error(f"❌ {name.upper()} eccezione: {e}")

    state = {
        "last_check": now.isoformat(),
        "next_check": (now + timedelta(seconds=interval)).isoformat(),
        "manual": bool(manual),
        "results": results,
    }
    _save_state(state)

    ok_count = sum(1 for r in results.values() if r["ok"])
    logger.info(f"Watchdog completato: {ok_count}/{len(results)} OK")
    return results


# =============================================================================
# LOOP
# =============================================================================

def watchdog_loop():
    cfg = _cfg()
    interval = cfg.get("check_interval_sec", 300)
    logger.info("=" * 50)
    logger.info("🐕 WATCHDOG BGY - AVVIO")
    logger.info(f"Intervallo: {interval}s")
    logger.info(f"Radar stale threshold: {cfg.get('radar_stale_min', DEFAULT_RADAR_STALE_MIN)} min (h24)")
    logger.info(f"Radar missing grace: {cfg.get('radar_missing_grace_min', DEFAULT_RADAR_MISSING_GRACE_MIN)} min")
    logger.info(f"Admin: {bgy_db_service.is_admin()}")
    logger.info("=" * 50)
    try:
        run_check(manual=False)
    except Exception as e:
        logger.error(f"Errore primo check: {e}")
    while True:
        try:
            time.sleep(interval)
            run_check(manual=False)
        except KeyboardInterrupt:
            logger.info("Watchdog interrotto manualmente")
            break
        except Exception as e:
            logger.error(f"Errore loop watchdog: {e}")
            time.sleep(30)


if __name__ == "__main__":
    try:
        watchdog_loop()
    except Exception as e:
        logger.critical(f"Watchdog terminato per errore fatale: {e}")
        sys.exit(1)