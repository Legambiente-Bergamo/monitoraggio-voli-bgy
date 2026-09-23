"""
bgy_core/bgy_mailer.py - Modulo unificato di invio email.
Versione 2.5.1
- Legge config via config_manager
- Rispetta i flag di silenziamento:
  * notifications.enabled             → master ON/OFF
  * notifications.alerts_enabled      → allarmi watchdog
  * notifications.daily_status_enabled → email stato 06:30
"""
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.utils import formataddr
from datetime import datetime

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import LOGS_DIR
from bgy_core.bgy_config_manager import config_manager
from bgy_core.bgy_version import version_string

logger = get_logger("Mailer")

COOLDOWN_FILE = os.path.join(LOGS_DIR, "notifier_cooldown.json")
DEFAULT_COOLDOWN_MIN = 30


# =============================================================================
# FLAG DI SILENZIAMENTO (v2.5.1)
# =============================================================================

def _notifications_config():
    """Ritorna la sezione notifications di config_data (dict, mai None)."""
    try:
        cfg = config_manager.get_data_config()
        return cfg.get("notifications", {}) or {}
    except Exception:
        return {}


def is_master_enabled():
    """Master switch globale."""
    return bool(_notifications_config().get("enabled", True))


def are_alerts_enabled():
    """Allarmi watchdog (radar mancante, opensky, scheduler, ecc.)."""
    if not is_master_enabled():
        return False
    return bool(_notifications_config().get("alerts_enabled", True))


def is_daily_status_enabled():
    """Email di stato giornaliero 06:30."""
    if not is_master_enabled():
        return False
    return bool(_notifications_config().get("daily_status_enabled", True))


def get_notifications_state():
    """Ritorna lo stato dei 3 flag (utile per la GUI)."""
    cfg = _notifications_config()
    return {
        "enabled": bool(cfg.get("enabled", True)),
        "alerts_enabled": bool(cfg.get("alerts_enabled", True)),
        "daily_status_enabled": bool(cfg.get("daily_status_enabled", True)),
        "cooldown_minutes": int(cfg.get("cooldown_minutes", DEFAULT_COOLDOWN_MIN)),
    }


# =============================================================================
# CONFIG E COOLDOWN
# =============================================================================

def _load_mail_config():
    """Legge config mail via config_manager. Ritorna dict o None se incompleta."""
    cfg = config_manager.get_mail_config()
    if not cfg:
        logger.error("Configurazione mail vuota")
        return None
    if not cfg.get("sender_email") or not cfg.get("sender_password"):
        return None
    return cfg


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
    """Legge il cooldown da config_data via config_manager (default 30 min)."""
    try:
        cfg = config_manager.get_data_config()
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


# =============================================================================
# INVIO SMTP (core)
# =============================================================================

def _send_smtp(cfg, subject, plain_text, html_body=None, attachment_paths=None,
               recipients=None):
    try:
        smtp_server = cfg.get("smtp_server", "smtp.gmail.com")
        smtp_port = cfg.get("smtp_port", 587)
        sender_email = cfg.get("sender_email", "").strip()
        sender_password = cfg.get("sender_password", "").strip()
        sender_name = cfg.get("sender_name", "Sistema di Monitoraggio Automatico BGY")

        if not sender_email or not sender_password:
            logger.error("❌ Configurazione email incompleta (sender_email/password)")
            return False

        if recipients is None:
            recipients = cfg.get("recipients", [])
        if not recipients:
            logger.error("❌ Nessun destinatario configurato")
            return False

        if html_body:
            msg = MIMEMultipart('alternative')
            msg.attach(MIMEText(plain_text, 'plain', 'utf-8'))
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))
            if attachment_paths:
                mixed = MIMEMultipart('mixed')
                mixed.attach(msg)
                for path in attachment_paths:
                    if path and os.path.exists(path):
                        with open(path, "rb") as f:
                            part = MIMEApplication(f.read(), Name=os.path.basename(path))
                            part['Content-Disposition'] = (
                                f'attachment; filename="{os.path.basename(path)}"'
                            )
                            mixed.attach(part)
                msg = mixed
        else:
            msg = MIMEText(plain_text, "plain", "utf-8")
            if attachment_paths:
                mixed = MIMEMultipart('mixed')
                mixed.attach(msg)
                for path in attachment_paths:
                    if path and os.path.exists(path):
                        with open(path, "rb") as f:
                            part = MIMEApplication(f.read(), Name=os.path.basename(path))
                            part['Content-Disposition'] = (
                                f'attachment; filename="{os.path.basename(path)}"'
                            )
                            mixed.attach(part)
                msg = mixed

        msg['From'] = formataddr((sender_name, sender_email))
        msg['To'] = ", ".join(recipients)
        msg['Subject'] = subject

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipients, msg.as_string())
        server.quit()

        logger.info(f"📧 Email inviata a {len(recipients)} destinatari.")
        return True
    except Exception as e:
        logger.error(f"❌ Errore invio email: {e}")
        return False


# =============================================================================
# ALERT (con cooldown + flag silenziamento)
# =============================================================================

def send_alert(key, subject, body, force=False):
    """
    Invia un'email di allarme.
    Rispetta notifications.enabled e notifications.alerts_enabled.
    Con force=True ignora il flag alerts_enabled ma non il master.
    """
    # Master switch: se disabilitato, blocca tutto tranne force
    if not force and not are_alerts_enabled():
        logger.info(f"🔕 Allarme '{key}' silenziato (notifications.alerts_enabled=False)")
        return True  # considerato "gestito", non è un errore

    if not force and not can_send(key):
        return True

    cfg = _load_mail_config()
    if not cfg:
        return False

    recipients = cfg.get("recipients_daily") or cfg.get("recipients", [])
    now = datetime.now()
    full_subject = f"{subject} - {now.strftime('%d/%m/%Y %H:%M')}"
    full_body = (f"{body}\n\n---\n"
                 f"Notifica automatica generata il "
                 f"{now.strftime('%d/%m/%Y alle %H:%M:%S')}\n"
                 f"{version_string()}")

    success = _send_smtp(cfg, full_subject, full_body, recipients=recipients)

    if success:
        data = _load_cooldown()
        data[key] = datetime.now().isoformat()
        _save_cooldown(data)
        logger.info(f"📧 Notifica '{key}' inviata: {full_subject}")

    return success


# =============================================================================
# EMAIL DI STATO (HTML + allegati)
# =============================================================================

def _build_html_status(subject_icon, is_success, body, attachment_paths, now):
    status_color = "#27ae60" if is_success else "#e74c3c"
    attachments_html = ""
    if attachment_paths:
        for f in attachment_paths:
            if f and os.path.exists(f):
                attachments_html += f'<div class="file">📎 {os.path.basename(f)}</div>\n'

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
body {{ font-family: Arial; line-height: 1.6; color: #333; max-width: 700px; margin: 0 auto; padding: 20px; }}
.header {{ background: linear-gradient(135deg, #1a2a6c, #b21f1f, #fdbb2d); color: white; padding: 25px; border-radius: 12px 12px 0 0; text-align: center; }}
.content {{ background: #f8f9fa; padding: 25px 30px; border-left: 1px solid #ddd; border-right: 1px solid #ddd; }}
.status-box {{ padding: 15px 20px; border-radius: 8px; text-align: center; font-size: 18px; font-weight: bold; background: {status_color}22; border: 2px solid {status_color}; color: {status_color}; margin-bottom: 20px; }}
.footer {{ background: #2c3e50; color: #ecf0f1; padding: 18px 25px; border-radius: 0 0 12px 12px; text-align: center; font-size: 12px; }}
.body-text {{ white-space: pre-wrap; font-family: monospace; font-size: 13px; background: white; border: 1px solid #ddd; border-radius: 8px; padding: 15px; }}
</style></head>
<body>
<div class="header"><h1>✈️ BGY Monitoring Suite</h1></div>
<div class="content">
<div class="status-box">{subject_icon} OPERAZIONE {'COMPLETATA' if is_success else 'FALLITA'}</div>
<div class="body-text">{body}</div>
<div class="info-box" style="margin-top:15px;">📌 Generata il {now.strftime('%d/%m/%Y %H:%M:%S')}</div>
{f'<div class="allegati"><strong>📎 Allegati:</strong><br>{attachments_html}</div>' if attachments_html else ''}
</div>
<div class="footer"><div>Circolo Legambiente Bergamo APS</div><div>{version_string()}</div></div>
</body></html>"""


def send_status_email(subject, body, is_success=True,
                      attachment_paths=None, recipient_type="generic",
                      force=False):
    """
    Invia email di stato (con HTML).
    Rispetta il flag daily_status_enabled solo se recipient_type='daily'.
    """
    if not force and recipient_type == "daily":
        if not is_daily_status_enabled():
            logger.info("🔕 Email di stato giornaliero silenziata "
                        "(notifications.daily_status_enabled=False)")
            return True
    elif not force and not is_master_enabled():
        logger.info("🔕 Email silenziata (notifications.enabled=False)")
        return True

    cfg = _load_mail_config()
    if not cfg:
        return False

    if recipient_type == "daily":
        recipients = cfg.get("recipients_daily") or cfg.get("recipients", [])
    elif recipient_type == "monthly":
        recipients = cfg.get("recipients_monthly") or cfg.get("recipients", [])
    elif recipient_type == "yearly":
        recipients = cfg.get("recipients_yearly") or cfg.get("recipients", [])
    else:
        recipients = cfg.get("recipients", [])

    if not recipients:
        logger.error(f"❌ Nessun destinatario per tipo '{recipient_type}'")
        return False

    now = datetime.now()
    status_icon = "✅" if is_success else "❌"
    plain_text = (f"{status_icon} OPERAZIONE {'COMPLETATA' if is_success else 'FALLITA'}\n\n"
                  f"{body}\n\nGenerato il {now.strftime('%d/%m/%Y %H:%M:%S')}")
    html_body = _build_html_status(status_icon, is_success, body,
                                   attachment_paths, now)

    return _send_smtp(cfg, subject, plain_text, html_body,
                      attachment_paths, recipients)


def _get_today_log_path():
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(LOGS_DIR, f"bgy_app_{date_str}.log")
    return path if os.path.exists(path) else None


def send_daily_status(success=True, details="", checks=None, force=False):
    """
    Email di stato giornaliero (06:30).
    Rispetta notifications.enabled e notifications.daily_status_enabled.
    """
    if not force and not is_daily_status_enabled():
        logger.info("🔕 Email di stato giornaliero silenziata")
        return True

    if checks:
        all_ok = all(ok for ok, _ in checks.values())
    else:
        all_ok = success

    status_icon = "✅" if all_ok else "❌"
    status_text = "OK" if all_ok else "KO"
    subject = (f"{status_icon} Monitoraggio BGY - "
               f"{datetime.now().strftime('%d/%m/%Y')} [{status_text}]")

    if checks:
        lines = ["Riepilogo processi di monitoraggio:", ""]
        labels = [
            ('sacbo_acquisition', '1) Acquisizione dati dal tabellone SACBO'),
            ('sacbo_processing', '2) Elaborazione dati dal tabellone SACBO'),
            ('night_acquisition', '3) Acquisizione dati notturni (23:00-05:59)'),
            ('night_enrichment', '4) Arricchimento dati notturni'),
            ('github_sync', '5) Sincronizzazione GitHub'),
        ]
        for key, label in labels:
            if key in checks:
                ok, msg = checks[key]
                icon = '✅' if ok else '❌'
                stato = 'OK' if ok else 'KO'
                lines.append(f"{icon} {label}: {stato}")
                if msg:
                    lines.append(f"      → {msg}")
                lines.append("")
        body = "\n".join(lines)
        if details:
            body += f"\n{details}"
    else:
        body = f"Report: {'OK' if success else 'KO'}\n\n{details}"

    attachments = []
    if not all_ok:
        only_sync_error = (
            checks and
            'github_sync' in checks and
            not checks['github_sync'][0] and
            all(ok for k, (ok, _) in checks.items() if k != 'github_sync')
        )
        if not only_sync_error:
            log_path = _get_today_log_path()
            if log_path:
                attachments.append(log_path)
                body += (f"\n\n📎 In allegato il file di log completo: "
                         f"{os.path.basename(log_path)}")

    return send_status_email(subject, body, all_ok,
                             attachment_paths=attachments,
                             recipient_type="daily",
                             force=force)


def send_email_with_attachments(attachment_paths, subject=None,
                                recipient_type="monthly",
                                is_success=True, body=None, force=False):
    if not subject:
        subject = f"📊 Report BGY - {datetime.now().strftime('%d/%m/%Y')}"
    if body is None:
        body = "In allegato i report richiesti."

    return send_status_email(
        subject, body, is_success,
        attachment_paths=attachment_paths,
        recipient_type=recipient_type,
        force=force,
    )


def send_test_email():
    """Invia un'email di test (ignora tutti i flag). Ritorna (bool, msg)."""
    now = datetime.now()
    subject = f"🧪 Email di test BGY - {now.strftime('%d/%m/%Y %H:%M')}"
    body = (
        "Questa è un'email di test inviata manualmente dalla GUI.\n\n"
        "Se la ricevi, la configurazione SMTP è corretta.\n\n"
        f"Stato flag notifiche:\n"
        f"  • enabled: {is_master_enabled()}\n"
        f"  • alerts_enabled: {are_alerts_enabled()}\n"
        f"  • daily_status_enabled: {is_daily_status_enabled()}"
    )
    ok = send_status_email(subject, body, is_success=True,
                            recipient_type="daily", force=True)
    if ok:
        return True, "Email di test inviata"
    return False, "Invio email di test fallito (controlla i log)"