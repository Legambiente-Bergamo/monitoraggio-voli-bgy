import subprocess
import sys

def run_cmd(cmd):
    print(f"Esecuzione: {cmd}")
    result = subprocess.run(cmd, shell=True, text=True)
    if result.returncode != 0:
        print(f"Errore nell'esecuzione del comando: {cmd}")
        sys.exit(1)

def main():
    if len(sys.argv) > 1:
        commit_msg = " ".join(sys.argv[1:])
    else:
        commit_msg = input("Inserisci il messaggio di commit: ").strip()
        if not commit_msg:
            print("Il messaggio di commit non può essere vuoto.")
            sys.exit(1)

    print("\n1. Rigenerazione hash (QA-06)...")
    run_cmd("py -3.12 bgy_tools/qa_hashes.py")

    print("\n2. Aggiunta file modificati...")
    run_cmd("git add .")

    print(f"\n3. Creazione del commit...")
    safe_msg = commit_msg.replace('"', '\\"')
    run_cmd(f'git commit -m "{safe_msg}"')

    print("\n4. Push su GitHub...")
    run_cmd("git push origin main")

    print("\nTutto completato con successo!")

if __name__ == "__main__":
    main()