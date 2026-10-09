"""
bgy_core/bgy_wordpress.py - Pubblicazione dati su WordPress via REST API.
Versione 1.0.3

Scopo:
  - Caricare i file JSON aggregati (bgy-data.csv, bgy-delays.csv) nella
    Media Library di WordPress, sovrascrivendo i precedenti.
  - Verificare la connessione REST API.
  - Gestire le credenziali via config_wordpress.json.

Architettura:
  - Opzione A (raccomandata): JSON statici pubblicati su WordPress,
    letti lato browser via endpoint REST custom (wp-json/bgy/v1/*).

Sicurezza:
  - Usa Application Password (Basic Auth over HTTPS).
  - Non committare mai config_wordpress.json su Git.
  - Il token è limitato all'utente BGY (ruolo amministratore).

Novità v1.0.3 (08/10/2026):
- FIX CRITICO: il filename remoto è ora derivato dal path locale
  (os.path.basename), non più da config. Prima, qualsiasi file
  pubblicato veniva rinominato in 'bgy-data.csv', sovrascrivendo
  il file notturno quando si pubblicava bgy-delays.csv.
- Ogni file locale mantiene il proprio nome su WordPress.

Novità v1.0.2:
- Ritorno a .csv con Content-Type text/csv, dopo che il filtro MIME
  è stato autorizzato lato WordPress. Il file locale inizia con una
  riga di prefisso '#' (gestita da bgy_export_web.py) per superare
  il controllo magic-bytes di WordPress.

Novità v1.0.1 (breve parentesi .txt):
- Estensione file cambiata da .csv a .txt con Content-Type text/plain.
  Tentativo di aggirare il blocco MIME. Non sufficiente.

Novità v1.0.0:
- Prima versione.

Uso:
    py -3.12 -m bgy_core.bgy_wordpress --test
    py -3.12 -m bgy_core.bgy_wordpress --publish <path_to_json>
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

def _find_media_by_filename(filename):
    """
    Cerca un media nella Media Library per nome file.
    Ritorna l'ID del media se trovato, altrimenti None.
    """
    headers = _auth_header()
    if not headers:
        return None

    cfg = _cfg()
    timeout = int(cfg.get("http_timeout", 30))
    verify = bool(cfg.get("verify_ssl", True))

    search_term = filename.rsplit(".", 1)[0]

    try:
        r = requests.get(
            _api_url("/wp/v2/media"),
            headers=headers,
            params={"search": search_term, "per_page": 20},
            timeout=timeout,
            verify=verify,
        )
        if r.status_code != 200:
            logger.warning(f"Errore ricerca media: HTTP {r.status_code}")
            return None

        items = r.json()
        for item in items:
            slug = item.get("slug", "")
            source_url = item.get("source_url", "")
            if search_term in slug or search_term in source_url:
                return item.get("id")
        return None
    except Exception as e:
        logger.warning(f"Errore ricerca media: {e}")
        return None


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


# -----------------------------------------------------------------------------
# PUBBLICAZIONE
# -----------------------------------------------------------------------------

def publish_json(local_json_path):
    """
    Pubblica un file JSON aggregato su WordPress, sostituendo il precedente
    con lo stesso nome.

    v1.0.3: il nome remoto è derivato da os.path.basename(local_json_path).
    Così bgy-data.csv → bgy-data.csv e bgy-delays.csv → bgy-delays.csv.

    Ritorna (ok, msg, source_url).
    """
    if not is_enabled():
        return False, "WordPress disabilitato in config", None

    if not os.path.exists(local_json_path):
        return False, f"File non trovato: {local_json_path}", None

    # v1.0.3: filename dal path locale, non da config
    filename = os.path.basename(local_json_path)
    if not filename:
        cfg = _cfg()
        filename = cfg.get("json_filename", "bgy-data.csv")

    existing_id = _find_media_by_filename(filename)
    if existing_id:
        _delete_media(existing_id)

    ok, media_id, source_url = _upload_media(local_json_path, filename)
    if not ok:
        return False, source_url or "Upload fallito", None

    return True, f"Pubblicato (id={media_id}, filename={filename})", source_url


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