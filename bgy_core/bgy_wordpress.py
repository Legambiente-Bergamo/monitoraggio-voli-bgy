"""
bgy_core/bgy_wordpress.py - Pubblicazione dati su WordPress via REST API.
Versione 1.1.0

Novità v1.1.0 (INFRA-08, 20/10/2026):
- Opzione B: naming timestampato. Il file viene caricato con un nome
  univoco (es. bgy-data_20261020_174500.csv). Il vecchio file non
  viene cancellato prima del caricamento, eliminando la finestra 404.
- Cleanup automatico: dopo l'upload, vengono eliminati i file vecchi
  mantenendo solo i 3 più recenti per lo stesso prefisso.

Novità v1.0.3:
- FIX CRITICO: il filename remoto è derivato dal path locale.
"""
import os
import sys
import json
import base64
import argparse
from datetime import datetime

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_config_manager import config_manager
from bgy_core.bgy_paths import CONFIG_DIR

logger = get_logger("WordPress")

CONFIG_WORDPRESS = os.path.join(CONFIG_DIR, "config_wordpress.json")


# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------

def _cfg():
    """Legge config_wordpress.json (cache + fallback file)."""
    cfg = config_manager.configs.get("wordpress", {})
    if cfg:
        return cfg

    if os.path.exists(CONFIG_WORDPRESS):
        try:
            with open(CONFIG_WORDPRESS, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                config_manager.configs["wordpress"] = cfg
                return cfg
        except Exception as e:
            logger.error(f"Errore lettura config_wordpress.json: {e}")
    return {}


def is_enabled():
    cfg = _cfg()
    return bool(cfg.get("enabled", False))


def _auth_header():
    """Costruisce l'header di Basic Auth con username + app_password."""
    cfg = _cfg()
    user = cfg.get("username", "").strip()
    pwd = cfg.get("app_password", "").strip()
    if not user or not pwd:
        return None
    token = base64.b64encode(f"{user}:{pwd}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _api_url(path):
    """Costruisce l'URL completo della REST API."""
    cfg = _cfg()
    base = cfg.get("base_url", "").rstrip("/")
    return f"{base}/wp-json{path}"


# -----------------------------------------------------------------------------
# TEST CONNESSIONE
# -----------------------------------------------------------------------------

def test_connection():
    """Verifica che le credenziali funzionino. Ritorna (ok, msg)."""
    cfg = _cfg()
    if not cfg:
        return False, "config_wordpress.json non trovato o vuoto"

    if not cfg.get("username") or not cfg.get("app_password"):
        return False, "Credenziali WordPress mancanti in config"

    headers = _auth_header()
    if not headers:
        return False, "Impossibile costruire l'header di autenticazione"

    timeout = int(cfg.get("http_timeout", 30))
    verify = bool(cfg.get("verify_ssl", True))

    try:
        r = requests.get(
            _api_url("/wp/v2/users/me"),
            headers=headers,
            timeout=timeout,
            verify=verify,
        )
        if r.status_code == 200:
            data = r.json()
            name = data.get("name", "?")
            user_id = data.get("id", "?")
            return True, f"Connesso come '{name}' (id={user_id})"
        if r.status_code == 401:
            return False, "401 Unauthorized: credenziali errate"
        if r.status_code == 403:
            return False, "403 Forbidden: l'utente non ha i permessi necessari"
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except requests.Timeout:
        return False, f"Timeout nella connessione (>{timeout}s)"
    except requests.RequestException as e:
        return False, f"Errore di rete: {e}"


# -----------------------------------------------------------------------------
# GESTIONE MEDIA
# -----------------------------------------------------------------------------

def _find_all_media_by_prefix(base_name, ext):
    """Trova tutti i media che iniziano con base_name e finiscono con ext."""
    headers = _auth_header()
    if not headers:
        return []

    cfg = _cfg()
    timeout = int(cfg.get("http_timeout", 30))
    verify = bool(cfg.get("verify_ssl", True))

    try:
        r = requests.get(
            _api_url("/wp/v2/media"),
            headers=headers,
            params={"search": base_name, "per_page": 20},
            timeout=timeout,
            verify=verify,
        )
        if r.status_code != 200:
            return []

        items = r.json()
        valid_items = []
        for item in items:
            source_url = item.get("source_url", "")
            filename = source_url.split("/")[-1]
            # Match esatto del prefisso e dell'estensione
            if filename.startswith(f"{base_name}_") and filename.endswith(ext):
                valid_items.append(item)
        
        # Ordina per ID discendente (il più recente prima)
        valid_items.sort(key=lambda x: x.get("id", 0), reverse=True)
        return valid_items
    except Exception as e:
        logger.warning(f"Errore ricerca media: {e}")
        return []


def _delete_media(media_id):
    """Cancella un media dalla Media Library (force=true)."""
    headers = _auth_header()
    if not headers:
        return False

    cfg = _cfg()
    timeout = int(cfg.get("http_timeout", 30))
    verify = bool(cfg.get("verify_ssl", True))

    try:
        r = requests.delete(
            _api_url(f"/wp/v2/media/{media_id}"),
            headers=headers,
            params={"force": "true"},
            timeout=timeout,
            verify=verify,
        )
        if r.status_code in (200, 201):
            logger.info(f"🗑️ Media ID {media_id} cancellato")
            return True
        logger.warning(f"Errore cancellazione media {media_id}: HTTP {r.status_code}")
        return False
    except Exception as e:
        logger.warning(f"Errore cancellazione media: {e}")
        return False


def _upload_media(local_path, remote_filename):
    """
    Carica un file nella Media Library.
    Ritorna (ok, media_id, source_url).
    """
    headers = _auth_header()
    if not headers:
        return False, None, "Autenticazione non configurata"

    cfg = _cfg()
    timeout = int(cfg.get("http_timeout", 30))
    verify = bool(cfg.get("verify_ssl", True))

    try:
        with open(local_path, "rb") as f:
            file_bytes = f.read()
    except Exception as e:
        return False, None, f"Errore lettura file locale: {e}"

    upload_headers = dict(headers)
    upload_headers["Content-Disposition"] = (
        f'attachment; filename="{remote_filename}"'
    )
    upload_headers["Content-Type"] = "text/csv"

    try:
        r = requests.post(
            _api_url("/wp/v2/media"),
            headers=upload_headers,
            data=file_bytes,
            timeout=timeout,
            verify=verify,
        )
        if r.status_code in (200, 201):
            data = r.json()
            media_id = data.get("id")
            source_url = data.get("source_url")
            logger.info(f"✅ Media caricato: id={media_id}, url={source_url}")
            return True, media_id, source_url
        logger.error(f"❌ Upload fallito: HTTP {r.status_code}: {r.text[:300]}")
        return False, None, f"HTTP {r.status_code}: {r.text[:200]}"
    except requests.Timeout:
        return False, None, "Timeout durante l'upload"
    except Exception as e:
        return False, None, f"Errore upload: {e}"


def _cleanup_old_media(base_name, ext, keep=3):
    """Mantiene solo i 'keep' file più recenti per un dato prefisso."""
    all_media = _find_all_media_by_prefix(base_name, ext)
    if len(all_media) <= keep:
        return
    
    to_delete = all_media[keep:]
    for item in to_delete:
        _delete_media(item.get("id"))


# -----------------------------------------------------------------------------
# PUBBLICAZIONE
# -----------------------------------------------------------------------------

def publish_json(local_json_path):
    """
    Pubblica un file JSON aggregato su WordPress con un nome timestampato.
    Ritorna (ok, msg, source_url).
    """
    if not is_enabled():
        return False, "WordPress disabilitato in config", None

    if not os.path.exists(local_json_path):
        return False, f"File non trovato: {local_json_path}", None

    filename = os.path.basename(local_json_path)
    base_name, ext = os.path.splitext(filename)
    
    # Genera il nome timestampato (es. bgy-data_20261020_174500.csv)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    remote_filename = f"{base_name}_{timestamp}{ext}"

    # Carica il nuovo file (non cancelliamo nulla prima)
    ok, media_id, source_url = _upload_media(local_json_path, remote_filename)
    if not ok:
        return False, source_url or "Upload fallito", None

    # Cleanup: mantieni solo gli ultimi 3 file
    _cleanup_old_media(base_name, ext, keep=3)

    return True, f"Pubblicato (id={media_id}, filename={remote_filename})", source_url


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Pubblicazione dati su WordPress"
    )
    parser.add_argument("--test", action="store_true",
                        help="Verifica la connessione")
    parser.add_argument("--publish", type=str,
                        help="Pubblica il file JSON specificato")
    args = parser.parse_args()

    if args.test:
        ok, msg = test_connection()
        print(f"{'✅' if ok else '❌'} {msg}")
        sys.exit(0 if ok else 1)

    if args.publish:
        ok, msg, url = publish_json(args.publish)
        print(f"{'✅' if ok else '❌'} {msg}")
        if url:
            print(f"🔗 URL pubblico: {url}")
        sys.exit(0 if ok else 1)

    parser.print_help()


if __name__ == "__main__":
    main()