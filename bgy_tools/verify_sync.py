"""
bgy_tools/verify_sync.py - Verifica stato sync GitHub e backup.
Versione 1.1.0

Novita v1.1.0 (INFRA-03, 07/10/2026):
- check_backup_local_status() riscritto: legge lo state file
  bgy_data/bgy_logs/backup_local_state.json scritto da bgy_backup_local.ps1.
  Cosi' il check funziona anche se l'HD non e' connesso al momento.
- Aggiunto campo hd_connected: se True, l'HD e' raggiungibile ora.
- Nuova force_backup_local(): esegue bgy_backup_local.ps1.

Novita v1.0.0 (INFRA-02, 07/10/2026):
- Prima versione.

Uso:
    py -3.12 -m bgy_tools.verify_sync
    py -3.12 -m bgy_tools.verify_sync --json
    py -3.12 -m bgy_tools.verify_sync --sync
    py -3.12 -m bgy_tools.verify_sync --backup
    py -3.12 -m bgy_tools.verify_sync --backup-local
    py -3.12 -m bgy_tools.verify_sync --all
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
BACKUP_LOCAL_LOG_FILE = os.path.join(LOGS_DIR, "backup_local.log")
BACKUP_LOCAL_STATE_FILE = os.path.join(LOGS_DIR, "backup_local_state.json")

BACKUP_DB_MAX_AGE_HOURS = 36
BACKUP_LOCAL_MAX_AGE_HOURS = 48
GIT_CMD_TIMEOUT_SEC = 20


# -----------------------------------------------------------------------------
# GITHUB SYNC
# -----------------------------------------------------------------------------

def _run_git(args, timeout=GIT_CMD_TIMEOUT_SEC, allow_prompt=False):
    env = os.environ.copy()
    if not allow_prompt:
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GCM_INTERACTIVE"] = "Never"
        env["GIT_ASKPASS"] = "echo"
    try:
        result = sp.run(
            ["git"] + args, cwd=PROJECT_ROOT,
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except sp.TimeoutExpired:
        return -1, "", f"Timeout dopo {timeout}s"
    except FileNotFoundError:
        return -1, "", "Git non trovato nel PATH"
    except Exception as e:
        return -1, "", str(e)


def _git_last_commit(ref=None):
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
    code, out, err = _run_git(["status", "--porcelain"])
    if code != 0:
        return []
    files = []
    for line in out.split("\n"):
        line = line.rstrip()
        if not line or len(line) < 4:
            continue
        files.append(f"[{line[:2]}] {line[3:].strip()}")
    return files


def _git_ahead_behind(branch, remote="origin"):
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
    result = {
        "enabled": False, "ok": True, "status": "disabled",
        "last_commit_local": None, "last_commit_local_hash": None,
        "last_commit_remote": None, "last_commit_remote_hash": None,
        "ahead": 0, "behind": 0,
        "modified_files": [], "modified_count": 0,
        "message": "GitHub sync disabilitato",
    }
    try:
        cfg = config_manager.get_github_config() or {}
    except Exception as e:
        result["ok"] = False; result["status"] = "error"
        result["message"] = f"Errore lettura config GitHub: {e}"
        return result

    result["enabled"] = bool(cfg.get("enabled", True))
    if not result["enabled"]:
        result["message"] = "GitHub sync disabilitato in config"
        return result

    if not os.path.isdir(os.path.join(PROJECT_ROOT, ".git")):
        result["ok"] = False; result["status"] = "error"
        result["message"] = "Repo Git non inizializzato"
        return result

    branch = branch_override or cfg.get("branch", "main")

    h_local, subj_local, _ = _git_last_commit()
    result["last_commit_local"] = subj_local
    result["last_commit_local_hash"] = h_local[:7] if h_local else None

    _run_git(["fetch", "origin", branch], timeout=15)

    if not _git_remote_ref_exists(branch):
        result["status"] = "error"; result["ok"] = False
        result["message"] = f"Riferimento origin/{branch} non trovato (fetch fallito?)"
        return result

    h_remote, subj_remote, _ = _git_last_commit(f"origin/{branch}")
    result["last_commit_remote"] = subj_remote
    result["last_commit_remote_hash"] = h_remote[:7] if h_remote else None

    ahead, behind = _git_ahead_behind(branch)
    result["ahead"] = ahead
    result["behind"] = behind

    modified = _git_modified_files()
    result["modified_files"] = modified
    result["modified_count"] = len(modified)

    if ahead > 0 and behind > 0:
        result["status"] = "diverged"; result["ok"] = False
        result["message"] = f"Diverged: {ahead} commit locali, {behind} remoti"
    elif ahead > 0:
        result["status"] = "ahead"; result["ok"] = True
        result["message"] = f"{ahead} commit locali non ancora pushati"
    elif behind > 0:
        result["status"] = "behind"; result["ok"] = False
        result["message"] = f"{behind} commit remoti non ancora pullati"
    else:
        result["status"] = "in_sync"; result["ok"] = True
        if result["modified_count"] > 0:
            result["message"] = (f"In sync, {result['modified_count']} file "
                                 f"modificati (verranno pushati al prossimo sync)")
        else:
            result["message"] = "In sync, nessuna modifica locale"

    return result


# -----------------------------------------------------------------------------
# BACKUP DB (GOOGLE DRIVE)
# -----------------------------------------------------------------------------

def check_backup_db_status():
    result = {
        "enabled": True, "ok": True, "status": "ok",
        "last_success": None, "age_hours": None,
        "threshold_hours": BACKUP_DB_MAX_AGE_HOURS, "message": "",
    }

    if not os.path.exists(BACKUP_LOG_FILE):
        result["ok"] = False; result["status"] = "missing"
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
        result["ok"] = False; result["status"] = "error"
        result["message"] = f"Errore lettura log: {str(e)[:80]}"
        return result

    if not last_success_ts:
        result["ok"] = False; result["status"] = "missing"
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
        result["ok"] = False; result["status"] = "error"
        result["message"] = f"Errore parsing timestamp: {str(e)[:80]}"
        return result

    if result["age_hours"] > BACKUP_DB_MAX_AGE_HOURS:
        result["ok"] = False; result["status"] = "stale"
        result["message"] = (f"Ultimo backup OK: {last_success_ts} "
                             f"({result['age_hours']:.1f}h fa, "
                             f"soglia {BACKUP_DB_MAX_AGE_HOURS}h)")
    else:
        result["ok"] = True; result["status"] = "ok"
        result["message"] = (f"Backup OK: {last_success_ts} "
                             f"({result['age_hours']:.1f}h fa)")
    return result


# -----------------------------------------------------------------------------
# BACKUP LOCALE (HD ESTERNO) — v1.1.0
# -----------------------------------------------------------------------------

def _load_backup_local_config():
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
            "enabled": False, "path": None,
            "max_age_hours": BACKUP_LOCAL_MAX_AGE_HOURS,
            "include_credentials": True,
        }


def _load_backup_local_state():
    if not os.path.exists(BACKUP_LOCAL_STATE_FILE):
        return {}
    try:
        with open(BACKUP_LOCAL_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def check_backup_local_status():
    result = {
        "enabled": False, "ok": True, "status": "not_configured",
        "path": None, "hd_connected": False,
        "last_success": None, "age_hours": None,
        "threshold_hours": BACKUP_LOCAL_MAX_AGE_HOURS,
        "message": "Backup locale non configurato (INFRA-03)",
    }

    cfg = _load_backup_local_config()
    result["enabled"] = cfg["enabled"]
    result["path"] = cfg["path"]
    result["threshold_hours"] = cfg["max_age_hours"]

    if not cfg["enabled"] or not cfg["path"]:
        return result

    hd_connected = os.path.isdir(cfg["path"])
    result["hd_connected"] = hd_connected

    state = _load_backup_local_state()
    last_success = state.get("last_success")
    result["last_success"] = last_success

    if not last_success:
        result["ok"] = False
        result["status"] = "missing"
        if hd_connected:
            result["message"] = "Nessun backup locale trovato (HD connesso)"
        else:
            result["message"] = "Nessun backup locale trovato (HD non connesso)"
        return result

    try:
        success_dt = datetime.fromisoformat(last_success)
        age_hours = (datetime.now() - success_dt).total_seconds() / 3600
        result["age_hours"] = round(age_hours, 1)
    except Exception as e:
        result["ok"] = False; result["status"] = "error"
        result["message"] = f"Errore parsing timestamp: {str(e)[:80]}"
        return result

    if age_hours > cfg["max_age_hours"]:
        result["ok"] = False; result["status"] = "stale"
        hd_note = "" if hd_connected else " (HD non connesso)"
        result["message"] = (
            f"Ultimo backup locale: {last_success[:19]} "
            f"({age_hours:.1f}h fa, soglia {cfg['max_age_hours']}h){hd_note}"
        )
        return result

    if not hd_connected:
        result["ok"] = True
        result["status"] = "hd_disconnected"
        result["message"] = (
            f"Ultimo backup locale OK ({age_hours:.1f}h fa), "
            f"ma HD non connesso ora"
        )
        return result

    result["ok"] = True
    result["status"] = "ok"
    result["message"] = (f"Backup locale OK: {last_success[:19]} "
                          f"({age_hours:.1f}h fa)")
    return result


# -----------------------------------------------------------------------------
# CHECK ALL
# -----------------------------------------------------------------------------

def check_all():
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
# AZIONI FORZATE
# -----------------------------------------------------------------------------

def force_sync_github():
    try:
        from bgy_core.bgy_github_sync import sync_to_github
        return sync_to_github(force=True)
    except Exception as e:
        return False, f"Errore sync GitHub: {str(e)[:120]}"


def force_backup_db():
    script_path = os.path.join(PROJECT_ROOT, "bgy_backup_db.ps1")
    if not os.path.exists(script_path):
        return False, f"Script non trovato: {script_path}"
    try:
        result = sp.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", script_path],
            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=600,
        )
        if result.returncode == 0:
            return True, "Backup DB completato"
        err = (result.stderr or result.stdout or "").strip()[:200]
        return False, f"Backup DB fallito (code {result.returncode}): {err}"
    except sp.TimeoutExpired:
        return False, "Backup DB timeout dopo 10 minuti"
    except Exception as e:
        return False, f"Errore backup DB: {str(e)[:120]}"


def force_backup_local():
    """v1.1.0: esegue bgy_backup_local.ps1."""
    script_path = os.path.join(PROJECT_ROOT, "bgy_backup_local.ps1")
    if not os.path.exists(script_path):
        return False, f"Script non trovato: {script_path}"
    try:
        result = sp.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", script_path],
            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=1800,
        )
        if result.returncode == 0:
            return True, "Backup locale completato"
        if result.returncode == 2:
            return False, "HD esterno E: non collegato"
        err = (result.stderr or result.stdout or "").strip()[:200]
        return False, f"Backup locale fallito (code {result.returncode}): {err}"
    except sp.TimeoutExpired:
        return False, "Backup locale timeout dopo 30 minuti"
    except Exception as e:
        return False, f"Errore backup locale: {str(e)[:120]}"


# -----------------------------------------------------------------------------
# RENDERING TESTO
# -----------------------------------------------------------------------------

_STATUS_ICON = {
    "in_sync": "✅", "ahead": "✅", "behind": "⚠️", "diverged": "❌",
    "disabled": "⏸️", "error": "❌",
    "ok": "✅", "stale": "❌", "missing": "❌",
    "not_configured": "⏸️", "hd_disconnected": "⚠️", "missing_path": "⚠️",
}


def _icon(status):
    return _STATUS_ICON.get(status, "❓")


def format_text(check_result):
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
        lines.append(f"   Stato:                 {_icon(g['status'])} {g['status']}")
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
        lines.append(f"   Stato:                 {_icon(b['status'])} {b['status']}")
    lines.append("")

    lines.append("💾 Backup locale (HD esterno)")
    if bl["status"] == "not_configured":
        lines.append("   Stato:                 ⏸️  non configurato")
    else:
        lines.append(f"   Percorso:              {bl['path'] or '?'}")
        lines.append(f"   HD connesso ora:       "
                     f"{'✅ sì' if bl['hd_connected'] else '❌ no'}")
        lines.append(f"   Ultimo OK:             {bl['last_success'] or '?'}"
                     + (f" ({bl['age_hours']:.1f}h fa)"
                        if bl['age_hours'] is not None else ""))
        lines.append(f"   Stato:                 "
                     f"{_icon(bl['status'])} {bl['status']}")

    return "\n".join(lines)


def format_compact(check_result):
    g = check_result["github"]
    b = check_result["backup_db"]
    bl = check_result["backup_local"]

    parts = [f"GitHub: {g['status']}"]
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
    print("🔄 Forzo backup DB (Google Drive)...")
    ok, msg = force_backup_db()
    print(f"{'✅' if ok else '❌'} {msg}")
    return 0 if ok else 1


def _cmd_backup_local():
    print("🔄 Forzo backup locale (HD esterno)...")
    ok, msg = force_backup_local()
    print(f"{'✅' if ok else '❌'} {msg}")
    return 0 if ok else 1


def _cmd_all():
    print("🔄 Forzo sync GitHub + backup DB + backup locale...")
    print()
    print("--- Sync GitHub ---")
    ok1, msg1 = force_sync_github()
    print(f"{'✅' if ok1 else '❌'} {msg1}")
    print()
    print("--- Backup DB (Google Drive) ---")
    ok2, msg2 = force_backup_db()
    print(f"{'✅' if ok2 else '❌'} {msg2}")
    print()
    print("--- Backup locale (HD esterno) ---")
    ok3, msg3 = force_backup_local()
    print(f"{'✅' if ok3 else '❌'} {msg3}")
    print()
    return 0 if (ok1 and ok2 and ok3) else 1


def main():
    parser = argparse.ArgumentParser(
        description="Verifica stato sync GitHub e backup.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--backup", action="store_true",
                        help="Forza backup DB (Google Drive)")
    parser.add_argument("--backup-local", action="store_true",
                        help="Forza backup locale (HD esterno)")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if args.sync:
        sys.exit(_cmd_sync())
    if args.backup:
        sys.exit(_cmd_backup())
    if args.backup_local:
        sys.exit(_cmd_backup_local())
    if args.all:
        sys.exit(_cmd_all())

    sys.exit(_cmd_check(as_json=args.json, compact=args.compact))


if __name__ == "__main__":
    main()