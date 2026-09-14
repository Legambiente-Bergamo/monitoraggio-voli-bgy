"""
bgy_watchdog.py - Watchdog per la BGY Monitoring Suite.

v2.3.5 - Fix: cerca sia python.exe che pythonw.exe
       - Fix: salta check SACBO se lo scheduler è stato avviato dopo l'orario previsto
       - Feature: riavvia automaticamente lo scheduler se morto
"""
import os
import sys
import json
import time
import glob
import subprocess as sp
from datetime import datetime, timedelta

# Assicura che la root del progetto sia nel path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.bgy_paths import RAW_DIR, LOGS_DIR, CONFIG_DATA
from core.bgy_logger import get_logger
from core.bgy_notifier import send_alert

logger = get_logger("Watchdog")

STATE_FILE = os.path.join(LOGS_DIR, "watchdog_state.json")
CHECK_INTERVAL = 300  # 5 minuti


# -----------------------------------------------------------------------------
# UTILITY
# -----------------------------------------------------------------------------

def _load_config():
    try:
        with open(CONFIG_DATA, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Errore lettura config: {e}")
        return {}


def _save_state(state):
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        state["last_update"] = datetime.now().isoformat()
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Errore salvataggio state: {e}")


def _load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _get_scheduler_start_time():
    """
    Legge dal log di oggi il timestamp dell'avvio dello scheduler.
    Ritorna un datetime o None.
    """
    log_file = os.path.join(LOGS_DIR, f"bgy_app_{datetime.now().strftime('%Y-%m-%d')}.log")
    if not os.path.exists(log_file):
        return None
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "SCHEDULER BGY - CONFIGURAZIONE" in line:
                    ts = line.split(" - ")[0].strip()
                    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S,%f")
    except Exception as e:
        logger.error(f"Errore lettura scheduler start time: {e}")
    return None


# -----------------------------------------------------------------------------
# CHECK SINGOLI
# -----------------------------------------------------------------------------

def check_sacbo_recent():
    """
    Verifica che l'ultima scansione SACBO prevista sia presente.
    Ignora il check se lo scheduler è stato avviato dopo l'orario previsto.
    """
    cfg = _load_config()
    scan_schedules = cfg.get("scan_schedules", ["00:00", "06:00", "12:00", "18:00"])

    now = datetime.now()
    today = now.strftime("%Y%m%d")
    scan_files = glob.glob(os.path.join(RAW_DIR, f"scan_{today}_*.csv"))

    # Trova l'orario previsto più recente già passato
    last_expected = None
    for t in sorted(scan_schedules):
        try:
            hh, mm = map(int, t.split(":"))
            dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if dt <= now:
                last_expected = dt
        except Exception:
            continue

    if not last_expected:
        return True, "Nessuna scansione ancora dovuta oggi"

    # Tolleranza 60 minuti
    if (now - last_expected) < timedelta(minutes=60):
        return True, f"Scansione delle {last_expected.strftime('%H:%M')} troppo recente"

    # Se lo scheduler è stato avviato DOPO l'orario previsto, salta il check
    start_time = _get_scheduler_start_time()
    if start_time and start_time > last_expected:
        return True, (f"Scansione delle {last_expected.strftime('%H:%M')} "
                      f"precedente all'avvio dello scheduler "
                      f"({start_time.strftime('%H:%M')})")

    # Cerca file scan vicino all'orario previsto (±60 min)
    expected_min = last_expected.hour * 60 + last_expected.minute
    found = False
    for f in scan_files:
        try:
            parts = os.path.basename(f).replace(".csv", "").split("_")
            actual = int(parts[2])
            actual_min = (actual // 100) * 60 + (actual % 100)
            if abs(actual_min - expected_min) <= 60:
                found = True
                break
        except Exception:
            continue

    if found:
        return True, f"Scansione delle {last_expected.strftime('%H:%M')} presente"

    msg = f"Scansione SACBO delle {last_expected.strftime('%H:%M')} mancante"
    send_alert(
        "sacbo_scan_missing",
        "⚠️ BGY - Scansione SACBO mancante",
        f"{msg}.\n\n"
        "Possibili cause:\n"
        "- Lo scheduler non è in esecuzione\n"
        "- Il tabellone SACBO non è raggiungibile\n"
        "- Playwright ha avuto un errore\n\n"
        "Controlla bgy_data/logs/bgy_app_*.log per dettagli."
    )
    return False, msg


def check_radar_active():
    """Verifica che il file radar si aggiorni durante la finestra notturna."""
    now = datetime.now()
    if not (now.hour >= 23 or now.hour < 6):
        return True, "Fuori dalla finestra notturna"

    if now.hour >= 23:
        session = now.strftime("%Y-%m-%d")
    else:
        session = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    radar_file = os.path.join(RAW_DIR, f"bgy_night_flights_{session}.csv")
    if not os.path.exists(radar_file):
        send_alert(
            "radar_missing",
            "⚠️ BGY - File radar notturno mancante",
            f"Nessun file radar per la sessione {session}.\n"
            "Verifica che lo scanner notturno stia girando."
        )
        return False, f"File radar {session} mancante"

    mtime = datetime.fromtimestamp(os.path.getmtime(radar_file))
    elapsed_min = (now - mtime).total_seconds() / 60
    if elapsed_min > 15:
        send_alert(
            "radar_stale",
            "⚠️ BGY - Radar notturno fermo",
            f"Il file radar non si aggiorna da {int(elapsed_min)} minuti.\n"
            "Verifica OpenSky o il loop dello scheduler."
        )
        return False, f"File radar fermo da {int(elapsed_min)} min"

    return True, f"File radar aggiornato {int(elapsed_min)} min fa"


def check_opensky_errors():
    """Verifica presenza di errori 429 OpenSky recenti nel log."""
    now = datetime.now()
    log_file = os.path.join(LOGS_DIR, f"bgy_app_{now.strftime('%Y-%m-%d')}.log")
    if not os.path.exists(log_file):
        return True, "Log del giorno non presente"

    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-500:]
        recent_429 = [l for l in lines if "Errore OpenSky: 429" in l]
        if len(recent_429) >= 5:
            send_alert(
                "opensky_429",
                "⚠️ BGY - OpenSky rate limit",
                f"Rilevati {len(recent_429)} errori 429 OpenSky negli ultimi 500 log.\n\n"
                "Suggerimento: aggiungere adsb.lol come fallback."
            )
            return False, f"{len(recent_429)} errori 429"
    except Exception:
        pass
    return True, "Nessun errore OpenSky recente"


def check_scheduler_alive():
    """
    Verifica che lo scheduler sia in esecuzione.
    FIX: cerca sia python.exe che pythonw.exe.
    Se morto, prova a riavviarlo automaticamente.
    """
    if sys.platform != "win32":
        return True, "Check non supportato su questo OS"

    try:
        result = sp.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-WmiObject Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | "
             "Where-Object { $_.CommandLine -like '*bgy_scheduler*' } | "
             "Measure-Object | Select-Object -ExpandProperty Count"],
            capture_output=True, text=True, timeout=10
        )
        count = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0

        if count == 1:
            return True, "Scheduler attivo"
        if count > 1:
            return False, f"⚠️ {count} scheduler in parallelo (dovrebbe essere 1)"

        # count == 0: scheduler morto, prova a riavviarlo
        logger.warning("⚠️ Scheduler non trovato, tentativo di riavvio...")
        try:
            scheduler_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "bgy_scheduler.py"
            )
            sp.Popen(
                [sys.executable, scheduler_path],
                stdout=sp.DEVNULL,
                stderr=sp.DEVNULL,
                creationflags=sp.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            logger.info("🔄 Scheduler riavviato automaticamente")
            # Non invia alert: il sistema ha reagito da solo
            return True, "Scheduler riavviato automaticamente"
        except Exception as e:
            send_alert(
                "scheduler_down",
                "⚠️ BGY - Scheduler non attivo",
                f"Lo scheduler non era in esecuzione e il riavvio automatico è fallito:\n{e}"
            )
            return False, f"Scheduler morto, riavvio fallito: {e}"

    except Exception as e:
        return True, f"Check scheduler saltato: {e}"


# -----------------------------------------------------------------------------
# ESECUZIONE
# -----------------------------------------------------------------------------

def run_check(manual=False):
    """Esegue tutti i check e salva lo stato."""
    logger.info(f"{'👤' if manual else '🔄'} Check{' manuale' if manual else ' automatico'}...")
    results = {}

    checks = [
        ("sacbo", check_sacbo_recent),
        ("radar", check_radar_active),
        ("opensky", check_opensky_errors),
        ("scheduler", check_scheduler_alive),
    ]

    for name, fn in checks:
        try:
            ok, msg = fn()
            results[name] = {"ok": ok, "msg": msg}
            logger.info(f"  {'✅' if ok else '❌'} {name}: {msg}")
        except Exception as e:
            results[name] = {"ok": False, "msg": f"Errore: {e}"}
            logger.error(f"  ❌ {name}: {e}")

    state = {
        "last_check": datetime.now().isoformat(),
        "results": results,
        "manual": manual,
    }
    _save_state(state)
    return results


def main():
    """Loop infinito del watchdog."""
    logger.info("🐕 Watchdog BGY avviato")
    logger.info(f"⏱️ Intervallo check: {CHECK_INTERVAL} secondi")

    next_check = datetime.now()

    while True:
        try:
            now = datetime.now()
            if now >= next_check:
                run_check(manual=False)
                next_check = datetime.now() + timedelta(seconds=CHECK_INTERVAL)

            state = _load_state()
            state["next_check"] = next_check.isoformat()
            state["interval_seconds"] = CHECK_INTERVAL
            _save_state(state)

            time.sleep(5)
        except KeyboardInterrupt:
            logger.info("🐕 Watchdog fermato manualmente")
            break
        except Exception as e:
            logger.error(f"Errore watchdog loop: {e}")
            time.sleep(30)


if __name__ == "__main__":
    main()