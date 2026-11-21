"""
bgy_core/bgy_disclaimer.py - Gestione centralizzata Nota Metodologica e Disclaimer web.
Versione 1.1.0
"""
import os
import json
from datetime import datetime

from bgy_core import get_logger, config_manager
from bgy_core.bgy_paths import DATA_DIR

logger = get_logger("Disclaimer")

WEB_OUTPUT_DIR = os.path.join(DATA_DIR, "bgy_output", "bgy_web")
DISCLAIMER_OUTPUT_FILE = os.path.join(WEB_OUTPUT_DIR, "bgy-disclaimer.csv")
DISCLAIMER_PREFIX = "# BGY Monitoring Suite - DISCLAIMER - dati JSON sotto questa riga\n"

PAGES_KNOWN = ("home", "night", "delays", "anticipi", "fleet", "airports", "noise", "runway")


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


def _build_section(raw_sec, min_date):
    sec = raw_sec or {}
    if not sec.get("enabled", True):
        return None
    g_in = sec.get("global", {}) or {}
    global_out = {
        "show":  bool(g_in.get("show", True)),
        "title": str(g_in.get("title", "")).strip(),
        "body":  _resolve_placeholders(g_in.get("body", ""), min_date),
    }
    pages_in = sec.get("pages", {}) or {}
    pages_out = {}
    for page_key in PAGES_KNOWN:
        p = pages_in.get(page_key, {}) or {}
        pages_out[page_key] = {
            "show_global": bool(p.get("show_global", True)),
            "extra":       _resolve_placeholders(p.get("extra", ""), min_date),
        }
    return {"global": global_out, "pages": pages_out}


def build_disclaimer_json():
    try:
        cfg = config_manager.get_data_config() or {}
    except Exception:
        cfg = {}

    min_date = _cfg_web_min_date()
    disc_sec = _build_section(cfg.get("disclaimers", {}), min_date)
    meth_sec = _build_section(cfg.get("methodology", {}), min_date)

    if not disc_sec and not meth_sec:
        logger.info("Sezioni disclaimers e methodology disabilitate in config_data.json")
        return None

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "min_date": min_date,
        "global": (disc_sec or {}).get("global", {"show": False, "title": "", "body": ""}),
        "pages": (disc_sec or {}).get("pages", {}),
        "methodology": meth_sec or {"global": {"show": False, "title": "", "body": ""}, "pages": {}},
    }
    logger.info("Disclaimer & Nota Metodologica JSON generati correttamente")
    return payload


def save_disclaimer_json(payload):
    os.makedirs(WEB_OUTPUT_DIR, exist_ok=True)
    try:
        with open(DISCLAIMER_OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(DISCLAIMER_PREFIX)
            json.dump(payload, f, ensure_ascii=True, indent=2)
        size_kb = round(os.path.getsize(DISCLAIMER_OUTPUT_FILE) / 1024, 1)
        logger.info(f"Disclaimer salvato: {DISCLAIMER_OUTPUT_FILE} ({size_kb} KB)")
        return DISCLAIMER_OUTPUT_FILE
    except Exception as e:
        logger.error(f"Errore salvataggio disclaimer: {e}")
        return None


def export_and_publish_disclaimer():
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
