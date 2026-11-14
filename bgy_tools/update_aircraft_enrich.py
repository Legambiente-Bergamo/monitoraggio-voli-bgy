"""
bgy_tools/update_aircraft_enrich.py
Arricchisce aircraft_icao24_db con modello/operatore/registrazione.
Fonte primaria: HexDB API v2 (gratuita, no key).
Fallback: Mictronics (archivio ZIP settimanale).

Uso:
    py -3.12 -m bgy_tools.update_aircraft_enrich                # dry-run
    py -3.12 -m bgy_tools.update_aircraft_enrich --apply
    py -3.12 -m bgy_tools.update_aircraft_enrich --limit 20
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
from bgy_tools.normalize_icao24_models import normalize

HEXDB_URL = "https://hexdb.io/api/v2/aircraft/{icao24}"
MICTRONICS_ZIP = "https://github.com/Mictronics/aircraft-database/raw/refs/heads/main/indexedDB.zip"
DELAY_SEC = 0.15

TYPECODE_MAP = {
    "A19N": "Airbus A319-100", "A320": "Airbus A320-200", "A321": "Airbus A321-200",
    "A20N": "Airbus A320neo", "A21N": "Airbus A321neo",
    "A332": "Airbus A330-200", "A333": "Airbus A330-300", "A339": "Airbus A330-900neo",
    "A359": "Airbus A350-900", "A35K": "Airbus A350-1000",
    "A388": "Airbus A380-800", "A306": "Airbus A300-600F", "A30B": "Airbus A300-600F",
    "B738": "Boeing 737-800", "B739": "Boeing 737-800", "B737": "Boeing 737-800",
    "B38M": "Boeing 737 MAX 8-200", "B39M": "Boeing 737 MAX 8-200",
    "B752": "Boeing 757-200", "B753": "Boeing 757-200",
    "B763": "Boeing 767-300", "B764": "Boeing 767-400", "B76F": "Boeing 767-300F",
    "B772": "Boeing 777-200", "B773": "Boeing 777-300ER", "B77W": "Boeing 777-300ER",
    "B77L": "Boeing 777-200", "B778": "Boeing 777-300ER", "B779": "Boeing 777-300ER",
    "B77F": "Boeing 777F", "B788": "Boeing 787-8", "B789": "Boeing 787-9", "B78X": "Boeing 787-10",
    "B744": "Boeing 747-400", "B748": "Boeing 747-8F",
    "E170": "Embraer E170", "E175": "Embraer E175", "E190": "Embraer ERJ-190",
    "E195": "Embraer E195", "E290": "Embraer ERJ-190", "E295": "Embraer E195", "E145": "Embraer ERJ-145",
    "E55P": "Embraer Phenom 300", "E50P": "Embraer Phenom 100",
    "AT72": "ATR 72-600", "AT45": "ATR 42-500", "AT46": "ATR 42-500",
    "DH8D": "De Havilland Canada Dash 8-400", "DH8C": "De Havilland Canada Dash 8-400",
    "SF34": "Saab 340", "F100": "Fokker 100",
    "CRJ9": "Bombardier Challenger 600", "CRJ2": "Bombardier Challenger 600", "CRJ7": "Bombardier Challenger 600",
    "CL30": "Bombardier Challenger 300", "CL35": "Bombardier Challenger 300", "CL60": "Bombardier Challenger 600",
    "GLF4": "Gulfstream IV", "GLF5": "Gulfstream G550", "GLF6": "Gulfstream G650", "GL7T": "Gulfstream G650",
    "C25A": "Cessna Citation CJ2+", "C25B": "Cessna Citation CJ2+", "C25C": "Cessna Citation CJ2+", "C25M": "Cessna Citation CJ2+",
    "C56X": "Cessna Citation XLS+", "C550": "Cessna Citation XLS+", "C510": "Cessna Citation Mustang",
    "C680": "Cessna Citation (generico)", "C68A": "Cessna Citation (generico)", "C525": "Cessna Citation CJ2+",
    "LJ45": "Learjet 45", "LJ40": "Learjet 45", "LJ60": "Learjet 45",
    "FA7X": "Dassault Falcon 7X/8X", "FA8X": "Dassault Falcon 7X/8X",
    "F2TH": "Dassault Falcon 2000", "F900": "Dassault Falcon 900", "F50": "Dassault Falcon 50",
    "H25B": "Hawker 800/900XP", "H25C": "Hawker 800/900XP",
    "PC12": "Pilatus PC-12", "PC24": "Pilatus PC-24",
    "EC35": "Elicottero", "EC45": "Elicottero", "H145": "Elicottero", "H125": "Elicottero", "A109": "Elicottero", "AS50": "Elicottero",
}


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
            return None
        d = r.json()
        if not d or not isinstance(d, dict):
            return None
        return {
            "registration": d.get("registration"),
            "typecode": d.get("icao_type_code"),
            "model_raw": d.get("type"),
            "manufacturer": d.get("manufacturer"),
            "operator": d.get("registered_owner"),
            "source": "hexdb"
        }
    except Exception:
        return None


def _download_mictronics():
    try:
        r = requests.get(MICTRONICS_ZIP, timeout=120)
        r.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        with zf.open("aircrafts.json") as f:
            aircrafts = json.load(f)
        with zf.open("types.json") as f:
            types = json.load(f)
    except Exception as e:
        print("  Mictronics download/parsing fallito: " + str(e))
        return {}, {}
    # Fix: chiavi in minuscolo
    aircrafts_lower = {k.lower(): v for k, v in aircrafts.items()}
    return aircrafts_lower, types


def _resolve_model(typecode, model_raw):
    if typecode and typecode.upper() in TYPECODE_MAP:
        return TYPECODE_MAP[typecode.upper()], "typecode"
    if model_raw:
        canon = normalize(model_raw)
        if canon not in ("Aviazione generale (generico)", "N/D"):
            return canon, "normalize"
    return None, None


def _save_record(icao24, rec):
    bgy_db.execute_query(
        "INSERT INTO aircraft_hexdb "
        "(icao24, registration, typecode, model, manufacturer, operator, source, fetched_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) "
        "ON CONFLICT (icao24) DO UPDATE SET "
        "registration = EXCLUDED.registration, typecode = EXCLUDED.typecode, "
        "model = EXCLUDED.model, manufacturer = EXCLUDED.manufacturer, "
        "operator = EXCLUDED.operator, source = EXCLUDED.source, fetched_at = NOW()",
        (icao24, rec.get("registration"), rec.get("typecode"), rec.get("model_raw"),
         rec.get("manufacturer"), rec.get("operator"), rec.get("source")), fetch=False
    )
    bgy_db.execute_query(
        "UPDATE aircraft_icao24_db SET "
        "model = %s, "
        "operator = COALESCE(operator, %s), "
        "registration = COALESCE(registration, %s), "
        "typecode = COALESCE(typecode, %s) "
        "WHERE icao24 = %s",
        (rec["model_canon"], rec.get("operator"), rec.get("registration"),
         rec.get("typecode"), icao24), fetch=False
    )


def main():
    apply = "--apply" in sys.argv
    limit = None
    for i, a in enumerate(sys.argv):
        if a == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    icao_list = _load_icao24_senza_modello(limit)
    print("\n" + "=" * 70)
    print("ARRICCHIMENTO AEREI (HexDB v2 + Mictronics) — " + ("APPLY" if apply else "DRY-RUN"))
    print("=" * 70)
    print("icao24 senza modello: " + str(len(icao_list)))
    if not icao_list:
        return

    hits_hexdb = 0
    misses_hexdb = []

    # 1. HexDB
    print("\n[1/2] HexDB v2...")
    for i, icao in enumerate(icao_list, 1):
        rec = _hexdb_lookup(icao)
        if rec:
            canon, how = _resolve_model(rec["typecode"], rec["model_raw"])
            if canon:
                hits_hexdb += 1
                print("  " + icao + "  " + str(rec["typecode"]).ljust(6) + "  " + canon.ljust(32) + " (hexdb-" + how + ")")
                if apply:
                    rec["model_canon"] = canon
                    _save_record(icao, rec)
            else:
                misses_hexdb.append(icao)
        else:
            misses_hexdb.append(icao)
        time.sleep(DELAY_SEC)

    print("\nHexDB: " + str(hits_hexdb) + " arricchiti, " + str(len(misses_hexdb)) + " passano a Mictronics")

    # 2. Mictronics
    if misses_hexdb:
        print("\n[2/2] Mictronics...")
        aircrafts, types = _download_mictronics()
        hits_mic = 0
        for icao in misses_hexdb:
            vals = aircrafts.get(icao.lower())
            if not vals or not isinstance(vals, list) or len(vals) < 2:
                continue
            reg = vals[0]
            td = vals[1]
            type_info = types.get(td) if isinstance(types, dict) else None
            model_raw = type_info[0] if isinstance(type_info, list) and type_info else None
            canon, how = _resolve_model(td, model_raw)
            if canon:
                hits_mic += 1
                print("  " + icao + "  " + str(td).ljust(6) + "  " + canon.ljust(32) + " (mic-" + how + ")")
                if apply:
                    _save_record(icao, {
                        "registration": reg, "typecode": td, "model_raw": model_raw,
                        "manufacturer": None, "operator": None, "source": "mictronics",
                        "model_canon": canon
                    })
        print("\nMictronics: " + str(hits_mic) + " arricchiti")

    if not apply:
        print("\nDRY-RUN: nessuna modifica. Rilancia con --apply.")
    else:
        print("\nApplicato. Verifica con:")
        print("  SELECT model, COUNT(*) FROM aircraft_icao24_db WHERE model NOT IN ('N/D','') GROUP BY model ORDER BY COUNT(*) DESC LIMIT 15;")


if __name__ == "__main__":
    main()