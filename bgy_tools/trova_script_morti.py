"""
bgy_tools/trova_script_morti.py - Analisi dead code.
Versione 1.0.0

Cerca file .py nel progetto che:
  - Non sono importati da nessun altro modulo.
  - Non sono entry point (non hanno `if __name__ == "__main__"` eseguito
    da un .bat o da uno scheduler).

Un file è classificato:
  - ENTRY POINT: ha un main richiamato da un .bat o da un processo.
  - MODULO ATTIVO: importato da almeno un altro modulo.
  - TOOL: ha un main ma non è importato (script lanciato a mano).
  - SOSPETTO MORT0: né entry point, né importato, né tool.

Uso:
    py -3.12 -m bgy_tools.trova_script_morti
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# File noti per essere entry point (non importati ma legittimi)
ENTRY_POINTS = {
    "bgy_gui.py",
    "bgy_scheduler.py",
    "bgy_watchdog.py",
}

# Pattern di directory da ignorare
SKIP_DIRS = {"__pycache__", ".git", "bgy_data"}


def _read(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def _has_main(content):
    return bool(re.search(r'if\s+__name__\s*==\s*["\']__main__["\']', content))


def _collect_py_files():
    files = []
    for root, dirs, names in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            if name.endswith(".py"):
                files.append(os.path.join(root, name))
    return sorted(files)


def _module_name(path):
    """Es. bgy_core/bgy_db.py -> bgy_core.bgy_db"""
    rel = os.path.relpath(path, PROJECT_ROOT).replace(os.sep, "/")
    return rel[:-3].replace("/", ".")


def _find_imports(target_module, all_files):
    """
    Ritorna la lista di file che importano `target_module`.
    Cerca import di:
      - from bgy_core.bgy_db import ...
      - import bgy_core.bgy_db
      - from .bgy_db import ... (import relativo, cerca per nome file)
    """
    base_name = target_module.split(".")[-1]
    callers = []
    for f in all_files:
        if f == target_module:
            continue
        content = _read(f)
        # Import assoluto
        if re.search(rf'(from|import)\s+{re.escape(target_module)}\b', content):
            callers.append(os.path.relpath(f, PROJECT_ROOT))
            continue
        # Import relativo (stesso pacchetto)
        if re.search(rf'from\s+\.\s*{re.escape(base_name)}\s+import', content):
            callers.append(os.path.relpath(f, PROJECT_ROOT))
            continue
        if re.search(rf'from\s+\.\w+\s+import\s+\w*{re.escape(base_name)}', content):
            callers.append(os.path.relpath(f, PROJECT_ROOT))
            continue
    return callers


def _is_in_package_init(path, all_files):
    """Verifica se il file è esportato da un __init__.py del suo pacchetto."""
    dirpath = os.path.dirname(path)
    init_file = os.path.join(dirpath, "__init__.py")
    if not os.path.exists(init_file):
        return False
    init_content = _read(init_file)
    base_name = os.path.basename(path)[:-3]  # senza .py
    return bool(re.search(rf'\b{re.escape(base_name)}\b', init_content))


def main():
    print("=" * 78)
    print("ANALISI SCRIPT MORTI - BGY Monitoring Suite")
    print("=" * 78)
    print()

    files = _collect_py_files()
    print(f"File .py trovati: {len(files)}")
    print()

    moduli = {}  # module -> path
    for f in files:
        mod = _module_name(f)
        if mod.startswith("bgy_"):
            moduli[mod] = f

    sospetti = []
    entry = []
    attivi = []
    tool = []
    init_only = []

    for mod, path in sorted(moduli.items()):
        rel = os.path.relpath(path, PROJECT_ROOT)
        basename = os.path.basename(path)

        if basename == "__init__.py":
            init_only.append(rel)
            continue

        if basename in ENTRY_POINTS:
            entry.append(rel)
            continue

        content = _read(path)
        has_main = _has_main(content)
        imported_by_init = _is_in_package_init(path, files)
        callers = _find_imports(mod, files)

        if callers or imported_by_init:
            attivi.append((rel, callers[:3]))
        elif has_main:
            tool.append(rel)
        else:
            sospetti.append(rel)

    print("─" * 78)
    print(f"ENTRY POINT ({len(entry)}):")
    for e in entry:
        print(f"  ✅ {e}")
    print()

    print(f"MODULI ATTIVI ({len(attivi)}):")
    for rel, callers in attivi:
        caller_str = ", ".join(callers) if callers else "(esportato da __init__)"
        print(f"  ✅ {rel}")
        print(f"      ← importato da: {caller_str}")
    print()

    print(f"TOOL / SCRIPT STANDALONE ({len(tool)}):")
    for t in tool:
        print(f"  🔧 {t}")
    print()

    if sospetti:
        print(f"⚠️  SOSPETTI MORTI ({len(sospetti)}):")
        for s in sospetti:
            print(f"  ❓ {s}")
        print()
        print("Azione: verificare manualmente se sono davvero inutili.")
        print("Se sì: cancellare o spostare in bgy_data/bgy_archive/.")
    else:
        print("✅ Nessuno script sospetto morto.")
    print()

    print("─" * 78)
    print("LEGENDA:")
    print("  ✅ ENTRY POINT     = avviato da .bat o processo (mai importato)")
    print("  ✅ MODULI ATTIVI   = importato da almeno un altro modulo")
    print("  🔧 TOOL            = ha un main ma non è importato (lanciato a mano)")
    print("  ❓ SOSPETTO MORTO  = né importato, né tool: possibile codice morto")
    print()


if __name__ == "__main__":
    main()