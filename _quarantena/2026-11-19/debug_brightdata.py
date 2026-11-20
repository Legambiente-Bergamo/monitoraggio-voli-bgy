import requests
import time

API_TOKEN = "4c68f213-be7c-484d-aa45-6ddd96d37d74"
COLLECTION_ID = "j_mwi6ynh7azpr229vg"  # L'ultimo collection_id generato
DATASET_URL = "https://api.brightdata.com/dca/dataset"

headers = {"Authorization": f"Bearer {API_TOKEN}"}
params = {"id": COLLECTION_ID}

print(f"Interrogo lo stato del job {COLLECTION_ID}...")
for i in range(5):
    r = requests.get(DATASET_URL, headers=headers, params=params, timeout=30)
    print(f"\nTentativo {i+1} - HTTP {r.status_code}")
    print(f"Risposta: {r.text[:500]}")
    if r.status_code == 200:
        print("✅ Dataset pronto!")
        break
    elif r.status_code == 202:
        print("⏳ Ancora in elaborazione...")
    time.sleep(30)  # Aspetta 30 secondi tra i tentativi