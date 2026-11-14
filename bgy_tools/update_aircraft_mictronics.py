"""
bgy_tools/update_aircraft_mictronics.py
Arricchisce aircraft_icao24_db con modello/registrazione/typecode da Mictronics.
HexDB è stato scartato (404 su tutti gli icao24, endpoint non funzionante).

Priorità di mappatura:
  1. TYPECODE_MAP (codice ICAO univoco: A320, B738, B38M, ecc.)
  2. normalize() da normalize_icao24_models.py (fallback su nome lungo)

Uso:
    py -3.12 -m bgy_tools.update_aircraft_mictronics                # dry-run
    py -3.12 -m bgy_tools.update_aircraft_mictronics --apply
    py -3.12 -m bgy_tools.update_aircraft_mictronics --limit 20
"""
import os
import sys
import json
import zipfile
import io
import requests

sys.path.insert(0, os.getcwd())
from bgy_core import bgy_db
from bgy_tools.normalize_icao24_models import normalize

MICTRONICS_ZIP = "https://github.com/Mictronics/aircraft-database/raw/refs/heads/main/indexedDB.zip"

# Mappatura typecode ICAO -> canonico (tabella curata)
TYPECODE_MAP = {
    # Airbus
    "A19N": "Airbus A319-100", "A320": "Airbus A320-200", "A321": "Airbus A321-200",
    "A20N": "Airbus A320neo", "A21N": "Airbus A321neo",
    "A332": "Airbus A330-200", "A333": "Airbus A330-300", "A339": "Airbus A330-900neo",
    "A359": "Airbus A350-900", "A35K": "Airbus A350-1000",
    "A388": "Airbus A380-800",
    "A306": "Airbus A300-600F", "A30B": "Airbus A300-600F",
    # Boeing
    "B738": "Boeing 737-800", "B739": "Boeing 737-800", "B737": "Boeing 737-800",
    "B38M": "Boeing 737 MAX 8-200", "B39M": "Boeing 737 MAX 8-200",
    "B752": "Boeing 757-200", "B753": "Boeing 757-200",
    "B763": "Boeing 767-300", "B764": "Boeing 767-400", "B76F": "Boeing 767-300F",
    "B772": "Boeing 777-200", "B773": "Boeing 777-300ER", "B77W": "Boeing 777-300ER",
    "B77L": "Boeing 777-200", "B778": "Boeing 777-300ER", "B779": "Boeing 777-300ER",
    "B77F": "Boeing 777F", "B77L": "Boeing 777F",
    "B788": "Boeing 787-8", "B789": "Boeing 787-9", "B78X": "Boeing 787-10",
    "B744": "Boeing 747-400", "B748": "Boeing 747-8F",
    # Embraer
    "E170": "Embraer E170", "E175": "Embraer E175", "E190": "Embraer ERJ-190",
    "E195": "Embraer E195", "E290": "Embraer ERJ-190", "E295": "Embraer E195",
    "E145": "Embraer ERJ-145",
    "E55P": "Embraer Phenom 300", "E50P": "Embraer Phenom 100",
    # Regional
    "AT72": "ATR 72-600", "AT45": "ATR 42-500", "AT46": "ATR 42-500",
    "DH8D": "De Havilland Canada Dash 8-400", "DH8C": "De Havilland Canada Dash 8-400",
    "SF34": "Saab 340", "F100": "Fokker 100",
    "CRJ9": "Bombardier Challenger 600", "CRJ2": "Bombardier Challenger 600",
    "CRJ7": "Bombardier Challenger 600",
    # Business jet
    "CL30": "Bombardier Challenger 300", "CL35": "Bombardier Challenger 300",
    "CL60": "Bombardier Challenger 600",
    "GLF4": "Gulfstream IV", "GLF5": "Gulfstream G550", "GLF6": "Gulfstream G650",
    "GL7T": "Gulfstream G650",
    "C25A": "Cessna Citation CJ2+", "C25B": "Cessna Citation CJ2+",
    "C25C": "Cessna Citation CJ2+", "C25M": "Cessna Citation CJ2+",
    "C56X": "Cessna Citation XLS+", "C550": "Cessna Citation XLS+",
    "C510": "Cessna Citation Mustang",
    "C680": "Cessna Citation (generico)", "C68A": "Cessna Citation (generico)",
    "C525": "Cessna Citation CJ2+",
    "LJ45": "Learjet 45", "LJ40": "Learjet 45", "LJ60": "Learjet 45",
    "FA7X": "Dassault Falcon 7X/8X", "FA8X": "Dassault Falcon 7X/8X",
    "F2TH": "Dassault Falcon 2000", "F900": "Dassault Falcon 900",
    "F50": "Dassault Falcon 50",
    "H25B": "Hawker 800/900XP", "H25C": "Hawker 800/900XP",
    "PC12": "Pilatus PC-12", "PC24": "Pilatus PC-24",
    # Elicotteri
    "EC35": "Elicottero", "EC45": "Elicottero", "H145": "Elicottero",
    "H125": "Elicottero", "A109": "Elicottero", "AS50": "Elicottero",
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


def _download_mictronics():
    print("Scarico Mictronics...")
    try:
        r = requests.get(MICTRONICS_ZIP, timeout=120)
        r.raise_for_status()
    except Exception as e:
        print("  Download fallito: " + str(e))
        return {}, {}
    try:
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        with zf.open("aircrafts.json") as f:
            aircrafts = json.load(f)
        with zf.open("types.json") as f:
            types = json.load(f)
    except Exception as e:
        print("  Parsing fallito: " + str(e))
        return {}, {}
    print("  " + str(len(aircrafts)) + " aircrafts, " + str(len(types)) + " types")
    return aircrafts, types


def _resolve_model(typecode, model_long):
    if typecode and typecode.upper() in TYPECODE_MAP:
        return TYPECODE_MAP[typecode.upper()], "typecode"
    if model_long:
        canon = normalize(model_long)
        if canon not in ("Aviazione generale (generico)", "N/D"):
            return canon, "normalize"
    return None, None


def _upsert_and_update(icao24, rec):
    bgy_db.execute_query(
        "INSERT INTO aircraft_hexdb "
        "(icao24, registration, typecode, model, manufacturer, operator, built, source, fetched_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW()) "
        "ON CONFLICT (icao24) DO UPDATE SET "
        "registration = EXCLUDED.registration, typecode = EXCLUDED.typecode, "
        "model = EXCLUDED.model, source = EXCLUDED.source, fetched_at = NOW()",
        (icao24, rec["registration"], rec["typecode"], rec["model_raw"],
         None, None, None, "mictronics"), fetch=False
    )
    bgy_db.execute_query(
        "UPDATE aircraft_icao24_db SET "
        "model = %s, "
        "operator = COALESCE(operator, %s), "
        "registration = COALESCE(registration, %s), "
        "typecode = COALESCE(typecode, %s) "
        "WHERE icao24 = %s",
        (rec["model_canon"], rec.get("operator"), rec["registration"], rec["typecode"], icao24),
        fetch=False
    )


def main():
    apply = "--apply" in sys.argv
    limit = None
    for i, a in enumerate(sys.argv):
        if a == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    icao_list = _load_icao24_senza_modello(limit)
    print("\n" + "=" * 70)
    print("ARRICCHIMENTO MICTRONICS — " + ("APPLY" if apply else "DRY-RUN"))
    print("=" * 70)
    print("icao24 senza modello: " + str(len(icao_list)))
    if not icao_list:
        return

    aircrafts, types = _download_mictronics()
    if not aircrafts:
        print("Mictronics non disponibile. Stop.")
        return

    hits = 0
    misses = []
    for icao in icao_list:
        key = icao.lower()
        vals = aircrafts.get(key)
        if not vals or not isinstance(vals, list) or len(vals) < 2:
            misses.append(icao)
            continue
        reg = vals[0]
        td = vals[1]
        type_info = types.get(td) if isinstance(types, dict) else None
        model_long = type_info[0] if isinstance(type_info, list) and type_info else None
        model_canon, how = _resolve_model(td, model_long)
        if not model_canon:
            misses.append(icao)
            continue
        hits += 1
        print("  " + icao + "  " + str(td).ljust(6) + "  " + model_canon.ljust(32) + " (" + str(how) + ")")
        if apply:
            _upsert_and_update(icao, {
                "registration": reg, "typecode": td,
                "model_raw": model_long, "model_canon": model_canon,
            })

    print("\nMictronics: " + str(hits) + " arricchiti, " + str(len(misses)) + " non mappati")
    if misses and len(misses) <= 30:
        print("Non mappati: " + ", ".join(misses))
    elif misses:
        print("Non mappati (primi 30): " + ", ".join(misses[:30]) + " ...")

    if not apply:
        print("\nDRY-RUN: nessuna modifica. Rilancia con --apply.")
    else:
        print("\nApplicato. Verifica:")
        print("  SELECT source, COUNT(*) FROM aircraft_hexdb GROUP BY source;")
        print("  SELECT model, COUNT(*) FROM aircraft_icao24_db WHERE model NOT IN ('N/D','') GROUP BY model ORDER BY COUNT(*) DESC LIMIT 15;")


if __name__ == "__main__":
    main()