"""
bgy_tools/update_aircraft_brightdata.py
Arricchisce aircraft_icao24_db con l'anno di costruzione (built) tramite Bright Data + Planespotters.net.
v1.3 - Timeout esteso a 30 minuti e gestione della scadenza del job.

Uso:
    py -3.12 -m bgy_tools.update_aircraft_brightdata            # dry-run su 3 aerei
    py -3.12 -m bgy_tools.update_aircraft_brightdata --apply     # applica su tutti gli aerei senza anno
"""
import os
import sys
import time
import re
import requests

sys.path.insert(0, os.getcwd())
from bgy_core import bgy_db

API_TOKEN = "4c68f213-be7c-484d-aa45-6ddd96d37d74"
COLLECTOR_ID = "c_mwi5b2kb2njpk402ae"
TRIGGER_URL = f"https://api.brightdata.com/dca/trigger?collector={COLLECTOR_ID}&queue_next=1"
DATASET_URL = "https://api.brightdata.com/dca/dataset"

CURRENT_YEAR = 2026


def _estrai_anno_da_eta(eta_str):
    if not eta_str or eta_str == 'N/D':
        return None
    try:
        m = re.search(r'([0-9]+(?:\.[0-9]+)?)', str(eta_str))
        if m:
            anni = float(m.group(1))
            return CURRENT_YEAR - int(anni)
    except (ValueError, AttributeError):
        pass
    return None


def _carica_icao_senza_anno(limit=None):
    sql = (
        "SELECT icao24 FROM aircraft_icao24_db "
        "WHERE (built IS NULL OR built = 0) "
        "AND icao24 IS NOT NULL "
        "AND LEFT(icao24, 1) != 'a' "
        "ORDER BY icao24"
    )
    if limit:
        sql += " LIMIT " + str(int(limit))
    ok, rows = bgy_db.execute_query(sql)
    return [r[0] for r in rows] if ok else []


def _trigger_brightdata(lista_icao):
    inputs = [{"url": f"https://www.planespotters.net/hex/{icao}"} for icao in lista_icao]
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
    }
    print(f"Invio {len(inputs)} richieste a Bright Data...")
    try:
        r = requests.post(TRIGGER_URL, headers=headers, json=inputs, timeout=60)
        r.raise_for_status()
        data = r.json()
        collection_id = data.get("collection_id") or data.get("snapshot_id")
        if collection_id:
            print(f"✅ Richiesta accettata. Collection ID: {collection_id}")
            return collection_id
        else:
            print(f"⚠️ Risposta inattesa: {data}")
            return None
    except Exception as e:
        print(f"❌ Errore trigger: {e}")
        return None


def _attendi_e_scarica(collection_id, timeout_min=30):
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    params = {"id": collection_id}

    print(f"Attendo i risultati (max {timeout_min} minuti)...")
    print("Se il job impiega troppo, potrebbe scadere: in quel caso rilancia lo script.")
    start = time.time()
    last_status = None
    
    while time.time() - start < timeout_min * 60:
        try:
            r = requests.get(DATASET_URL, headers=headers, params=params, timeout=60)
            
            if r.status_code == 200:
                try:
                    data = r.json()
                    if isinstance(data, list) and len(data) > 0:
                        print(f"\n✅ Dataset pronto! {len(data)} record ricevuti.")
                        return data
                    elif isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
                        print(f"\n✅ Dataset pronto! {len(data['data'])} record ricevuti.")
                        return data['data']
                    elif data == [] or (isinstance(data, dict) and not data):
                        print(f"\n❌ Job scaduto o vuoto (risposta vuota). Rilancia lo script.")
                        return None
                except ValueError:
                    # Risposta vuota (testo vuoto) -> job scaduto
                    if not r.text.strip():
                        print(f"\n❌ Job scaduto (risposta vuota). Rilancia lo script.")
                        return None
                    print(f"\n⚠️ Risposta non JSON: {r.text[:200]}")
                    return None
            
            elif r.status_code == 202:
                pass  # In elaborazione
            
            elif r.status_code == 404:
                print(f"\n❌ Job non trovato (scaduto o ID errato). Rilancia lo script.")
                return None
            
            elif r.status_code != last_status:
                print(f"\n⚠️ HTTP {r.status_code}: {r.text[:100]}")
                last_status = r.status_code
                
        except Exception as e:
            err_str = str(e)
            if err_str != last_status:
                print(f"\n⚠️ Errore polling: {err_str}")
                last_status = err_str

        print(".", end="", flush=True)
        time.sleep(15)  # Polling ogni 15 secondi

    print(f"\n❌ Timeout dopo {timeout_min} minuti. Bright Data non ha completato il job.")
    return None


def main():
    apply = "--apply" in sys.argv
    limit = None
    for i, a in enumerate(sys.argv):
        if a == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    if not apply:
        limit = limit or 3

    icao_list = _carica_icao_senza_anno(limit)
    print("\n" + "=" * 70)
    print("ARRICCHIMENTO BRIGHT DATA (Planespotters) — " + ("APPLY" if apply else "DRY-RUN"))
    print("=" * 70)
    print(f"icao24 senza anno da processare: {len(icao_list)}")

    if not icao_list:
        print("Nessun aereo da arricchire.")
        return

    collection_id = _trigger_brightdata(icao_list)
    if not collection_id:
        return

    risultati = _attendi_e_scarica(collection_id)
    if not risultati:
        return

    trovati = 0
    aggiornati = 0
    errori = 0

    for rec in risultati:
        icao_orig = None
        for key in ['icao24', 'hex', 'icao', 'input_url', 'url']:
            if key in rec:
                val = str(rec[key])
                if val.startswith('http'):
                    icao_orig = val.rstrip('/').split('/')[-1]
                else:
                    icao_orig = val
                break

        if not icao_orig:
            errori += 1
            continue

        eta = rec.get('built') or rec.get('age') or rec.get('Age')
        anno = _estrai_anno_da_eta(eta)

        if anno:
            trovati += 1
            print(f"  {icao_orig}: età='{eta}' -> anno {anno}")
            if apply:
                bgy_db.execute_query(
                    "UPDATE aircraft_icao24_db SET built = %s WHERE icao24 = %s",
                    (anno, icao_orig), fetch=False
                )
                bgy_db.execute_query(
                    """INSERT INTO aircraft_hexdb (icao24, built, source, fetched_at)
                       VALUES (%s, %s, 'brightdata', NOW())
                       ON CONFLICT (icao24) DO UPDATE SET built = EXCLUDED.built, source = 'brightdata', fetched_at = NOW()""",
                    (icao_orig, anno), fetch=False
                )
                aggiornati += 1
        else:
            errori += 1
            print(f"  {icao_orig}: nessun anno trovato (record: {rec})")

    print("\n" + "=" * 70)
    print(f"Record processati: {len(risultati)}")
    print(f"Con anno di costruzione: {trovati}")
    print(f"Aggiornati nel DB: {aggiornati}")
    print(f"Senza anno / errori: {errori}")
    if not apply:
        print("\nDRY-RUN: nessuna modifica al DB. Rilancia con --apply per applicare.")
    print("=" * 70)


if __name__ == "__main__":
    main()