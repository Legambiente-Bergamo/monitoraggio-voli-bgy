"""
core/bgy_github_sync.py - Sincronizzazione automatica verso GitHub.
Sincronizza: script, config generiche, dati raw.
Esclude: report, grafici, log, credenziali.
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
    """Carica la configurazione GitHub."""
    if not os.path.exists(CONFIG_GITHUB):
        logger.warning(f"⚠️ config_github.json non trovato: {CONFIG_GITHUB}")
        return None
    try:
        with open(CONFIG_GITHUB, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Errore lettura config GitHub: {e}")
        return None


def _run_git(args, cwd=None, timeout=60):
    """Esegue un comando git. Ritorna (returncode, stdout, stderr)."""
    try:
        result = sp.run(
            ["git"] + args,
            cwd=cwd or PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except sp.TimeoutExpired:
        return -1, "", f"Timeout dopo {timeout}s"
    except FileNotFoundError:
        return -1, "", "Git non trovato nel PATH"
    except Exception as e:
        return -1, "", str(e)


def _ensure_remote_url(cfg):
    """Imposta l'URL del remote con il token per l'autenticazione."""
    token = cfg.get("token", "").strip()
    repo_url = cfg.get("repo_url", "").strip()

    if not token:
        logger.error("❌ Token GitHub mancante in config_github.json")
        return False
    if not repo_url:
        logger.error("❌ repo_url mancante in config_github.json")
        return False

    # Inserisci il token nell'URL per autenticazione automatica
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
    """Verifica se il repo git è già inizializzato."""
    git_dir = os.path.join(PROJECT_ROOT, ".git")
    return os.path.isdir(git_dir)


def sync_to_github(force=False):
    """
    Sincronizza il progetto su GitHub.
    Ritorna (success: bool, message: str).
    """
    cfg = _load_github_config()
    if not cfg:
        return False, "Configurazione GitHub non trovata"

    if not cfg.get("enabled", True) and not force:
        logger.info("⏸️ Sync GitHub disabilitato in config")
        return True, "Sync disabilitato"

    if not _is_repo_initialized():
        return False, "Repo Git non inizializzato (esegui setup una tantum)"

    code, out, _ = _run_git(["--version"])
    if code != 0:
        return False, "Git non disponibile"

    _run_git(["config", "user.name", cfg.get("username", "Legambiente Bergamo")])
    _run_git(["config", "user.email", cfg.get("email", "info@legambientebergamo.it")])

    if not _ensure_remote_url(cfg):
        send_alert(
            "github_sync_failed",
            "⚠️ BGY - Sync GitHub fallito",
            "Impossibile impostare il remote GitHub.\n"
            "Verifica il token in config_github.json"
        )
        return False, "Errore configurazione remote"

    branch = cfg.get("branch", "main")
    _run_git(["checkout", branch])

    code, out, err = _run_git(["pull", "--rebase", "origin", branch], timeout=60)
    if code != 0 and "couldn't find remote ref" not in err.lower():
        logger.warning(f"⚠️ git pull: {err}")

    code, out, err = _run_git(["add", "-A"])
    if code != 0:
        return False, f"Errore git add: {err}"

    code, out, _ = _run_git(["status", "--porcelain"])
    if not out:
        logger.info("ℹ️ Nessuna modifica da sincronizzare")
        return True, "Nessuna modifica"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    prefix = cfg.get("commit_prefix", "BGY Sync")
    commit_msg = f"{prefix} - {timestamp}"
    code, out, err = _run_git(["commit", "-m", commit_msg])
    if code != 0:
        return False, f"Errore git commit: {err}"

    code, out, _ = _run_git(["diff", "--stat", "HEAD~1", "HEAD"])
    changed_files = out.split("\n")[-1] if out else "?"

    timeout = cfg.get("push_timeout_seconds", 120)
    code, out, err = _run_git(["push", "origin", branch], timeout=timeout)
    if code != 0:
        send_alert(
            "github_push_failed",
            "⚠️ BGY - Push GitHub fallito",
            f"Errore durante il push:\n{err}\n\n"
            "Possibili cause:\n"
            "- Token scaduto o revocato\n"
            "- Conflitto con modifiche remote\n"
            "- Problema di rete\n\n"
            "Controlla config_github.json e riprova manualmente."
        )
        return False, f"Errore git push: {err}"

    logger.info(f"✅ Sync GitHub completato: {changed_files}")
    return True, f"Sync OK ({changed_files})"


if __name__ == "__main__":
    success, msg = sync_to_github()
    print(f"{'✅' if success else '❌'} {msg}")