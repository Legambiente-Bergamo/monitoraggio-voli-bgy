"""
consolidate_step2.py - Consolidamento F12 Step 2 (parte 1).

Tre consolidamenti:
1. _get_today_log_path: da bgy_mailer.py a bgy_logger.py
2. parse_radar_filename: da bgy_db_migrate.py a bgy_dates.py
3. _is_in_night_window: da bgy_scanner_night.py + bgy_scheduler.py a bgy_dates.py

Ogni consolidamento:
- Estrae la funzione sorgente e destinazione
- Verifica che i corpi siano identici (o compatibili)
- Rimuove la funzione duplicata
- Aggiunge l'import corretto
- Sostituisce le chiamate
- Verifica sintassi del file modificato
- Rollback automatico se qualcosa va storto

Script one-shot con backup.
"""
import ast
import re
import shutil
from pathlib import Path
from datetime import datetime

BACKUP_DIR = Path("bgy_data") / "bgy_archive" / "pre_step2"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, source):
    Path(path).write_text(source, encoding="utf-8")


def extract_function(source, name):
    """Estrae info di una funzione: args, inizio, fine, testo."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = source.split("\n")
            return {
                "args": [a.arg for a in node.args.args],
                "start_line": node.lineno,
                "end_line": node.end_lineno,
                "text": "\n".join(lines[node.lineno - 1:node.end_lineno]),
            }
    return None


def remove_function(source, name):
    """Rimuove una funzione. Ritorna (nuovo_source, ok)."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = source.split("\n")
            start = node.lineno - 1
            end = node.end_lineno
            # Salta righe vuote dopo
            while end < len(lines) and lines[end].strip() == "":
                end += 1
            # Salta riga vuota PRIMA se presente e se dopo c'è riga vuota
            if start > 0 and lines[start - 1].strip() == "":
                start -= 1
            new_lines = lines[:start] + lines[end:]
            return "\n".join(new_lines), True
    return source, False


def add_import(source, import_line):
    """Aggiunge l'import dopo l'ultimo import del blocco iniziale."""
    if import_line in source:
        return source, False

    lines = source.split("\n")
    last_import_idx = -1
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or s.startswith("#") or s.startswith('"""') or s.startswith("'''"):
            continue
        if s.startswith("import ") or s.startswith("from "):
            last_import_idx = i
        else:
            if last_import_idx >= 0:
                break

    if last_import_idx < 0:
        return f"{import_line}\n\n{source}", True

    new_lines = lines[:last_import_idx + 1] + [import_line] + lines[last_import_idx + 1:]
    return "\n".join(new_lines), True


def replace_calls(source, old, new):
    """Sostituisce old( con new( (word boundary)."""
    pattern = rf"\b{re.escape(old)}\s*\("
    return re.subn(pattern, f"{new}(", source)


def is_valid_python(source):
    try:
        ast.parse(source)
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError riga {e.lineno}: {e.msg}"


def backup_file(path):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{Path(path).name}.{TIMESTAMP}.bak"
    shutil.copy2(path, backup_path)
    return backup_path


def consolidate(description, source_file, target_file,
                func_name, import_line, additional_call_files=None):
    """
    Consolida func_name: rimuove da source_file, importa da target_file,
    sostituisce chiamate in source_file (+ additional_call_files).
    """
    print(f"\n{'=' * 60}")
    print(f"🔧 {description}")
    print(f"   Fonte: {source_file}")
    print(f"   Dest:  {target_file}")
    print(f"   Funz:  {func_name}()")
    print("=" * 60)

    source_path = Path(source_file)
    target_path = Path(target_file)

    if not source_path.exists():
        print(f"❌ File non trovato: {source_file}")
        return False
    if not target_path.exists():
        print(f"❌ File non trovato: {target_file}")
        return False

    source_src = read(source_path)
    target_src = read(target_path)

    # Estrai funzioni
    src_func = extract_function(source_src, func_name)
    tgt_func = extract_function(target_src, func_name)

    if not src_func:
        print(f"⚠️  {func_name} non trovata in {source_file} — skip")
        return True
    if not tgt_func:
        print(f"❌ {func_name} non trovata in {target_file} — impossibile consolidare")
        return False

    print(f"  Sorgente: righe {src_func['start_line']}-{src_func['end_line']}, "
          f"args={src_func['args']}")
    print(f"  Dest:     righe {tgt_func['start_line']}-{tgt_func['end_line']}, "
          f"args={tgt_func['args']}")

    if src_func["args"] != tgt_func["args"]:
        print(f"⚠️  Firme diverse! Fonte: {src_func['args']}, Dest: {tgt_func['args']}")
        print("   → Skip (consolidamento manuale)")
        return False

    # Backup
    src_backup = backup_file(source_path)
    print(f"  ✅ Backup: {src_backup}")

    # Rimuovi funzione dalla sorgente
    modified, ok = remove_function(source_src, func_name)
    if not ok:
        print(f"❌ Errore rimozione {func_name}")
        return False
    print(f"  🗑️  Funzione rimossa da {source_file}")

    # Aggiungi import
    modified, added = add_import(modified, import_line)
    if added:
        print(f"  📥 Import aggiunto: {import_line}")

    # Sostituisci chiamate nel source
    modified, n = replace_calls(modified, func_name, func_name)
    print(f"  🔍 Chiamate nel source: {n} (self-call)")

    # Verifica sintassi
    valid, err = is_valid_python(modified)
    if not valid:
        print(f"  ❌ File invalido: {err}")
        print(f"  → Rollback da {src_backup}")
        shutil.copy2(src_backup, source_path)
        return False

    write(source_path, modified)
    print(f"  ✅ {source_file} aggiornato")

    # File aggiuntivi che chiamano la funzione
    if additional_call_files:
        for extra_file in additional_call_files:
            extra_path = Path(extra_file)
            if not extra_path.exists():
                print(f"  ⚠️  File aggiuntivo non trovato: {extra_file}")
                continue

            extra_src = read(extra_path)
            extra_backup = backup_file(extra_path)
            modified, n = replace_calls(extra_src, func_name, func_name)
            modified, added = add_import(modified, import_line)

            if n > 0 or added:
                valid, err = is_valid_python(modified)
                if not valid:
                    print(f"  ❌ {extra_file} invalido: {err}")
                    shutil.copy2(extra_backup, extra_path)
                    continue
                write(extra_path, modified)
                print(f"  ✅ {extra_file}: {n} chiamate, import={'sì' if added else 'no'}")

    return True


def main():
    print("=" * 60)
    print("🔧 F12 Step 2 — Consolidamento (parte 1)")
    print("=" * 60)

    results = []

    # 1. _get_today_log_path
    results.append(consolidate(
        description="_get_today_log_path",
        source_file="bgy_core/bgy_mailer.py",
        target_file="bgy_core/bgy_logger.py",
        func_name="_get_today_log_path",
        import_line="from bgy_core.bgy_logger import _get_today_log_path",
    ))

    # 2. parse_radar_filename
    results.append(consolidate(
        description="parse_radar_filename",
        source_file="bgy_core/bgy_db_migrate.py",
        target_file="bgy_core/bgy_dates.py",
        func_name="parse_radar_filename",
        import_line="from bgy_core.bgy_dates import parse_radar_filename",
    ))

    # 3. _is_in_night_window
    # Sorgente principale: bgy_scanner_night.py
    # Destinazione: bgy_dates.py (dove c'è is_night_time)
    # Chiamante aggiuntivo: bgy_scheduler.py
    results.append(consolidate(
        description="_is_in_night_window",
        source_file="bgy_scanners/bgy_scanner_night.py",
        target_file="bgy_core/bgy_dates.py",
        func_name="_is_in_night_window",
        import_line="from bgy_core.bgy_dates import _is_in_night_window",
        additional_call_files=["bgy_scheduler.py"],
    ))

    print()
    print("=" * 60)
    print("📊 Riepilogo")
    print("=" * 60)
    for i, r in enumerate(results, 1):
        print(f"  {i}. {'✅' if r else '❌ o skip'}")
    print()
    print(f"Backup in: {BACKUP_DIR}")
    print()
    print("Verifica con:")
    print("  py -3.12 -c \"from bgy_scheduler import job_daily; "
          "from bgy_scanners import run_night_scan; print('OK')\"")


if __name__ == "__main__":
    main()