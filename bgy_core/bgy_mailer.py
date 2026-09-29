"""
bgy_core/bgy_mailer.py - Modulo unificato di invio email.
Versione 2.5.13

Novità v2.5.13 (distribuzione ritardi):
- _format_delay_section() mostra la distribuzione dei voli in ritardo
  per fasce: <5, 5-10, 10-15, 15-30, 30-60, >60 minuti.

Novità v2.5.12 (check 11 servizio DB):
- Aggiunto check 11 "Servizio Database" alla lista labels.
- Il messaggio multi-riga viene indentato come gli altri check.

Novità v2.5.11 (statistiche puntualità):
- _format_stats_section() mostra, dopo i movimenti del giorno:
    * Puntualità: voli in ritardo, ritardo medio, ritardo massimo
    * Cancellati: elenco con callsign, compagnia, destinazione
- I dati arrivano da stats["delay"] (dict opzionale).

Novità v2.5.10 (Avionio check 10):
- Aggiunto check 10 "Conferma incrociata Avionio".
- Il check 10 è "warning-only": se fallisce, l'email resta ✅ nell'oggetto
  ma mostra il warning nel corpo.
- Definite WARNING_ONLY_CHECKS per escludere questi check da all_ok.

Novità v2.5.9 (sconfinamenti gravi + anomalie):
- _format_stats_section() mostra tre sezioni dedicate.

Novità v2.5.8 (sconfinamenti):
- _format_stats_section() mostra sezione 🚨 SCONFINAMENTI.

Novità v2.5.7 (F14c):
- send_daily_status() accetta parametro `screenshot_paths`.

Novità v2.5.6 (F14b):
- send_daily_status() mostra anche il check 9.

Novità v2.5.5 (F14):
- send_daily_status() mostra anche il check 8.

Novità v2.5.4:
- send_daily_status() accetta parametro `stats`.
- Gradiente header bianco → azzurro → blu scuro (F18c).

Novità v2.5.2:
- Flag di silenziamento (notifications.enabled/alerts_enabled/daily_status_enabled)
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
from bgy_core.bgy_logger import _get_today_log_path

logger = get_logger("Mailer")

COOLDOWN_FILE = os.path.join(LOGS_DIR, "notifier_cooldown.json")
DEFAULT_COOLDOWN_MIN = 30

# Check che non fanno diventare l'email ❌ se falliscono
WARNING_ONLY_CHECKS = {'avionio_confronto'}


# =============================================================================
# FLAG DI SILENZIAMENTO
# =============================================================================

def _notifications_config():
    try:
        cfg = config_manager.get_data_config()
        return cfg.get("notifications", {}) or {}
    except Exception:
        return {}


def is_master_enabled():
    return bool(_notifications_config().get("enabled", True))


def are_alerts_enabled():
    if not is_master_enabled():
        return False
    return bool(_notifications_config().get("alerts_enabled", True))


def is_daily_status_enabled():
    if not is_master_enabled():
        return False
    return bool(_notifications_config().get("daily_status_enabled", True))


def get_notifications_state():
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
    try:
        cfg = config_manager.get_data_config()
        return int(cfg.get("notifications", {}).get("cooldown_minutes", DEFAULT_COOLDOWN_MIN))
    except Exception:
        return DEFAULT_COOLDOWN_MIN


def can_send(key):
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
    try:
        if os.path.exists(COOLDOWN_FILE):
            os.remove(COOLDOWN_FILE)
            logger.info("🗑️ Cooldown resettato")
        return True
    except Exception as e:
        logger.error(f"Errore reset cooldown: {e}")
        return False


def get_active_cooldowns():
    return _load_cooldown()


# =============================================================================
# INVIO SMTP
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
# ALERT
# =============================================================================

def send_alert(key, subject, body, force=False):
    if not force and not are_alerts_enabled():
        logger.info(f"🔕 Allarme '{key}' silenziato (notifications.alerts_enabled=False)")
        return True

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
# EMAIL DI STATO (HTML)
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
.header {{ background: linear-gradient(135deg, #ffffff 0%, #87CEEB 50%, #1a2a6c 100%); color: #1a2a6c; padding: 25px; border-radius: 12px 12px 0 0; text-align: center; }}
.header h1 {{ color: #1a2a6c; text-shadow: 0 1px 2px rgba(255,255,255,0.8); }}
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


# =============================================================================
# FORMATTAZIONE STATISTICHE (v2.5.9)
# =============================================================================

def _format_cat_line(cat_key, cat_label, cat_data):
    """Riga singola categoria."""
    d = cat_data.get("decolli", 0)
    a = cat_data.get("atterraggi", 0)
    if d == 0 and a == 0:
        return None
    return f"   {cat_label}: D={d:>3}  A={a:>3}  (tot {d + a})"


def _format_delay_section(delay, yesterday_str):
    """Formatta la sezione puntualità + cancellati + distribuzione fasce."""
    if not delay:
        return ""

    lines = []
    totale = delay.get("totale_voli", 0)
    if totale == 0:
        return ""

    in_rit = delay.get("in_ritardo", 0)
    in_oro = delay.get("in_orario", 0)
    in_ant = delay.get("in_anticipo", 0)
    medio = delay.get("ritardo_medio", 0.0)
    massimo = delay.get("ritardo_massimo", 0)
    canc_count = delay.get("cancellati_count", 0)

    pct = round(100.0 * in_rit / totale, 1) if totale > 0 else 0.0

    lines.append(f"⏱️  PUNTUALITÀ ({yesterday_str})")
    lines.append(f"   • Voli in ritardo: {in_rit:>3}  ({pct}%)")
    if in_rit > 0:
        lines.append(f"   • Ritardo medio:   {medio} min")
        lines.append(f"   • Ritardo massimo: {massimo} min")
    lines.append(f"   • In orario:       {in_oro:>3}")
    lines.append(f"   • In anticipo:     {in_ant:>3}")
    lines.append("")

    # Distribuzione per fasce (Fase 2)
    fasce = delay.get("fasce", {})
    if fasce:
        lines.append("   📊 Distribuzione per fascia di ritardo:")
        for nome, count in fasce.items():
            if count > 0:
                barra = "█" * min(count, 30)
                lines.append(f"     • {nome:<10} {count:>3}  {barra}")
        lines.append("")

    if canc_count > 0:
        lines.append(f"❌ CANCELLATI: {canc_count}")
        for c in delay.get("cancellati", [])[:20]:
            lines.append(f"   • {c.get('callsign', '?')} "
                         f"({c.get('compagnia', '?')} -> {c.get('destinazione', '?')})")
        if canc_count > 20:
            lines.append(f"   ... e altri {canc_count - 20}")
        lines.append("")

    return "\n".join(lines)


def _format_stats_section(stats, yesterday_str):
    lines = []

    daily = stats.get("daily") if stats else None
    nightly = stats.get("nightly") if stats else None
    delay = stats.get("delay") if stats else None

    if daily:
        lines.append(f"📊 MOVIMENTI DEL GIORNO ({yesterday_str})")
        lines.append(f"   • Decolli:    {daily.get('decolli', 0):>3}")
        lines.append(f"   • Atterraggi: {daily.get('atterraggi', 0):>3}")
        lines.append(f"   • TOTALE:     {daily.get('totale', 0):>3}")
        lines.append("")

    # Sezione puntualita + cancellati
    if delay:
        delay_text = _format_delay_section(delay, yesterday_str)
        if delay_text:
            lines.append(delay_text)

    if nightly:
        lines.append(f"🌙 MOVIMENTI DELLA NOTTE ({yesterday_str})")
        for cat_key, cat_label in (("passeggeri", "Passeggeri"),
                                    ("cargo", "Cargo"),
                                    ("charter", "Charter")):
            cat = nightly.get(cat_key, {})
            d = cat.get("decolli", 0)
            a = cat.get("atterraggi", 0)
            t = cat.get("totale", 0)
            lines.append(f"   {cat_label}:")
            lines.append(f"     • Decolli:    {d:>3}")
            lines.append(f"     • Atterraggi: {a:>3}")
            lines.append(f"     • Sub-totale: {t:>3}")
        lines.append(f"   ─────────────────────")
        lines.append(f"   TOTALE NOTTE: {nightly.get('totale', 0)}")
        lines.append("")

        sconf = nightly.get("sconfinamenti", {})
        sconf_tot = sconf.get("totale", 0)
        if sconf_tot > 0:
            lines.append("🚨 SCONFINAMENTI")
            lines.append("   (voli schedulati fuori fascia, ritardo < 1h)")
            for cat_key, cat_label in (("passeggeri", "Passeggeri"),
                                        ("cargo", "Cargo"),
                                        ("charter", "Charter")):
                line = _format_cat_line(cat_key, cat_label, sconf.get(cat_key, {}))
                if line:
                    lines.append(line)
            lines.append(f"   ─────────────────────")
            lines.append(f"   TOTALE SCONFINAMENTI: {sconf_tot}")
            lines.append("")

        sconf_gravi = nightly.get("sconfinamenti_gravi", {})
        sconf_gravi_tot = sconf_gravi.get("totale", 0)
        if sconf_gravi_tot > 0:
            lines.append("🚨🚨 SCONFINAMENTI GRAVI")
            lines.append("   (voli schedulati fuori fascia, ritardo >= 1h)")
            for cat_key, cat_label in (("passeggeri", "Passeggeri"),
                                        ("cargo", "Cargo"),
                                        ("charter", "Charter")):
                line = _format_cat_line(cat_key, cat_label, sconf_gravi.get(cat_key, {}))
                if line:
                    lines.append(line)
            lines.append(f"   ─────────────────────")
            lines.append(f"   TOTALE GRAVI: {sconf_gravi_tot}")
            lines.append("")

        anomalie = nightly.get("anomalie", {})
        anom_tot = anomalie.get("totale", 0)
        if anom_tot > 0:
            lines.append("⚠️  ANOMALIE NOTTURNE")
            lines.append("   (voli a tabellone 3+ ore dopo lo sched)")
            dettagli = anomalie.get("dettagli", [])
            for d in dettagli[:10]:
                lines.append(
                    f"   • {d.get('callsign', '?')} "
                    f"({d.get('direzione_sacbo', '?')}) "
                    f"sched={d.get('orario_schedulato', '?')}"
                )
            if len(dettagli) > 10:
                lines.append(f"   ... e altre {len(dettagli) - 10} anomalie")
            lines.append(f"   ─────────────────────")
            lines.append(f"   TOTALE ANOMALIE: {anom_tot}")
            lines.append("")

    return "\n".join(lines)


def send_daily_status(success=True, details="", checks=None, stats=None,
                      screenshot_paths=None, force=False):
    if not force and not is_daily_status_enabled():
        logger.info("🔕 Email di stato giornaliero silenziata")
        return True

    if checks:
        all_ok = all(
            ok for k, (ok, _) in checks.items()
            if k not in WARNING_ONLY_CHECKS
        )
    else:
        all_ok = success

    status_icon = "✅" if all_ok else "❌"
    status_text = "OK" if all_ok else "KO"
    subject = (f"{status_icon} Monitoraggio BGY - "
               f"{datetime.now().strftime('%d/%m/%Y')} [{status_text}]")

    from datetime import timedelta
    yesterday_dt = datetime.now() - timedelta(days=1)
    yesterday_str = yesterday_dt.strftime("%d/%m/%Y")

    parts = []

    if checks:
        parts.append("Riepilogo processi di monitoraggio:")
        parts.append("")
        labels = [
            ('sacbo_acquisition', '1) Acquisizione dati dal tabellone SACBO'),
            ('sacbo_processing', '2) Elaborazione dati dal tabellone SACBO'),
            ('night_acquisition', '3) Acquisizione dati notturni (23:00-05:59)'),
            ('night_enrichment', '4) Arricchimento dati notturni'),
            ('github_sync', '5) Sincronizzazione GitHub'),
            ('db_sync', '6) Sincronizzazione Database'),
            ('quality_check', '7) Verifica qualità dati'),
            ('unresolved_airlines', '8) Compagnie da risolvere'),
            ('scanner_day_status', '9) Diagnostica scanner diurno'),
            ('avionio_confronto', '10) Conferma incrociata Avionio'),
            ('db_service', '11) Servizio Database'),
        ]
        for key, label in labels:
            if key in checks:
                ok, msg = checks[key]
                icon = '✅' if ok else '❌'
                stato = 'OK' if ok else 'KO'
                # Warning-only: icona ⚠️ invece di ❌
                if key in WARNING_ONLY_CHECKS and not ok:
                    icon = '⚠️'
                    stato = 'WARN'
                parts.append(f"{icon} {label}: {stato}")
                if msg:
                    if key == 'quality_check':
                        parts.append(msg)
                    elif key in ('unresolved_airlines', 'scanner_day_status',
                                 'avionio_confronto', 'db_service'):
                        for line in msg.split('\n'):
                            parts.append(f"   {line}")
                    else:
                        parts.append(f"      → {msg}")
                parts.append("")

    if stats:
        stats_text = _format_stats_section(stats, yesterday_str)
        if stats_text:
            parts.append("━" * 37)
            parts.append("")
            parts.append(stats_text)

    body = "\n".join(parts)
    if details:
        body += f"\n{details}"

    attachments = []

    if not all_ok:
        only_sync_error = (
            checks and
            'github_sync' in checks and
            not checks['github_sync'][0] and
            all(ok for k, (ok, _) in checks.items()
                if k not in ('github_sync', 'quality_check',
                             'unresolved_airlines', 'scanner_day_status',
                             'avionio_confronto', 'db_service'))
        )
        if not only_sync_error:
            log_path = _get_today_log_path()
            if log_path:
                attachments.append(log_path)
                body += (f"\n\n📎 In allegato il file di log completo: "
                         f"{os.path.basename(log_path)}")

    screenshots_present = []
    if screenshot_paths:
        for sp in screenshot_paths:
            if sp and os.path.exists(sp):
                attachments.append(sp)
                screenshots_present.append(sp)

    if screenshots_present:
        body += ("\n\n📸 In allegato gli screenshot del tabellone: "
                 + ", ".join(os.path.basename(s) for s in screenshots_present))

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