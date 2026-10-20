"""
bgy_tools/qa_igiene.py - Controllo di igiene sui file Python.
Versione 1.0.3

Novita v1.0.3 (QA-05, 20/10/2026):
- Fix falso positivo sul conteggio __main__: le stringhe di ricerca
  sono costruite a runtime per non trovare sé stesse.

Novita v1.0.2 (QA-05, 20/10/2026):
- Fix lettura file con BOM (utf-8-sig).
- Fix duplicati: controlla solo le def a livello di modulo (ignora i metodi).

Uso:
    py -3.12 -m bgy_tools.qa_igiene
"""
import os
import ast
import sys
from collections import Counter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IGNORE_DIRS = {'__pycache__', '.git', '.venv', 'venv', 'env', 'bgy_tests', 'bgy_data'}

def check_file(filepath):
    problems = []
    
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            content = f.read()
    except Exception as e:
        return [f"Errore lettura file: {e}"]

    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError as e:
        problems.append(f"Errore di sintassi alla riga {e.lineno}: {e.msg}")
        return problems

    # Conteggio triple quote
    triple_quote = chr(34) * 3
    n_triple = content.count(triple_quote)
    if n_triple % 2 != 0:
        problems.append(f"Numero dispari di triple quote ({n_triple}). File troncato?")

    # Conteggio blocchi __main__ (stringhe costruite a runtime per non autotrovarsi)
    m1 = "if __name__" + " == '__main__':"
    m2 = 'if __name__' + ' == "__main__":'
    main_count = content.count(m1) + content.count(m2)
    
    if main_count > 1:
        problems.append(f"Trovati {main_count} blocchi __main__ (atteso 1 o 0).")

    # Definizioni duplicate (solo a livello di modulo)
    definitions = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions.append(node.name)
    
    counts = Counter(definitions)
    duplicates = [name for name, count in counts.items() if count > 1]
    if duplicates:
        problems.append(f"Definizioni duplicate a livello di modulo: {', '.join(duplicates)}")

    return problems

def main():
    print("=== CONTROLLO IGIENE FILE PYTHON (QA-05) ===\n")
    total_files = 0
    total_problems = 0

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for file in files:
            if not file.endswith(".py") or file.startswith("_tmp_"):
                continue
            total_files += 1
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, PROJECT_ROOT)
            problems = check_file(filepath)
            if problems:
                total_problems += 1
                print(f"❌ {rel_path}")
                for p in problems:
                    print(f"   - {p}")

    print("\n" + "=" * 40)
    if total_problems == 0:
        print(f"✅ Tutti i {total_files} file sono in ordine. Nessun problema rilevato.")
        sys.exit(0)
    else:
        print(f"⚠️  Trovati problemi in {total_problems} file su {total_files} scansionati.")
        sys.exit(1)

if __name__ == "__main__":
    main()