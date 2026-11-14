"""
bgy_tools/update_aircraft_hexdb.py
Arricchisce aircraft_icao24_db con modello/operatore/registrazione via HexDB,
con fallback su Mictronics.

Uso:
    py -3.12 -m bgy_tools.update_aircraft_hexdb                # dry-run
    py -3.12 -m bgy_tools.update_aircraft_hexdb --apply
    py -3.12 -m bgy_tools.update_aircraft_hexdb --limit 20
"""
import os
import sys
import json
import time
import zipfile
import io
import requests

sys.path.insert(0, os.getcwd())
from bgy_core import bgy_db

HEXDB_URL = "https://hexdb.io/api/v1/aircraft/icao/{icao24}"
MICTRONICS_ZIP = "https://github.com/Mictronics/aircraft-database/raw/refs/heads/main/indexedDB.zip"
DELAY_SEC = 0.15


def _load_icao24_senza_modello(limit=None):
    sql = (
        "SELECT icao24 FROM aircraft_icao24_db "
        "WHERE (model IS NULL OR TRIM(model) = '' OR model = 'N/D') "
        "AND icao24 IS NOT NULL ORDER BY icao24"
    )
    if limit:
        sql += " LIMIT " + str(int(limit))
    ok, rows = bgy_db.execute_query(sql)
    return [r[0] for r in rows] if ok else []


def _hexdb_lookup(icao24):
    try:
        r = requests.get(
            HEXDB_URL.format(icao24=icao24), timeout=10,
            headers={"User-Agent": "BGY-Monitoring-Suite/3.9 (info@legambientebergamo.it)"}
        )
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            print("  HexDB HTTP " + str(r.status_code) + " per " + icao24)
            return None
        d = r.json()
        if not d or not isinstance(d, dict):
            return None
        return {
            "registration": d.get("Registration") or d.get("registration"),
            "typecode": d.get("ICAOTypeCode") or d.get("icao_type_code"),
            "model": d.get("Type") or d.get("type"),
            "manufacturer": d.get("Manufacturer") or d.get("manufacturer"),
            "operator": d.get("RegisteredOwners") or d.get("operator"),
            "built": None,
            "source": "hexdb",
        }
    except Exception as e:
        print("  HexDB errore " + icao24 + ": " + str(e))
        return None


def _download_mictronics():
    print("Scarico Mictronics...")
    try:
        r = requests.get(MICTRONICS_ZIP, timeout=120)
        r.raise_for_status()
    except Exception as e:
        print("  Mictronics download fallito: " + str(e))
        return {}
    try:
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        with zf.open("aircrafts.json") as f:
            aircrafts = json.load(f)
        with zf.open("types.json") as f:
            types = json.load(f)
    except Exception as e:
        print("  Mictronics parsing fallito: " + str(e))
        return {}
    idx = {}
    for icao, vals in aircrafts.items():
        if not isinstance(vals, list) or len(vals) < 2:
            continue
        reg = vals[0]
        td = vals[1]
        type_info = types.get(td) if isinstance(types, dict) else None
        model = type_info[0] if isinstance(type_info, list) and type_info else None
        idx[icao.lower()] = {
            "registration": reg, "typecode": td, "model": model,
            "manufacturer": None, "operator": None, "built": None,
            "source": "mictronics",
        }
    print("  Mictronics: " + str(len(idx)) + " icao24 indicizzati")
    return idx


def _upsert_hexdb(icao24, rec):
    sql = (
        "INSERT INTO aircraft_hexdb "
        "(icao24, registration, typecode, model, manufacturer, operator, built, source, fetched_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW()) "
        "ON CONFLICT (icao24) DO UPDATE SET "
        "registration = EXCLUDED.registration, typecode = EXCLUDED.typecode, "
        "model = EXCLUDED.model, manufacturer = EXCLUDED.manufacturer, "
        "operator = EXCLUDED.operator, built = EXCLUDED.built, "
        "source = EXCLUDED.source, fetched_at = NOW()"
    )
    return bgy_db.execute_query(sql, (
        icao24, rec.get("registration"), rec.get("typecode"), rec.get("model"),
        rec.get("manufacturer"), rec.get("operator"), rec.get("built"), rec.get("source")
    ), fetch=False)


def _update_aircraft_icao24(icao24, rec):
    sets = []
    vals = []
    if rec.get("model"):
        sets.append("model = %s"); vals.append(rec["model"])
    if rec.get("operator"):
        sets.append("operator = COALESCE(operator, %s)"); vals.append(rec["operator"])
    if rec.get("registration"):
        sets.append("registration = COALESCE(registration, %s)"); vals.append(rec["registration"])
    if rec.get("typecode"):
        sets.append("typecode = COALESCE(typecode, %s)"); vals.append(rec["typecode"])
    if rec.get("built"):
        sets.append("built = COALESCE(built, %s)"); vals.append(rec["built"])
    if not sets:
        return True, 0
    vals.append(icao24)
    sql = "UPDATE aircraft_icao24_db SET " + ", ".join(sets) + " WHERE icao24 = %s"
    return bgy_db.execute_query(sql, tuple(vals), fetch=False)


def main():
    apply = '--apply' in sys.argv
    limit = None
    for i, a in enumerate(sys.argv):
        if a == '--limit' and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    icao_list = _load_icao24_senza_modello(limit)
    print("\n" + "=" * 70)
    print("ARRICCHIMENTO HEXDB/MICTRONICS — " + ("APPLY" if apply else "DRY-RUN"))
    print("=" * 70)
    print("icao24 senza modello: " + str(len(icao_list)))
    if not icao_list:
        return

    hexdb_hits = 0
    mictronics_needed = []
    for i, icao in enumerate(icao_list, 1):
        rec = _hexdb_lookup(icao)
        if rec and rec.get("model"):
            hexdb_hits += 1
            print("  [" + str(i) + "/" + str(len(icao_list)) + "] " + icao + " -> " + str(rec.get("model")))
            if apply:
                _upsert_hexdb(icao, rec)
                _update_aircraft_icao24(icao, rec)
        else:
            mictronics_needed.append(icao)
        time.sleep(DELAY_SEC)

    print("\nHexDB: " + str(hexdb_hits) + " arricchiti, " + str(len(mictronics_needed)) + " da provare su Mictronics")

    if mictronics_needed:
        mic = _download_mictronics()
        mic_hits = 0
        for icao in mictronics_needed:
            rec = mic.get(icao.lower())
            if rec and rec.get("model"):
                mic_hits += 1
                print("  [MIC] " + icao + " -> " + str(rec.get("model")))
                if apply:
                    _upsert_hexdb(icao, rec)
                    _update_aircraft_icao24(icao, rec)
        print("Mictronics: " + str(mic_hits) + " arricchiti")
    else:
        print("Mictronics: non necessario")

    if not apply:
        print("\nDRY-RUN: nessuna modifica. Rilancia con --apply.")
    else:
        print("\nApplicato. Verifica: SELECT source, COUNT(*) FROM aircraft_hexdb GROUP BY source;")


if __name__ == '__main__':
    main()