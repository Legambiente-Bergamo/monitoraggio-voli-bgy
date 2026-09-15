"""
core/bgy_github_sync.py - Sincronizzazione automatica verso GitHub.
v2.3.9: flusso robusto (commit locale prima del pull), no credential prompt,
        timeout aumentato, gestione config auto-arricchite.
"""
import os
import sys
import json
import subprocess as sp
from datetime import datetime

from core.bgy_logger import get_logger
from core.bgy_paths import PROJECT_ROOT, CONFIG_DIR
from core.bgy_notifier import send_alert

logger = get_logger("GitHubSync")

CONFIG_GITHUB = os.path.join(CONFIG_DIR, "config_github.json")


def _load_github_config():
    if not os.path.exists(CONFIG_GITHUB):
        logger.warning(f"⚠️ config_github.json non trovato: {CONFIG_GITHUB}")
        return None
    try:
        with open(CONFIG_GITHUB, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Errore lettura config GitHub: {e}")
        return None


def _run_git(args, cwd=None, timeout=60, check_credential_prompt=False):
    """
    Esegue un comando git.
    Se check_credential_prompt=True, imposta GIT_TERMINAL_PROMPT=0 per evitare
    prompt interattivi che bloccherebbero il processo.
    """
    env = os.environ.copy()
    if check_credential_prompt:
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GCM_INTERACTIVE"] = "Never"
        env["GIT_ASKPASS"] = "echo"

    try:
        result = sp.run(
            ["git"] + args,
            cwd=cwd or PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except sp.TimeoutExpired:
        return -1, "", f"Timeout dopo {timeout}s"
    except FileNotFoundError:
        return -1, "", "Git non trovato nel PATH"
    except Exception as e:
        return -1, "", str(e)


def _ensure_remote_url(cfg):
    """Imposta l'URL del remote con il token per autenticazione automatica."""
    token = cfg.get("token", "").strip()
    repo_url = cfg.get("repo_url", "").strip()

    if not token or not repo_url:
        logger.error("❌ Token o repo_url mancanti")
        return False

    # Inserisci il token nell'URL
    if "@" in repo_url:
        parts = repo_url.split("://", 1)
        if len(parts) == 2:
            after_scheme = parts[1]
            if "@" in after_scheme:
                after_scheme = after_scheme.split("@", 1)[1]
            repo_url = f"{parts[0]}://{token}@{after_scheme}"
    else:
        parts = repo_url.split("://", 1)
        if len(parts) == 2:
            repo_url = f"{parts[0]}://{token}@{parts[1]}"

    code, _, err = _run_git(["remote", "set-url", "origin", repo_url])
    if code != 0:
        logger.error(f"❌ Errore set-url remote: {err}")
        return False
    return True


def _is_repo_initialized():
    return os.path.isdir(os.path.join(PROJECT_ROOT, ".git"))


def _disable_credential_helper():
    """Disabilita il credential helper locale per evitare prompt bloccanti."""
    _run_git(["config", "--local", "credential.helper", ""])


def _count_staged_or_modified():
    """Ritorna il numero di file modificati/nuovi."""
    code, out, _ = _run_git(["status", "--porcelain"])
    if code != 0:
        return 0
    return len([l for l in out.split("\n") if l.strip()])


def sync_to_github(force=False):
    """
    Sincronizza il progetto su GitHub.
    Flusso robusto:
    1. git add -A + commit locale (se ci sono modifiche)
    2. git pull --rebase
    3. git push
    """
    cfg = _load_github_config()
    if not cfg:
        return False, "Configurazione GitHub non trovata"

    if not cfg.get("enabled", True) and not force:
        logger.info("⏸️ Sync GitHub disabilitato in config")
        return True, "Sync disabilitato"

    if not _is_repo_initialized():
        return False, "Repo Git non inizializzato (esegui setup una tantum)"

    # 1. Verifica Git disponibile
    code, _, _ = _run_git(["--version"])
    if code != 0:
        return False, "Git non disponibile"

    # 2. Imposta identità locale
    _run_git(["config", "user.name", cfg.get("username", "Legambiente Bergamo")])
    _run_git(["config", "user.email", cfg.get("email", "info@legambientebergamo.it")])

    # 3. Disabilita credential prompt (evita blocco con pythonw)
    _disable_credential_helper()

    # 4. Imposta URL con token
    if not _ensure_remote_url(cfg):
        send_alert(
            "github_sync_failed",
            "⚠️ BGY - Sync GitHub fallito",
            "Impossibile impostare il remote GitHub.\n"
            "Verifica il token in config_github.json"
        )
        return False, "Errore configurazione remote"

    branch = cfg.get("branch", "main")

    # 5. Assicura branch corretto
    _run_git(["checkout", branch])

    # 6. Aggiungi TUTTE le modifiche (config auto-arricchite incluse)
    code, _, err = _run_git(["add", "-A"])
    if code != 0:
        return False, f"Errore git add: {err}"

    # 7. Conta modifiche
    modified_count = _count_staged_or_modified()

    # 8. Se ci sono modifiche, committa PRIMA del pull
    if modified_count > 0:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        prefix = cfg.get("commit_prefix", "BGY Sync")
        commit_msg = f"{prefix} - {timestamp}"
        code, _, err = _run_git(["commit", "-m", commit_msg])
        if code != 0:
            # Potrebbe essere che non ci siano davvero modifiche da committare
            logger.warning(f"⚠️ git commit: {err}")

    # 9. Pull con rebase (ora senza modifiche pendenti)
    code, _, err = _run_git(["pull", "--rebase", "origin", branch],
                             timeout=60, check_credential_prompt=True)
    if code != 0 and "couldn't find remote ref" not in err.lower() \
            and "already up to date" not in err.lower() \
            and "already up-to-date" not in err.lower():
        logger.warning(f"⚠️ git pull: {err}")
        # Prova a abortire un eventuale rebase in corso
        _run_git(["rebase", "--abort"])

    # 10. Push con timeout aumentato (300s)
    timeout = cfg.get("push_timeout_seconds", 300)
    code, _, err = _run_git(["push", "origin", branch],
                             timeout=timeout, check_credential_prompt=True)

    if code != 0:
        send_alert(
            "github_push_failed",
            "⚠️ BGY - Push GitHub fallito",
            f"Errore durante il push:\n{err}\n\n"
            "Possibili cause:\n"
            "- Token scaduto o revocato\n"
            "- Conflitto con modifiche remote\n"
            "- Problema di rete\n\n"
            "Controlla config_github.json."
        )
        return False, f"Errore git push: {err}"

    if modified_count == 0:
        logger.info("ℹ️ Nessuna modifica da sincronizzare")
        return True, "Nessuna modifica"

    logger.info(f"✅ Sync GitHub completato ({modified_count} file)")
    return True, f"Sync OK ({modified_count} file)"


if __name__ == "__main__":
    success, msg = sync_to_github()
    print(f"{'✅' if success else '❌'} {msg}")