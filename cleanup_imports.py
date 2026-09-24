"""
cleanup_imports.py - Rimuove import inutilizzati da 13 file.
Script one-shot con backup e verifica automatica.

Uso:
    py -3.12 cleanup_imports.py

Se un file diventa invalido dopo la modifica, viene automaticamente
ripristinato dal backup.
"""
import ast
import re
import shutil
from pathlib import Path
from datetime import datetime

BACKUP_DIR = Path("bgy_data") / "bgy_archive" / "pre_imports_cleanup"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# =============================================================================
# DEFINIZIONE DELLE MODIFICHE
# =============================================================================
# Ogni voce è (file, tipo_modifica, contenuto)
# - tipo "remove_line": rimuove la riga che matcha il pattern
# - tipo "substitute": sostituisce il pattern con replacement
# - tipo "remove_block": rimuove un blocco multi-riga che matcha il pattern

CHANGES = {
    "bgy_core/bgy_charts.py": [
        ("remove_line", r"^import pandas as pd\s*$", None),
        ("substitute",
         r"^from datetime import datetime, timedelta\s*$",
         "from datetime import timedelta"),
        ("remove_line", r"^from datetime import datetime\s*$", None),
    ],
    "bgy_core/bgy_db.py": [
        ("remove_line", r"^from datetime import datetime\s*$", None),
    ],
    "bgy_core/bgy_export_common.py": [
        ("remove_line", r"^import os\s*$", None),
    ],
    "bgy_core/bgy_github_sync.py": [
        ("remove_line", r"^import sys\s*$", None),
    ],
    "bgy_core/bgy_update_rules.py": [
        ("substitute",
         r"^from datetime import datetime, timedelta\s*$",
         "from datetime import datetime"),
    ],
    "bgy_gui.py": [
        ("remove_line", r"^import json\s*$", None),
    ],
    "bgy_gui/bgy_gui_charts.py": [
        ("substitute",
         r"^from bgy_core\.bgy_update_rules import get_airline, get_country\s*$",
         "from bgy_core.bgy_update_rules import get_airline"),
    ],
    "bgy_gui/bgy_gui_scan_config.py": [
        ("remove_line", r"^import tkinter as tk\s*$", None),
    ],
    "bgy_reports/bgy_report_month.py": [
        ("remove_block",
         r"from bgy_core\.bgy_dates import \(\s*\n"
         r"\s*normalize_date, report_monthly_filename, to_year_month\s*\n"
         r"\s*\)\n",
         ""),
    ],
    "bgy_reports/bgy_report_night.py": [
        ("remove_line", r"^from datetime import datetime, timedelta\s*$", None),
    ],
    "bgy_scheduler.py": [
        ("substitute",
         r"^from bgy_core\.bgy_paths import LOGS_DIR, RAW_DIR, PROJECT_ROOT\s*$",
         "from bgy_core.bgy_paths import LOGS_DIR, RAW_DIR"),
    ],
    "bgy_utils/bgy_utils_assaeroporti.py": [
        ("substitute",
         r"^from datetime import datetime, timedelta\s*$",
         "from datetime import datetime"),
    ],
    "rigenera_e_sync.py": [
        ("remove_line", r"^from pathlib import Path\s*$", None),
    ],
}


def apply_change(source, change_type, pattern, replacement):
    """Applica una singola modifica. Ritorna (nuovo_source, n_applicate)."""
    if change_type == "remove_line":
        lines = source.split("\n")
        result = []
        removed = 0
        for line in lines:
            if re.match(pattern, line):
                removed += 1
                continue
            result.append(line)
        return "\n".join(result), removed

    elif change_type == "substitute":
        new_source, n = re.subn(pattern, replacement, source, flags=re.MULTILINE)
        return new_source, n

    elif change_type == "remove_block":
        new_source, n = re.subn(pattern, replacement, source, flags=re.MULTILINE)
        return new_source, n

    return source, 0


def is_valid_python(source):
    """Verifica che il sorgente sia Python valido."""
    try:
        ast.parse(source)
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError riga {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)


def main():
    root = Path(".")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("🧹 Pulizia import inutilizzati")
    print("=" * 60)
    print(f"Backup dir: {BACKUP_DIR}")
    print()

    total_modified = 0
    total_changes = 0
    total_errors = 0
    files_modified = []

    for rel_path, changes in CHANGES.items():
        p = root / rel_path
        if not p.exists():
            print(f"⚠️  File non trovato: {rel_path}")
            continue

        # Leggi sorgente originale
        try:
            original = p.read_text(encoding="utf-8")
        except Exception as e:
            print(f"❌ {rel_path}: errore lettura ({e})")
            total_errors += 1
            continue

        # Applica tutte le modifiche
        modified = original
        applied = 0
        for change_type, pattern, replacement in changes:
            modified, n = apply_change(modified, change_type, pattern, replacement)
            applied += n

        if applied == 0:
            print(f"⏭️  {rel_path}: nessuna modifica (pattern non trovato)")
            continue

        # Verifica sintassi
        valid, err = is_valid_python(modified)
        if not valid:
            print(f"❌ {rel_path}: file invalido dopo modifica ({err})")
            print(f"   → Modifica annullata")
            total_errors += 1
            continue

        # Backup
        backup_path = BACKUP_DIR / f"{rel_path.replace('/', '_')}.{TIMESTAMP}.bak"
        shutil.copy2(p, backup_path)

        # Scrivi
        try:
            p.write_text(modified, encoding="utf-8")
            print(f"✅ {rel_path}: {applied} modifiche")
            total_modified += 1
            total_changes += applied
            files_modified.append(rel_path)
        except Exception as e:
            print(f"❌ {rel_path}: errore scrittura ({e})")
            total_errors += 1

    print()
    print("=" * 60)
    print("📊 Riepilogo")
    print("=" * 60)
    print(f"File modificati:  {total_modified}")
    print(f"Modifiche totali: {total_changes}")
    print(f"Errori:           {total_errors}")
    print()

    if files_modified:
        print("File modificati:")
        for f in files_modified:
            print(f"  - {f}")
        print()
        print(f"Backup in: {BACKUP_DIR}")

    print()
    print("Prossimo passo: verificare che tutti i moduli si importino:")
    print("  py -3.12 -c \"from bgy_core import load_rules; "
          "from bgy_reports import generate_nightly_report; print('OK')\"")


if __name__ == "__main__":
    main()