"""
bgy_watchdog.py - Watchdog per il controllo anomalie BGY Monitoring Suite.
Versione 2.5.3
- Doppio check prima di riavviare lo scheduler (evita falsi positivi)
- Messaggi di alert letti da bgy_config/config_alert_messages.json

Fix v2.5.3:
- check_opensky(): prima contava QUALSIASI riga contenente "429" nel log,
  incluse le righe di allarme generate dal watchdog stesso (❌ OPENSKY:
  Rilevati N errori 429...). Questo causava un ciclo di auto-alimentazione:
  ogni check trovava le righe dei check precedenti e le contava come nuovi
  errori, generando notifiche continue anche fuori dalla fascia notturna.
  Ora il check ignora le righe di [Watchdog] e [Mailer], e considera solo
  gli errori 429 generati dallo scanner OpenSky ([ScannerNight] o OpenSky).
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

logger = get_logger("Watchdog")

STATE_FILE = os.path.join(LOGS_DIR, "watchdog_state.json")
SCHEDULER_SCRIPT = os.path.join(PROJECT_ROOT, "bgy_scheduler.py")

# Ritardo tra primo e secondo check scheduler
SCHEDULER_DOUBLE_CHECK_DELAY_SEC = 3


def _cfg():
    return config_manager.get_watchdog_config()


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


# =============================================================================
# CHECK 1 - SACBO
# =============================================================================

def check_sacbo():
    cfg = _cfg()
    max_age = cfg.get("sacbo_max_age_hours", 7)
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
        if age_hours > max_age:
            msg = (f"Ultima scansione SACBO: {os.path.basename(latest)} "
                   f"({age_hours:.1f}h fa)")
            _send_alert("sacbo_stale",
                        ultimo_file=os.path.basename(latest),
                        eta_ore=f"{age_hours:.1f}",
                        soglia_ore=max_age)
            return False, msg
        msg = (f"Ultima scansione: {os.path.basename(latest)} "
               f"({age_hours:.1f}h fa)")
        return True, msg
    except Exception as e:
        return False, f"Errore check SACBO: {e}"


# =============================================================================
# CHECK 2 - RADAR
# =============================================================================

def check_radar():
    cfg = _cfg()
    radar_stale = cfg.get("radar_stale_min", 30)
    log_window = cfg.get("scheduler_log_window_sec", 300)
    try:
        now = datetime.now()
        if not is_night_time(now):
            return True, "Fuori dalla finestra notturna"
        session = night_session_date(now)
        new_name = radar_filename(session)
        old_name = f"bgy_night_flights_{session}.csv"
        radar_file = None
        for name in (new_name, old_name):
            if name:
                p = os.path.join(RAW_DIR, name)
                if os.path.exists(p):
                    radar_file = p
                    break
        if not radar_file:
            msg = f"File radar mancante per la sessione {session}"
            _send_alert("radar_missing",
                        sessione=session,
                        file_atteso=new_name or old_name)
            return False, msg
        mtime = datetime.fromtimestamp(os.path.getmtime(radar_file))
        elapsed_min = (now - mtime).total_seconds() / 60
        if elapsed_min <= radar_stale:
            return True, f"Radar aggiornato {int(elapsed_min)} min fa"
        if _scanner_night_is_active(now, log_window):
            _send_alert("radar_stale_scanner_ok")
            return True, (f"Radar fermo da {int(elapsed_min)} min "
                          f"ma scanner attivo (nessun aereo nell'area)")
        msg = (f"Radar fermo da {int(elapsed_min)} min e scanner non attivo")
        _send_alert("radar_stale",
                    minuti_fermo=int(elapsed_min),
                    ultimo_aggiornamento=mtime.strftime("%Y-%m-%d %H:%M"))
        return False, msg
    except Exception as e:
        return False, f"Errore check radar: {e}"


def _scanner_night_is_active(now, window_sec=300, min_hits=2):
    log_file = os.path.join(LOGS_DIR, f"bgy_app_{now.strftime('%Y-%m-%d')}.log")
    if not os.path.exists(log_file):
        return False
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-200:]
        recent = 0
        for line in lines:
            if "ScannerNight" in line and "Avvio scansione" in line:
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
# CHECK 3 - OPENSKY
# =============================================================================

def check_opensky():
    """
    Conta gli errori 429 recenti nel log, MA:
    - Ignora le righe generate dal Watchdog stesso ([Watchdog])
    - Ignora le righe generate dal Mailer ([Mailer])
    - Considera solo gli errori 429 reali dello scanner OpenSky
      ([ScannerNight] o righe che menzionano OpenSky)

    Fix v2.5.3: senza questo filtro, il watchdog contava le proprie righe
    di allarme ("❌ OPENSKY: Rilevati N errori 429...") come se fossero
    nuovi errori, causando un ciclo infinito di notifiche.
    """
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
            # ✅ Ignora le righe generate dal Watchdog o dal Mailer
            #    (altrimenti il check si auto-alimenta contando i propri allarmi)
            if "[Watchdog]" in line or "[Mailer]" in line:
                continue
            # ✅ Considera solo le righe che menzionano OpenSky o ScannerNight
            if "OpenSky" not in line and "[ScannerNight]" not in line:
                continue
            # ✅ Cerca la presenza di "429"
            if "429" not in line:
                continue
            # ✅ Ignora eventuali righe di riepilogo (difensivo)
            if "Rilevati" in line and "errori 429" in line:
                continue
            # ✅ Verifica timestamp
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
# CHECK 4 - SCHEDULER (con doppio check)
# =============================================================================

def check_scheduler():
    cfg = _cfg()
    log_stale = cfg.get("scheduler_log_stale_min", 15)
    try:
        # Primo check
        running = _is_scheduler_process_running()

        # Doppio check: se il primo dice "non attivo", verifica di nuovo
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

        if is_night_time():
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
    now = datetime.now()
    for days_back in (0, 1):
        check_date = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")
        log_file = os.path.join(LOGS_DIR, f"bgy_app_{check_date}.log")
        if not os.path.exists(log_file):
            continue
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()[-500:]
            latest_ts = None
            for line in lines:
                if "[Scheduler]" not in line and "Scheduler" not in line:
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
                     ("scheduler", check_scheduler)):
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