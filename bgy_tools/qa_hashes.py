import os
import hashlib
import json
import sys

def generate_hashes(root_dir="."):
    hashes = {}
    for dirpath, _, filenames in os.walk(root_dir):
        # Escludiamo cartelle non necessarie
        if any(x in dirpath for x in [".git", "__pycache__", "bgy_tests", "bgy_data"]):
            continue
        for f in filenames:
            if f.endswith(".py"):
                filepath = os.path.join(dirpath, f)
                with open(filepath, "rb") as file:
                    file_hash = hashlib.sha256(file.read()).hexdigest()
                rel_path = os.path.relpath(filepath, root_dir).replace("\\", "/")
                hashes[rel_path] = file_hash
    return hashes

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        try:
            with open("bgy_tools/file_hashes.json", "r") as f:
                expected = json.load(f)
        except FileNotFoundError:
            print("Nessun registro hash trovato. Esegui senza --verify per generarlo.")
            sys.exit(1)
            
        current = generate_hashes()
        diff = False
        for k, v in expected.items():
            if current.get(k) != v:
                print(f"❌ Mismatch rilevato: {k}")
                diff = True
        if diff:
            print("\nATTENZIONE: Il codice è stato modificato senza aggiornare gli hash.")
            print("Se la modifica è voluta, rigenera gli hash con: py -3.12 bgy_tools/qa_hashes.py")
            sys.exit(1)
        print("✅ Tutti gli hash corrispondono.")
    else:
        with open("bgy_tools/file_hashes.json", "w", encoding="utf-8") as f:
            json.dump(generate_hashes(), f, indent=2)
        print("✅ Registro hash generato in bgy_tools/file_hashes.json")