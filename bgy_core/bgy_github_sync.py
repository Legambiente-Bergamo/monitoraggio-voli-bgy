"""
bgy_core/bgy_github_sync.py - Sincronizzazione automatica verso GitHub.
v2.5.0 - config via config_manager
"""
import os
import sys
import subprocess as sp
from datetime import datetime

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import PROJECT_ROOT
from bgy_core.bgy_config_manager import config_manager
from bgy_core.bgy_mailer import send_alert

logger = get_logger("GitHubSync")


def _load_github_config():
    """Legge config GitHub via config_manager. Ritorna dict o None se incompleta."""
    cfg = config_manager.get_github_config()
    if not cfg:
        logger.warning("Config GitHub non trovata")
        return None
    if not cfg.get("repo_url"):
        logger.warning("config_github.json: repo_url mancante")
        return None
    return cfg


def _run_git(args, cwd=None, timeout=60, check_credential_prompt=False):
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
    token = cfg.get("token", "").strip()
    repo_url = cfg.get("repo_url", "").strip()

    if not token or not repo_url:
        logger.error("❌ Token o repo_url mancanti")
        return False

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
    _run_git(["config", "--local", "credential.helper", ""])


def _count_staged_or_modified():
    code, out, _ = _run_git(["status", "--porcelain"])
    if code != 0:
        return 0
    return len([l for l in out.split("\n") if l.strip()])


def sync_to_github(force=False):
    cfg = _load_github_config()
    if not cfg:
        return False, "Configurazione GitHub non trovata"

    if not cfg.get("enabled", True) and not force:
        logger.info("⏸️ Sync GitHub disabilitato in config")
        return True, "Sync disabilitato"

    if not _is_repo_initialized():
        return False, "Repo Git non inizializzato (esegui setup una tantum)"

    code, _, _ = _run_git(["--version"])
    if code != 0:
        return False, "Git non disponibile"

    _run_git(["config", "user.name", cfg.get("username", "Legambiente Bergamo")])
    _run_git(["config", "user.email", cfg.get("email", "info@legambientebergamo.it")])
    _disable_credential_helper()

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

    code, _, err = _run_git(["add", "-A"])
    if code != 0:
        return False, f"Errore git add: {err}"

    modified_count = _count_staged_or_modified()

    if modified_count > 0:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        prefix = cfg.get("commit_prefix", "BGY Sync")
        commit_msg = f"{prefix} - {timestamp}"
        code, _, err = _run_git(["commit", "-m", commit_msg])
        if code != 0:
            logger.warning(f"⚠️ git commit: {err}")

    pull_timeout = cfg.get("pull_timeout_seconds", 60)
    code, _, err = _run_git(["pull", "--rebase", "origin", branch],
                             timeout=pull_timeout, check_credential_prompt=True)
    if code != 0 and "couldn't find remote ref" not in err.lower() \
            and "already up to date" not in err.lower() \
            and "already up-to-date" not in err.lower():
        logger.warning(f"⚠️ git pull: {err}")
        _run_git(["rebase", "--abort"])

    push_timeout = cfg.get("push_timeout_seconds", 300)
    code, _, err = _run_git(["push", "origin", branch],
                             timeout=push_timeout, check_credential_prompt=True)

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