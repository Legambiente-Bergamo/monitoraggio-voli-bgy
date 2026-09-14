"""
bgy_utils_mailer.py - Modulo spedizione report via Email SMTP TLS.
v2.3.8 - Aggiunto 5° check per sync GitHub
"""
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.utils import formataddr
from datetime import datetime

from core.bgy_logger import get_logger
from core.bgy_paths import CONFIG_MAIL, LOGS_DIR

logger = get_logger("Mailer")


def _get_today_log_path():
    """Restituisce il percorso del log di oggi (se esiste)."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(LOGS_DIR, f"bgy_app_{date_str}.log")
    return path if os.path.exists(path) else None


def send_status_email(subject, body, is_success=True, attachment_paths=None, recipient_type="generic"):
    """Invia una email di stato."""
    if not os.path.exists(CONFIG_MAIL):
        logger.error(f"File di configurazione mail non trovato: {CONFIG_MAIL}")
        return False

    try:
        with open(CONFIG_MAIL, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        smtp_server = cfg.get("smtp_server", "smtp.gmail.com")
        smtp_port = cfg.get("smtp_port", 587)
        sender_email = cfg.get("sender_email", "").strip()
        sender_password = cfg.get("sender_password", "").strip()
        sender_name = cfg.get("sender_name", "Sistema di Monitoraggio Automatico BGY")

        if recipient_type == "daily":
            recipients = cfg.get("recipients_daily") or cfg.get("recipients", [])
        elif recipient_type == "monthly":
            recipients = cfg.get("recipients_monthly") or cfg.get("recipients", [])
        elif recipient_type == "yearly":
            recipients = cfg.get("recipients_yearly") or cfg.get("recipients", [])
        else:
            recipients = cfg.get("recipients", [])

        logger.info(f"📋 Configurazione letta:")
        logger.info(f"   sender_email: '{sender_email}' (vuoto? {not sender_email})")
        logger.info(f"   recipient_type: '{recipient_type}'")
        logger.info(f"   recipients: {recipients}")

        if not sender_email or not sender_password or not recipients:
            logger.error("❌ Configurazione email incompleta")
            return False

        msg = MIMEMultipart('alternative')
        msg['From'] = formataddr((sender_name, sender_email))
        msg['To'] = ", ".join(recipients)
        msg['Subject'] = subject

        status_color = "#27ae60" if is_success else "#e74c3c"
        status_icon = "✅" if is_success else "❌"

        attachments_html = ""
        if attachment_paths:
            for f in attachment_paths:
                if f and os.path.exists(f):
                    attachments_html += f'<div class="file">📎 {os.path.basename(f)}</div>\n'

        now = datetime.now()

        html_body = f"""<!DOCTYPE html>
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
<div class="status-box">{status_icon} OPERAZIONE {'COMPLETATA' if is_success else 'FALLITA'}</div>
<div class="body-text">{body}</div>
<div class="info-box" style="margin-top:15px;">📌 Generata il {now.strftime('%d/%m/%Y %H:%M:%S')}</div>
{f'<div class="allegati"><strong>📎 Allegati:</strong><br>{attachments_html}</div>' if attachments_html else ''}
</div>
<div class="footer"><div>Circolo Legambiente Bergamo APS</div></div>
</body></html>"""

        plain_text = f"{status_icon} OPERAZIONE {'COMPLETATA' if is_success else 'FALLITA'}\n\n{body}\n\nGenerato il {now.strftime('%d/%m/%Y %H:%M:%S')}"

        msg.attach(MIMEText(plain_text, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        if attachment_paths:
            for path in attachment_paths:
                if path and os.path.exists(path):
                    with open(path, "rb") as f:
                        part = MIMEApplication(f.read(), Name=os.path.basename(path))
                        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
                        msg.attach(part)

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


def send_daily_status(success=True, details="", checks=None):
    """
    Invia email di stato per il report giornaliero.
    Se c'è un errore, allega automaticamente il file di log di oggi.
    Supporta 4 o 5 check (il 5° è il sync GitHub).
    """
    if checks:
        all_ok = all(ok for ok, _ in checks.values())
    else:
        all_ok = success

    status_icon = "✅" if all_ok else "❌"
    status_text = "OK" if all_ok else "KO"
    subject = f"{status_icon} Monitoraggio BGY - {datetime.now().strftime('%d/%m/%Y')} [{status_text}]"

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

    # Allega il log solo se c'è un errore (ma NON se l'unico errore è il sync GitHub,
    # perché il log potrebbe non contenere info utili sul problema di rete)
    attachments = []
    if not all_ok:
        # Controlla se gli errori sono solo sul sync GitHub
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
                body += f"\n\n📎 In allegato il file di log completo: {os.path.basename(log_path)}"

    return send_status_email(subject, body, all_ok, attachment_paths=attachments, recipient_type="daily")


def send_email_with_attachments(attachment_paths, subject=None, recipient_type="monthly", is_success=True, body=None):
    """Invia email con allegati (usata da report mensili/annuali)."""
    if not subject:
        subject = f"📊 Report BGY - {datetime.now().strftime('%d/%m/%Y')}"
    if body is None:
        body = "In allegato i report richiesti."

    return send_status_email(
        subject, body, is_success,
        attachment_paths=attachment_paths,
        recipient_type=recipient_type
    )


if __name__ == "__main__":
    print("📧 Test mailer...")
    test_checks = {
        'sacbo_acquisition': (True, "Tutte le scansioni eseguite"),
        'sacbo_processing': (True, "Report giornaliero: 76 voli"),
        'night_acquisition': (True, "Trovati 20 rilevamenti radar"),
        'night_enrichment': (True, "Report notturno: 25 voli"),
        'github_sync': (True, "Sync OK (5 files changed)"),
    }
    send_daily_status(True, "", checks=test_checks)