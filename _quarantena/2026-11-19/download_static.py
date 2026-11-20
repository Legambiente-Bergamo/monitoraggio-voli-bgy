import requests
import os

url = "https://csvbase.com/knastweib/aircraftDatabase.csv"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
print(f"Tentativo di download da: {url}")

r = requests.get(url, headers=headers)
print(f"Status HTTP: {r.status_code}")

if r.status_code == 200:
    # Verifichiamo se è davvero un CSV o una pagina HTML
    content_start = r.text[:100].strip()
    if content_start.startswith("<"):
        print("ERRORE: Il server ha restituito una pagina HTML, non un CSV.")
        print(f"Anteprima: {content_start}")
    else:
        os.makedirs("bgy_data/bgy_assets", exist_ok=True)
        path = "bgy_data/bgy_assets/aircraftDatabase_static.csv"
        with open(path, "wb") as f:
            f.write(r.content)
        size_mb = len(r.content) / (1024 * 1024)
        print(f"✅ File scaricato correttamente: {path} ({size_mb:.1f} MB)")
else:
    print(f"ERRORE HTTP: {r.status_code}")
    print(f"Risposta: {r.text[:200]}")