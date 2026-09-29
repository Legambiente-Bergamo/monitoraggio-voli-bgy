"""
bgy_core/bgy_db_service.py - Gestione servizio PostgreSQL Windows.
Versione 1.0.0

Scopo:
  - Rilevare stato del servizio PostgreSQL.
  - Verificare la raggiungibilità del DB.
  - Tentare il riavvio automatico del servizio.

Nota sui privilegi:
  - Il riavvio del servizio richiede privilegi amministrativi.
  - Se la suite gira con privilegi limitati, il riavvio fallisce.
  - Usare 'Avvia BGY.bat' v2.0.0+ per avviare la suite elevata.

API:
  - get_service_status() -> (status, msg)
    status ∈ {'Running', 'Stopped', 'Unknown'}
  - is_db_reachable() -> (ok, msg)
  - restart_service() -> (ok, msg)
  - is_admin() -> bool

Uso:
    from bgy_core.bgy_db_service import (get_service_status,
                                          is_db_reachable,
                                          restart_service,
                                          is_admin)
"""
import os
import sys
import time
import subprocess as sp

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_config_manager import config_manager

logger = get_logger("DBService")

DEFAULT_SERVICE_NAME = "postgresql-x64-17"


def _cfg():
    try:
        cfg = config_manager.get_data_config()
        return cfg.get("database_service", {}) or {}
    except Exception:
        return {}


def _service_name():
    return _cfg().get("service_name", DEFAULT_SERVICE_NAME)


def _is_windows():
    return sys.platform == "win32"


def is_admin():
    """Verifica se il processo corrente ha privilegi amministrativi."""
    if not _is_windows():
        return False
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


# -----------------------------------------------------------------------------
# STATO SERVIZIO
# -----------------------------------------------------------------------------

def get_service_status():
    """
    Ritorna (status, msg):
      - status: 'Running' | 'Stopped' | 'Unknown'
      - msg: descrizione human-readable
    """
    if not _is_windows():
        return 'Unknown', f"Sistema non Windows: {sys.platform}"

    service = _service_name()
    try:
        result = sp.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-Service -Name '{service}' -ErrorAction Stop).Status"],
            capture_output=True, text=True, timeout=10
        )
        output = (result.stdout or "").strip()
        if output:
            status = output.splitlines()[0].strip()
            if status in ("Running", "Stopped"):
                return status, f"Servizio {service}: {status}"
            return 'Unknown', f"Stato non riconosciuto: {output[:50]}"
        if result.returncode != 0:
            err = (result.stderr or "")[:100]
            return 'Unknown', f"Servizio {service} non trovato: {err}"
        return 'Unknown', f"Risposta vuota per servizio {service}"
    except sp.TimeoutExpired:
        return 'Unknown', f"Timeout verifica servizio {service}"
    except Exception as e:
        return 'Unknown', f"Errore verifica servizio: {str(e)[:80]}"


# -----------------------------------------------------------------------------
# CONNESSIONE DB
# -----------------------------------------------------------------------------

def is_db_reachable():
    """
    Verifica se il DB è raggiungibile tramite la normale connessione.
    Ritorna (ok, msg).
    """
    try:
        from bgy_core import bgy_db
        if not bgy_db.is_enabled():
            return False, "DB non abilitato in config_database.json"
        ok, msg = bgy_db.test_connection()
        return ok, msg
    except Exception as e:
        return False, f"Errore verifica DB: {str(e)[:80]}"


# -----------------------------------------------------------------------------
# RIAVVIO SERVIZIO
# -----------------------------------------------------------------------------

def restart_service():
    """
    Tenta di riavviare il servizio PostgreSQL.
    Ritorna (ok, msg).

    Richiede privilegi amministrativi. Se non elevato, ritorna (False, ...).
    """
    if not _is_windows():
        return False, "Riavvio non supportato su questo sistema"

    if not is_admin():
        return False, ("Privilegi amministrativi insufficienti. "
                       "Avvia la suite con 'Avvia BGY.bat' (UAC)")

    service = _service_name()
    logger.info(f"🔄 Tentativo riavvio servizio {service}...")

    # Stop
    try:
        stop = sp.run(
            ["net", "stop", service],
            capture_output=True, text=True, timeout=30
        )
        stop_out = ((stop.stdout or "") + (stop.stderr or ""))[:200]
        if stop.returncode != 0:
            logger.warning(f"⚠️  'net stop' fallito (rc={stop.returncode}): {stop_out}")
        else:
            logger.info(f"✅ Servizio {service} fermato")
    except sp.TimeoutExpired:
        logger.warning("⚠️  Timeout 'net stop' (30s)")
    except Exception as e:
        logger.warning(f"⚠️  Eccezione 'net stop': {e}")

    time.sleep(2)

    # Start
    try:
        start = sp.run(
            ["net", "start", service],
            capture_output=True, text=True, timeout=30
        )
        start_out = ((start.stdout or "") + (start.stderr or ""))[:200]
        if start.returncode != 0:
            msg = f"'net start' fallito (rc={start.returncode}): {start_out}"
            logger.error(f"❌ {msg}")
            return False, msg
        logger.info(f"✅ Servizio {service} avviato")
    except sp.TimeoutExpired:
        return False, "Timeout 'net start' (30s)"
    except Exception as e:
        return False, f"Eccezione 'net start': {str(e)[:100]}"

    time.sleep(3)

    # Verifica che il DB risponda
    ok, msg = is_db_reachable()
    if ok:
        return True, f"Servizio {service} riavviato e DB raggiungibile"
    return True, f"Servizio {service} riavviato, ma DB non ancora raggiungibile"


# -----------------------------------------------------------------------------
# ENTRY POINT (test CLI)
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("BGY DB Service — test CLI")
    print("=" * 60)

    is_adm = is_admin()
    print(f"Windows:  {_is_windows()}")
    print(f"Admin:    {is_adm}")
    print(f"Servizio: {_service_name()}")
    print()

    status, msg = get_service_status()
    print(f"Stato servizio: {status}")
    print(f"  → {msg}")
    print()

    ok, msg = is_db_reachable()
    print(f"DB raggiungibile: {ok}")
    print(f"  → {msg}")