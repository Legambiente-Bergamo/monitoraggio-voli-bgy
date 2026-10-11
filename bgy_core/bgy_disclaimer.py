"""
bgy_core/bgy_disclaimer.py - Gestione disclaimer web unificato.
Versione 1.0.0

Legge la sezione "disclaimers" di config_data.json e costruisce il JSON
che serve TUTTE le pagine web (notturna, ritardi, aeroporti, rumore, ...).

Struttura payload bgy-disclaimer.csv:
{
  "generated_at": "2026-10-10T18:30:00",
  "min_date": "2026-09-30",
  "global": { "show": bool, "title": str, "body": str },
  "pages": {
    "night":    { "show_global": bool, "extra": str },
    "delays":   { "show_global": bool, "extra": str },
    "airports": { "show_global": bool, "extra": str },
    "noise":    { "show_global": bool, "extra": str }
  }
}

Il placeholder {min_date} nel body viene sostituito automaticamente
con web_export.min_date (oggi: 2026-09-30).

API pubblica:
  build_disclaimer_json() -> dict | None
  save_disclaimer_json(payload) -> str | None
  export_and_publish_disclaimer() -> (ok, msg)
"""
import os
import json
from datetime import datetime

from bgy_core import get_logger, config_manager
from bgy_core.bgy_paths import DATA_DIR

logger = get_logger("Disclaimer")

# Stesso path di bgy_export_web.py
WEB_OUTPUT_DIR = os.path.join(DATA_DIR, "bgy_output", "bgy_web")
DISCLAIMER_OUTPUT_FILE = os.path.join(WEB_OUTPUT_DIR, "bgy-disclaimer.csv")
DISCLAIMER_PREFIX = "# BGY Monitoring Suite - DISCLAIMER - dati JSON sotto questa riga\n"

PAGES_KNOWN = ("night", "delays", "airports", "noise")


def _cfg_disclaimers():
    try:
        cfg = config_manager.get_data_config()
        return cfg.get("disclaimers", {}) or {}
    except Exception:
        return {}


def _cfg_web_min_date():
    try:
        cfg = config_manager.get_data_config()
        return (cfg.get("web_export", {}) or {}).get("min_date", "")
    except Exception:
        return ""


def _resolve_placeholders(text, min_date):
    if not text:
        return ""
    return str(text).replace("{min_date}", min_date or "")


def build_disclaimer_json():
    cfg = _cfg_disclaimers()
    if not cfg.get("enabled", True):
        logger.info("Sezione disclaimers disabilitata in config_data.json")
        return None

    min_date = _cfg_web_min_date()

    g_in = cfg.get("global", {}) or {}
    global_out = {
        "show":  bool(g_in.get("show", True)),
        "title": str(g_in.get("title", "")).strip(),
        "body":  _resolve_placeholders(g_in.get("body", ""), min_date),
    }

    pages_in = cfg.get("pages", {}) or {}
    pages_out = {}
    for page_key in PAGES_KNOWN:
        p = pages_in.get(page_key, {}) or {}
        pages_out[page_key] = {
            "show_global": bool(p.get("show_global", True)),
            "extra":       _resolve_placeholders(p.get("extra", ""), min_date),
        }

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "min_date": min_date,
        "global": global_out,
        "pages": pages_out,
    }

    n_extra = sum(1 for v in pages_out.values() if v["extra"])
    logger.info(
        f"Disclaimer JSON: global={'si' if global_out['show'] else 'no'}, "
        f"pagine={len(pages_out)}, extra non vuoti={n_extra}"
    )
    return payload


def save_disclaimer_json(payload):
    os.makedirs(WEB_OUTPUT_DIR, exist_ok=True)
    try:
        with open(DISCLAIMER_OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(DISCLAIMER_PREFIX)
            json.dump(payload, f, ensure_ascii=False, indent=2)
        size_kb = round(os.path.getsize(DISCLAIMER_OUTPUT_FILE) / 1024, 1)
        logger.info(f"Disclaimer salvato: {DISCLAIMER_OUTPUT_FILE} ({size_kb} KB)")
        return DISCLAIMER_OUTPUT_FILE
    except Exception as e:
        logger.error(f"Errore salvataggio disclaimer: {e}")
        return None


def export_and_publish_disclaimer():
    """
    Rigenera bgy-disclaimer.csv e lo pubblica su WordPress.
    Ritorna (ok, msg) come gli altri exporter.
    """
    from bgy_core import bgy_wordpress

    payload = build_disclaimer_json()
    if not payload:
        return False, "Disclaimer disabilitato o vuoto"

    local_path = save_disclaimer_json(payload)
    if not local_path:
        return False, "Errore salvataggio locale"

    if not bgy_wordpress.is_enabled():
        return True, f"Disclaimer locale salvato ({local_path}), WordPress disabilitato"

    ok, msg, url = bgy_wordpress.publish_json(local_path)
    return (True, f"Disclaimer pubblicato: {url}") if ok else (False, f"Errore: {msg}")