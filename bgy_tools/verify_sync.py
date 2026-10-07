"""
bgy_tools/verify_sync.py - Verifica stato sync GitHub e backup.
Versione 1.0.0

Ruolo:
  - Fornisce una funzione check_all() che ritorna un dict strutturato
    con lo stato di: GitHub sync, backup DB (Google Drive), backup locale (HD).
  - CLI per verifica manuale da terminale.
  - Usato da:
      - bgy_scheduler.job_daily() → nuova sezione email del mattino
      - bgy_gui.bgy_gui_sync_backup → tab GUI con forzatura manuale

Novità v1.0.0 (INFRA-02, 07/10/2026):
- Prima versione.
- check_github_status(): legge git status/log + confronto con origin.
- check_backup_db_status(): legge bgy_data/bgy_logs/backup.log.
- check_backup_local_status(): placeholder per INFRA-03 (HD esterno).
- check_all(): combina i tre.
- CLI:
    py -3.12 -m bgy_tools.verify_sync
    py -3.12 -m bgy_tools.verify_sync --json
    py -3.12 -m bgy_tools.verify_sync --sync      # forza sync GitHub
    py -3.12 -m bgy_tools.verify_sync --backup    # forza backup DB
    py -3.12 -m bgy_tools.verify_sync --all       # sync + backup

Contratto di output (check_all):
  {
    "github": {
      "enabled": bool,
      "ok": bool,
      "status": "in_sync" | "ahead" | "behind" | "diverged" | "error" | "disabled",
      "last_commit_local": str,
      "last_commit_local_hash": str,
      "last_commit_remote": str | None,
      "last_commit_remote_hash": str | None,
      "ahead": int,
      "behind": int,
      "modified_files": [str],  # file staged/modified/untracked
      "modified_count": int,
      "message": str,
    },
    "backup_db": {
      "enabled": bool,
      "ok": bool,
      "status": "ok" | "stale" | "missing" | "error" | "disabled",
      "last_success": str | None,
      "age_hours": float | None,
      "threshold_hours": int,
      "message": str,
    },
    "backup_local": {
      "enabled": bool,
      "ok": bool,
      "status": "ok" | "stale" | "not_configured" | "missing_path" | "error",
      "path": str | None,
      "last_success": str | None,
      "age_hours": float | None,
      "threshold_hours": int,
      "message": str,
    },
    "overall_ok": bool,
    "checked_at": str,  # ISO timestamp
  }
"""
import os
import re
import sys
import json
import subprocess as sp
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import PROJECT_ROOT, LOGS_DIR
from bgy_core.bgy_config_manager import config_manager

logger = get_logger("VerifySync")

BACKUP_LOG_FILE = os.path.join(LOGS_DIR, "backup.log")
BACKUP_DB_MAX_AGE_HOURS = 36
BACKUP_LOCAL_MAX_AGE_HOURS = 48
GIT_CMD_TIMEOUT_SEC = 20


# -----------------------------------------------------------------------------
# GITHUB SYNC
# -----------------------------------------------------------------------------

def _run_git(args, timeout=GIT_CMD_TIMEOUT_SEC, allow_prompt=False):
    """
    Esegue un comando git in PROJECT_ROOT. Ritorna (code, stdout, stderr).
    Di default blocca qualunque prompt di credenziali (non interattivo).
    """
    env = os.environ.copy()
    if not allow_prompt:
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GCM_INTERACTIVE"] = "Never"
        env["GIT_ASKPASS"] = "echo"

    try:
        result = sp.run(
            ["git"] + args,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except sp.TimeoutExpired:
        return -1, "", f"Timeout dopo {timeout}s"
    except FileNotFoundError:
        return -1, "", "Git non trovato nel PATH"
    except Exception as e:
        return -1, "", str(e)


def _git_last_commit(ref=None):
    """
    Ritorna (hash, subject, iso_date) dell'ultimo commit.
    Se ref è None, usa HEAD. Se ref è 'origin/main', usa il riferimento remoto.
    Ritorna (None, None, None) se il comando fallisce.
    """
    fmt = "%H|%s|%ai"
    args = ["log", "-1", f"--format={fmt}"]
    if ref:
        args.append(ref)
    code, out, err = _run_git(args)
    if code != 0 or not out:
        return None, None, None
    parts = out.split("|", 2)
    if len(parts) < 3:
        return None, None, None
    return parts[0], parts[1], parts[2]


def _git_modified_files():
    """
    Ritorna la lista di file modificati/staged/untracked.
    Formato riga: 'XY path' (X=staged, Y=working tree).
    """
    code, out, err = _run_git(["status", "--porcelain"])
    if code != 0:
        return []
    files = []
    for line in out.split("\n"):
        line = line.rstrip()
        if not line:
            continue
        if len(line) < 4:
            continue
        status = line[:2]
        path = line[3:].strip()
        files.append(f"[{status}] {path}")
    return files


def _git_ahead_behind(branch, remote="origin"):
    """
    Ritorna (ahead, behind) rispetto a <remote>/<branch>.
    ahead = commit locali non sul remoto; behind = commit remoti non locali.
    Ritorna (0, 0) se non riesce a determinare.
    """
    ref = f"{remote}/{branch}"
    code, out, _ = _run_git(["rev-list", "--count", f"{ref}..HEAD"])
    ahead = int(out) if code == 0 and out.isdigit() else 0
    code, out, _ = _run_git(["rev-list", "--count", f"HEAD..{ref}"])
    behind = int(out) if code == 0 and out.isdigit() else 0
    return ahead, behind


def _git_remote_ref_exists(branch, remote="origin"):
    code, out, _ = _run_git(["rev-parse", "--verify", f"{remote}/{branch}"])
    return code == 0


def check_github_status(branch_override=None):
    """
    Verifica lo stato del sync GitHub.
    Ritorna un dict strutturato (vedi contratto in testa al modulo).
    """
    result = {
        "enabled": False,
        "ok": True,
        "status": "disabled",
        "last_commit_local": None,
        "last_commit_local_hash": None,
        "last_commit_remote": None,
        "last_commit_remote_hash": None,
        "ahead": 0,
        "behind": 0,
        "modified_files": [],
        "modified_count": 0,
        "message": "GitHub sync disabilitato",
    }

    try:
        cfg = config_manager.get_github_config() or {}
    except Exception as e:
        result["ok"] = False
        result["status"] = "error"
        result["message"] = f"Errore lettura config GitHub: {e}"
        return result

    result["enabled"] = bool(cfg.get("enabled", True))

    if not result["enabled"]:
        result["message"] = "GitHub sync disabilitato in config"
        return result

    # Verifica repo git
    if not os.path.isdir(os.path.join(PROJECT_ROOT, ".git")):
        result["ok"] = False
        result["status"] = "error"
        result["message"] = "Repo Git non inizializzato"
        return result

    branch = branch_override or cfg.get("branch", "main")

    # Ultimo commit locale
    h_local, subj_local, date_local = _git_last_commit()
    result["last_commit_local"] = subj_local
    result["last_commit_local_hash"] = h_local[:7] if h_local else None

    # Fetch per allineare il ref remoto (fallisce silenziosamente se non
    # c'è rete o credenziali, senza bloccare)
    _run_git(["fetch", "origin", branch], timeout=15)

    if not _git_remote_ref_exists(branch):
        result["status"] = "error"
        result["ok"] = False
        result["message"] = f"Riferimento origin/{branch} non trovato (fetch fallito?)"
        return result

    # Ultimo commit remoto
    h_remote, subj_remote, date_remote = _git_last_commit(f"origin/{branch}")
    result["last_commit_remote"] = subj_remote
    result["last_commit_remote_hash"] = h_remote[:7] if h_remote else None

    # Ahead/behind
    ahead, behind = _git_ahead_behind(branch)
    result["ahead"] = ahead
    result["behind"] = behind

    # File modificati/untracked
    modified = _git_modified_files()
    result["modified_files"] = modified
    result["modified_count"] = len(modified)

    # Stato sintetico
    if ahead > 0 and behind > 0:
        result["status"] = "diverged"
        result["ok"] = False
        result["message"] = f"Diverged: {ahead} commit locali, {behind} remoti"
    elif ahead > 0:
        result["status"] = "ahead"
        # ahead da solo non è errore (il sync di domani pusherà)
        result["ok"] = True
        result["message"] = f"{ahead} commit locali non ancora pushati"
    elif behind > 0:
        result["status"] = "behind"
        result["ok"] = False
        result["message"] = f"{behind} commit remoti non ancora pullati"
    else:
        result["status"] = "in_sync"
        result["ok"] = True
        if result["modified_count"] > 0:
            result["message"] = (f"In sync, {result['modified_count']} file "
                                  f"modificati (verranno pushati al prossimo sync)")
        else:
            result["message"] = "In sync, nessuna modifica locale"

    return result


# -----------------------------------------------------------------------------
# BACKUP DB
# -----------------------------------------------------------------------------

def check_backup_db_status():
    """
    Verifica lo stato dell'ultimo backup DB su Google Drive.
    Legge bgy_data/bgy_logs/backup.log.
    """
    result = {
        "enabled": True,
        "ok": True,
        "status": "ok",
        "last_success": None,
        "age_hours": None,
        "threshold_hours": BACKUP_DB_MAX_AGE_HOURS,
        "message": "",
    }

    if not os.path.exists(BACKUP_LOG_FILE):
        result["ok"] = False
        result["status"] = "missing"
        result["message"] = "Log backup non trovato (nessun backup mai eseguito?)"
        return result

    last_success_ts = None
    last_error_msg = None
    try:
        with open(BACKUP_LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "Backup completato con successo" in line:
                    parts = line.split(" - ", 1)
                    if parts:
                        last_success_ts = parts[0].strip()
                elif "ERRORE:" in line:
                    parts = line.split("ERRORE:", 1)
                    if len(parts) == 2:
                        last_error_msg = parts[1].strip()
    except Exception as e:
        result["ok"] = False
        result["status"] = "error"
        result["message"] = f"Errore lettura log: {str(e)[:80]}"
        return result

    if not last_success_ts:
        result["ok"] = False
        result["status"] = "missing"
        msg = "Nessun backup completato con successo nel log"
        if last_error_msg:
            msg += f" (ultimo errore: {last_error_msg[:80]})"
        result["message"] = msg
        return result

    result["last_success"] = last_success_ts

    try:
        success_dt = datetime.strptime(last_success_ts, "%Y-%m-%d %H:%M:%S")
        age_hours = (datetime.now() - success_dt).total_seconds() / 3600
        result["age_hours"] = round(age_hours, 1)
    except Exception as e:
        result["ok"] = False
        result["status"] = "error"
        result["message"] = f"Errore parsing timestamp: {str(e)[:80]}"
        return result

    if result["age_hours"] > BACKUP_DB_MAX_AGE_HOURS:
        result["ok"] = False
        result["status"] = "stale"
        result["message"] = (f"Ultimo backup OK: {last_success_ts} "
                              f"({result['age_hours']:.1f}h fa, "
                              f"soglia {BACKUP_DB_MAX_AGE_HOURS}h)")
    else:
        result["ok"] = True
        result["status"] = "ok"
        result["message"] = (f"Backup OK: {last_success_ts} "
                              f"({result['age_hours']:.1f}h fa)")

    return result


# -----------------------------------------------------------------------------
# BACKUP LOCALE (placeholder per INFRA-03)
# -----------------------------------------------------------------------------

def _load_backup_local_config():
    """
    Legge da config_data.json la sezione 'backup_local' (se esiste).
    Struttura attesa:
      {
        "enabled": true,
        "path": "E:\\\\BGY_Backup",
        "max_age_hours": 48,
        "include_credentials": true
      }
    Se assente, ritorna {'enabled': False, 'path': None}.
    """
    try:
        cfg = config_manager.get_data_config() or {}
        section = cfg.get("backup_local", {}) or {}
        return {
            "enabled": bool(section.get("enabled", False)),
            "path": section.get("path") or None,
            "max_age_hours": int(section.get("max_age_hours", BACKUP_LOCAL_MAX_AGE_HOURS)),
            "include_credentials": bool(section.get("include_credentials", True)),
        }
    except Exception:
        return {
            "enabled": False,
            "path": None,
            "max_age_hours": BACKUP_LOCAL_MAX_AGE_HOURS,
            "include_credentials": True,
        }


def check_backup_local_status():
    """
    Verifica lo stato del backup locale su HD esterno.
    In INFRA-02 è un placeholder: senza config ritorna 'not_configured'.
    In INFRA-03 diventerà un check reale che legge l'ultimo file di backup.
    """
    result = {
        "enabled": False,
        "ok": True,
        "status": "not_configured",
        "path": None,
        "last_success": None,
        "age_hours": None,
        "threshold_hours": BACKUP_LOCAL_MAX_AGE_HOURS,
        "message": "Backup locale non configurato (INFRA-03)",
    }

    cfg = _load_backup_local_config()
    result["enabled"] = cfg["enabled"]
    result["path"] = cfg["path"]
    result["threshold_hours"] = cfg["max_age_hours"]

    if not cfg["enabled"] or not cfg["path"]:
        return result

    # Configurato: verifica path esiste
    if not os.path.isdir(cfg["path"]):
        result["ok"] = False
        result["status"] = "missing_path"
        result["message"] = f"Percorso backup non raggiungibile: {cfg['path']}"
        return result

    # Cerca il file più recente nella cartella di backup
    try:
        latest_mtime = None
        for name in os.listdir(cfg["path"]):
            full = os.path.join(cfg["path"], name)
            if not os.path.isfile(full):
                continue
            mtime = os.path.getmtime(full)
            if latest_mtime is None or mtime > latest_mtime:
                latest_mtime = mtime

        if latest_mtime is None:
            result["ok"] = False
            result["status"] = "missing"
            result["message"] = f"Nessun file di backup in {cfg['path']}"
            return result

        last_dt = datetime.fromtimestamp(latest_mtime)
        age_hours = (datetime.now() - last_dt).total_seconds() / 3600
        result["last_success"] = last_dt.strftime("%Y-%m-%d %H:%M")
        result["age_hours"] = round(age_hours, 1)

        if age_hours > cfg["max_age_hours"]:
            result["ok"] = False
            result["status"] = "stale"
            result["message"] = (f"Backup locale fermo da {age_hours:.1f}h "
                                  f"(soglia {cfg['max_age_hours']}h)")
        else:
            result["ok"] = True
            result["status"] = "ok"
            result["message"] = (f"Backup locale OK: {result['last_success']} "
                                  f"({age_hours:.1f}h fa)")
    except Exception as e:
        result["ok"] = False
        result["status"] = "error"
        result["message"] = f"Errore verifica backup locale: {str(e)[:80]}"

    return result


# -----------------------------------------------------------------------------
# CHECK ALL
# -----------------------------------------------------------------------------

def check_all():
    """
    Esegue tutti i check e ritorna un dict combinato.
    Vedi contratto in testa al modulo.
    """
    github = check_github_status()
    backup_db = check_backup_db_status()
    backup_local = check_backup_local_status()

    overall_ok = github["ok"] and backup_db["ok"] and backup_local["ok"]

    return {
        "github": github,
        "backup_db": backup_db,
        "backup_local": backup_local,
        "overall_ok": overall_ok,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }


# -----------------------------------------------------------------------------
# AZIONI FORZATE (usate dalla CLI e dalla GUI)
# -----------------------------------------------------------------------------

def force_sync_github():
    """Forza un sync GitHub. Ritorna (ok, msg)."""
    try:
        from bgy_core.bgy_github_sync import sync_to_github
        return sync_to_github(force=True)
    except Exception as e:
        return False, f"Errore sync GitHub: {str(e)[:120]}"


def force_backup_db():
    """
    Forza un backup DB lanciando bgy_backup_db.ps1.
    Ritorna (ok, msg).
    """
    script_path = os.path.join(PROJECT_ROOT, "bgy_backup_db.ps1")
    if not os.path.exists(script_path):
        return False, f"Script non trovato: {script_path}"

    try:
        result = sp.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", script_path],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minuti
        )
        if result.returncode == 0:
            return True, "Backup DB completato"
        err = (result.stderr or result.stdout or "").strip()[:200]
        return False, f"Backup DB fallito (code {result.returncode}): {err}"
    except sp.TimeoutExpired:
        return False, "Backup DB timeout dopo 10 minuti"
    except Exception as e:
        return False, f"Errore backup DB: {str(e)[:120]}"


# -----------------------------------------------------------------------------
# RENDERING TESTO (per CLI e per email)
# -----------------------------------------------------------------------------

def format_text(check_result):
    """Ritorna una stringa multi-riga human-readable."""
    lines = []
    g = check_result["github"]
    b = check_result["backup_db"]
    bl = check_result["backup_local"]

    lines.append("📤 GitHub Sync")
    if not g["enabled"]:
        lines.append("   Stato:                 ⏸️  disabilitato")
    else:
        lines.append(f"   Ultimo commit locale:  {g['last_commit_local'] or '?'}"
                      f" ({g['last_commit_local_hash'] or '?'})")
        lines.append(f"   Ultimo commit remoto:  {g['last_commit_remote'] or '?'}"
                      f" ({g['last_commit_remote_hash'] or '?'})")
        icon = "✅" if g["status"] == "in_sync" else "⚠️"
        lines.append(f"   Stato:                 {icon} {g['status']}")
        if g["modified_count"] > 0:
            lines.append(f"   File modificati:       {g['modified_count']}")
    lines.append("")

    lines.append("🗄️  Backup DB (Google Drive)")
    if not b["enabled"]:
        lines.append("   Stato:                 ⏸️  disabilitato")
    else:
        lines.append(f"   Ultimo OK:             {b['last_success'] or '?'}"
                      + (f" ({b['age_hours']:.1f}h fa)"
                         if b['age_hours'] is not None else ""))
        icon = "✅" if b["status"] == "ok" else "❌"
        lines.append(f"   Stato:                 {icon} {b['status']}")
    lines.append("")

    lines.append("💾 Backup locale (HD esterno)")
    if bl["status"] == "not_configured":
        lines.append("   Stato:                 ⏸️  non configurato")
    else:
        lines.append(f"   Percorso:              {bl['path'] or '?'}")
        lines.append(f"   Ultimo OK:             {bl['last_success'] or '?'}"
                      + (f" ({bl['age_hours']:.1f}h fa)"
                         if bl['age_hours'] is not None else ""))
        icon = "✅" if bl["status"] == "ok" else "❌"
        lines.append(f"   Stato:                 {icon} {bl['status']}")

    return "\n".join(lines)


def format_compact(check_result):
    """
    Ritorna una stringa compatta (una riga per sezione) per l'email.
    """
    g = check_result["github"]
    b = check_result["backup_db"]
    bl = check_result["backup_local"]

    parts = []
    parts.append(f"GitHub: {g['status']}")
    if b["enabled"]:
        parts.append(f"Backup DB: {b['status']}")
    if bl["enabled"]:
        parts.append(f"Backup locale: {bl['status']}")

    return " | ".join(parts)


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def _cmd_check(as_json=False, compact=False):
    result = check_all()
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    elif compact:
        print(format_compact(result))
    else:
        print()
        print("=" * 60)
        print("STATO SYNC E BACKUP")
        print("=" * 60)
        print()
        print(format_text(result))
        print()
        print("=" * 60)
        print(f"OVERALL: {'✅ OK' if result['overall_ok'] else '❌ PROBLEMI'}")
        print(f"Checked at: {result['checked_at']}")
        print("=" * 60)
    return 0 if result["overall_ok"] else 1


def _cmd_sync():
    print("🔄 Forzo sync GitHub...")
    ok, msg = force_sync_github()
    print(f"{'✅' if ok else '❌'} {msg}")
    return 0 if ok else 1


def _cmd_backup():
    print("🔄 Forzo backup DB...")
    ok, msg = force_backup_db()
    print(f"{'✅' if ok else '❌'} {msg}")
    return 0 if ok else 1


def _cmd_all():
    print("🔄 Forzo sync GitHub + backup DB...")
    print()
    print("--- Sync GitHub ---")
    ok1, msg1 = force_sync_github()
    print(f"{'✅' if ok1 else '❌'} {msg1}")
    print()
    print("--- Backup DB ---")
    ok2, msg2 = force_backup_db()
    print(f"{'✅' if ok2 else '❌'} {msg2}")
    print()
    return 0 if (ok1 and ok2) else 1


def main():
    parser = argparse.ArgumentParser(
        description="Verifica stato sync GitHub e backup.")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON strutturato")
    parser.add_argument("--compact", action="store_true",
                        help="Output compatto (una riga per sezione)")
    parser.add_argument("--sync", action="store_true",
                        help="Forza sync GitHub")
    parser.add_argument("--backup", action="store_true",
                        help="Forza backup DB")
    parser.add_argument("--all", action="store_true",
                        help="Forza sync GitHub + backup DB")
    args = parser.parse_args()

    if args.sync:
        sys.exit(_cmd_sync())
    if args.backup:
        sys.exit(_cmd_backup())
    if args.all:
        sys.exit(_cmd_all())

    sys.exit(_cmd_check(as_json=args.json, compact=args.compact))


if __name__ == "__main__":
    main()