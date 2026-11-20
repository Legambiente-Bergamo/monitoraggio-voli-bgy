"""
_quarantine_script.py - Sposta i file spuri in _quarantena/YYYY-MM-DD/.
"""
import os
import json
import shutil
from datetime import datetime

SPURIOUS_PATTERNS = [
    ".bak",
    ".bak_",
    ".bak_tmp",
    ".CORROTTO_",
    ".patched",
    ".avionio_ok",
    ".criterio_b_v2_ok",
    ".cross_source_ok",
]

EXACT_NAMES = {
    "confronto_avionio_sacbo.csv",
    "context_2026-10-07.txt",
    "migrate_2026-10-02.py",
    "patch_h24_scheduled.py",
    "report_h24_2026-10-17_OLD.csv",
    "report_h24_2026-10-21_AVIONIO.csv",
    "report_h24_2026-10-21_SOLO_A.csv",
}

EXCLUDE_DIRS = {
    "__pycache__", ".git", ".venv", "venv",
    "node_modules", "bgy_tests",
    "_quarantena",
}

def is_spurious(filename):
    if filename in EXACT_NAMES:
        return True
    lower = filename.lower()
    for pat in SPURIOUS_PATTERNS:
        if pat.lower() in lower:
            return True
    return False

def find_spurious(root="."):
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fname in filenames:
            if is_spurious(fname):
                full = os.path.join(dirpath, fname)
                try:
                    size = os.path.getsize(full)
                    mtime = datetime.fromtimestamp(os.path.getmtime(full)).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    size = 0
                    mtime = "?"
                found.append({"path": full, "size": size, "mtime": mtime})
    return found

def format_size(n):
    if n < 1024:
        return f"{n} B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    else:
        return f"{n / (1024 * 1024):.1f} MB"

def preview(items):
    if not items:
        print("Nessun file spurio trovato.")
        return
    total_size = sum(i["size"] for i in items)
    print(f"\nTrovati {len(items)} file spuri (totale {format_size(total_size)}):\n")
    print(f"{'Dimensione':<12} {'Data modifica':<18} {'File'}")
    print("-" * 90)
    for i in sorted(items, key=lambda x: -x["size"]):
        print(f"{format_size(i['size']):<12} {i['mtime']:<18} {i['path']}")

def do_quarantine(items, dry_run=True):
    if not items:
        return
    date_str = datetime.now().strftime("%Y-%m-%d")
    quarantine_root = os.path.join("_quarantena", date_str)
    os.makedirs(quarantine_root, exist_ok=True)
    manifest = {
        "created_at": datetime.now().isoformat(),
        "date": date_str,
        "n_files": len(items),
        "total_size_bytes": sum(i["size"] for i in items),
        "files": [],
    }
    for i in items:
        src = i["path"]
        rel = os.path.relpath(src, ".")
        dst = os.path.join(quarantine_root, rel)
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        if dry_run:
            print(f"[DRY RUN] Sposterei: {src} -> {dst}")
        else:
            try:
                shutil.move(src, dst)
                print(f"OK Spostato: {src} -> {dst}")
                manifest["files"].append({
                    "original_path": src,
                    "quarantine_path": dst,
                    "size": i["size"],
                    "mtime": i["mtime"],
                })
            except Exception as e:
                print(f"ERRORE spostando {src}: {e}")
    if not dry_run:
        manifest_path = os.path.join(quarantine_root, "_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        print(f"\nManifest salvato: {manifest_path}")

def do_restore(quarantine_date):
    quarantine_root = os.path.join("_quarantena", quarantine_date)
    manifest_path = os.path.join(quarantine_root, "_manifest.json")
    if not os.path.exists(manifest_path):
        print(f"ERRORE: manifest non trovato: {manifest_path}")
        return
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    for entry in manifest["files"]:
        src = entry["quarantine_path"]
        dst = entry["original_path"]
        if os.path.exists(src):
            try:
                os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
                shutil.move(src, dst)
                print(f"OK Ripristinato: {src} -> {dst}")
            except Exception as e:
                print(f"ERRORE ripristinando {src}: {e}")
        else:
            print(f"Gia' rimosso: {src}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "--move":
            items = find_spurious()
            preview(items)
            if items:
                print(f"\nSpostamento in _quarantena/ in corso...")
                do_quarantine(items, dry_run=False)
        elif sys.argv[1] == "--restore" and len(sys.argv) > 2:
            do_restore(sys.argv[2])
        else:
            print("Uso:")
            print("  python _quarantine_script.py            # anteprima (dry-run)")
            print("  python _quarantine_script.py --move     # sposta in _quarantena/")
            print("  python _quarantine_script.py --restore YYYY-MM-DD")
    else:
        items = find_spurious()
        preview(items)
        if items:
            print(f"\nPer spostare i file in _quarantena/:")
            print(f"  python _quarantine_script.py --move")