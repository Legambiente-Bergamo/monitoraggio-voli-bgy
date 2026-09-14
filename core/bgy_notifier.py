"""
core/bgy_notifier.py - Invio notifiche immediate con cooldown configurabile.
"""
import os
import json
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

from core.bgy_logger import get_logger
from core.bgy_paths import CONFIG_MAIL, CONFIG_DATA, LOGS_DIR

logger = get_logger("Notifier")

COOLDOWN_FILE = os.path.join(LOGS_DIR, "notifier_cooldown.json")
DEFAULT_COOLDOWN_MIN = 30


def _load_cooldown():
    if os.path.exists(COOLDOWN_FILE):
        try:
            with open(COOLDOWN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_cooldown(data):
    try:
        os.makedirs(os.path.dirname(COOLDOWN_FILE), exist_ok=True)
        with open(COOLDOWN_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Errore salvataggio cooldown: {e}")


def get_cooldown_minutes():
    """Legge il cooldown da config_data.json (default 30 min)."""
    try:
        with open(CONFIG_DATA, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return int(cfg.get("notifications", {}).get("cooldown_minutes", DEFAULT_COOLDOWN_MIN))
    except Exception:
        return DEFAULT_COOLDOWN_MIN


def can_send(key):
    """Verifica se è passato abbastanza tempo dall'ultima notifica per questa key."""
    cooldown_min = get_cooldown_minutes()
    data = _load_cooldown()
    if key in data:
        try:
            last = datetime.fromisoformat(data[key])
            elapsed_min = (datetime.now() - last).total_seconds() / 60
            if elapsed_min < cooldown_min:
                logger.info(f"⏸️ Notifica '{key}' in cooldown "
                            f"({int(elapsed_min)}/{cooldown_min} min)")
                return False
        except Exception:
            pass
    return True


def send_alert(key, subject, body, force=False):
    """
    Invia una notifica email se non è in cooldown.

    Args:
        key: identificativo univoco dell'errore (es. "sacbo_scan_missing")
        subject: oggetto dell'email
        body: corpo del messaggio
        force: se True, ignora il cooldown

    Returns:
        True se inviata (o saltata per cooldown), False se errore
    """
    if not force and not can_send(key):
        return True

    if not os.path.exists(CONFIG_MAIL):
        logger.error(f"Config mail non trovato: {CONFIG_MAIL}")
        return False

    try:
        with open(CONFIG_MAIL, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        sender = cfg.get("sender_email", "").strip()
        password = cfg.get("sender_password", "").strip()
        recipients = cfg.get("recipients_daily") or cfg.get("recipients", [])
        smtp_server = cfg.get("smtp_server", "smtp.gmail.com")
        smtp_port = cfg.get("smtp_port", 587)
        sender_name = cfg.get("sender_name", "BGY Monitoring Suite")

        if not sender or not password or not recipients:
            logger.error("❌ Config email incompleta, notifica non inviata")
            return False

        now = datetime.now()
        full_subject = f"{subject} - {now.strftime('%d/%m/%Y %H:%M')}"
        full_body = f"{body}\n\n---\nNotifica automatica generata il {now.strftime('%d/%m/%Y alle %H:%M:%S')}\nBGY Monitoring Suite"

        msg = MIMEText(full_body, "plain", "utf-8")
        msg["Subject"] = full_subject
        msg["From"] = f"{sender_name} <{sender}>"
        msg["To"] = ", ".join(recipients)

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, recipients, msg.as_string())
        server.quit()

        # Aggiorna cooldown solo se inviata con successo
        data = _load_cooldown()
        data[key] = datetime.now().isoformat()
        _save_cooldown(data)

        logger.info(f"📧 Notifica '{key}' inviata: {full_subject}")
        return True

    except Exception as e:
        logger.error(f"❌ Errore invio notifica '{key}': {e}")
        return False


def reset_cooldown():
    """Cancella tutti i cooldown (usato dal tab GUI)."""
    try:
        if os.path.exists(COOLDOWN_FILE):
            os.remove(COOLDOWN_FILE)
            logger.info("🗑️ Cooldown resettato")
        return True
    except Exception as e:
        logger.error(f"Errore reset cooldown: {e}")
        return False


def get_active_cooldowns():
    """Restituisce i cooldown attivi (per il tab GUI)."""
    return _load_cooldown()