"""
bgy_tools/metar_fetcher.py - Scarica e parsa i METAR di LIME (Bergamo).
Versione 2.0.0 — 22/10/2026

Novità v2.0.0:
- Doppia fonte: AWC (ultimi 15 giorni, parametro hours=360) + IEM ASOS (storico).
- Fallback automatico: se IEM non risponde, usa solo AWC e logga warning.
- Parsing unificato (parse_metar_raw) per entrambe le fonti.

Uso:
    py -3.12 -m bgy_tools.metar_fetcher --from 2026-09-30 --to 2026-10-22
    py -3.12 -m bgy_tools.metar_fetcher --date 2026-10-21
    py -3.12 -m bgy_tools.metar_fetcher --awc-only
"""
import sys
import re
import argparse
import requests
from datetime import datetime, timedelta
from bgy_core import bgy_db
from bgy_core.bgy_logger import get_logger

logger = get_logger("MetarFetcher")

AWC_URL = "https://aviationweather.gov/api/data/metar"
IEM_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
ICAO = "LIME"


def parse_metar_raw(raw, fallback_date=None):
    """Parsa un METAR grezzo. Ritorna dict o None."""
    if not raw:
        return None

    m_time = re.search(r'\b(\d{2})(\d{2})(\d{2})Z\b', raw)
    if not m_time:
        return None
    day = int(m_time.group(1))
    hh = int(m_time.group(2))
    mm = int(m_time.group(3))
    orario = f"{hh:02d}:{mm:02d}:00"

    m_wind = re.search(r'\b(\d{3}|VRB)(\d{2,3})(G\d{2,3})?KT\b', raw)
    vento_dir = None
    vento_kt = None
    if m_wind:
        dir_str = m_wind.group(1)
        if dir_str != "VRB":
            vento_dir = int(dir_str)
        vento_kt = int(m_wind.group(2))

    m_vis = re.search(r'\b(\d{4})\b', raw)
    visibilita_m = int(m_vis.group(1)) if m_vis else None

    m_temp = re.search(r'\b(M?\d{2})/(M?\d{2})\b', raw)
    temp_c = None
    dew_c = None
    if m_temp:
        t_str = m_temp.group(1).replace('M', '-')
        d_str = m_temp.group(2).replace('M', '-')
        try:
            temp_c = int(t_str)
            dew_c = int(d_str)
        except ValueError:
            pass

    m_qnh = re.search(r'\bQ(\d{3,4})\b', raw)
    qnh = int(m_qnh.group(1)) if m_qnh else None

    return {
        "orario": orario,
        "vento_dir": vento_dir,
        "vento_kt": vento_kt,
        "visibilita_m": visibilita_m,
        "temperatura_c": temp_c,
        "dewpoint_c": dew_c,
        "pressione_hpa": qnh,
        "raw": raw,
    }


def fetch_awc():
    """Scarica gli ultimi ~15 giorni da AWC. Ritorna lista di dict con data_riferimento."""
    url = f"{AWC_URL}?ids={ICAO}&format=json&hours=360"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            logger.warning(f"AWC HTTP {r.status_code}: {r.text[:100]}")
            return []
        data = r.json()
        if not isinstance(data, list):
            return []
        out = []
        for m in data:
            raw = m.get("rawOb")
            rt = m.get("reportTime")
            if not raw or not rt:
                continue
            try:
                dt = datetime.fromisoformat(rt.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
                orario = dt.strftime("%H:%M:%S")
            except ValueError:
                continue
            parsed = parse_metar_raw(raw)
            if not parsed:
                continue
            parsed["data_riferimento"] = date_str
            parsed["orario"] = orario
            out.append(parsed)
        logger.info(f"AWC: {len(out)} METAR")
        return out
    except Exception as e:
        logger.error(f"Errore AWC: {e}")
        return []


def fetch_iem(date_from, date_to):
    """Scarica lo storico da IEM ASOS. Ritorna lista di dict."""
    d1 = datetime.strptime(date_from, "%Y-%m-%d")
    d2 = datetime.strptime(date_to, "%Y-%m-%d")
    url = (
        f"{IEM_URL}?station={ICAO}&data=metar"
        f"&year1={d1.year}&month1={d1.month}&day1={d1.day}"
        f"&year2={d2.year}&month2={d2.month}&day2={d2.day}"
        f"&tz=UTC&format=json"
    )
    try:
        r = requests.get(url, timeout=60)
        if r.status_code != 200:
            logger.warning(f"IEM HTTP {r.status_code}")
            return []
        data = r.json()
        if not isinstance(data, list):
            return []
        out = []
        for m in data:
            valid = m.get("valid")
            raw = m.get("metar")
            if not valid or not raw:
                continue
            try:
                dt = datetime.fromisoformat(valid)
                date_str = dt.strftime("%Y-%m-%d")
                orario = dt.strftime("%H:%M:%S")
            except ValueError:
                continue
            parsed = parse_metar_raw(raw)
            if not parsed:
                continue
            parsed["data_riferimento"] = date_str
            parsed["orario"] = orario
            out.append(parsed)
        logger.info(f"IEM: {len(out)} METAR ({date_from} → {date_to})")
        return out
    except Exception as e:
        logger.error(f"Errore IEM: {e}")
        return []


def save_metar_to_db(records):
    if not records:
        return 0
    sql = """
        INSERT INTO weather_metar 
        (data_riferimento, orario, vento_dir, vento_kt, visibilita_m, temperatura_c, dewpoint_c, pressione_hpa, raw)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (data_riferimento, orario) DO NOTHING
    """
    params = [
        (r["data_riferimento"], r["orario"], r["vento_dir"], r["vento_kt"], r["visibilita_m"],
         r["temperatura_c"], r["dewpoint_c"], r["pressione_hpa"], r["raw"])
        for r in records
    ]
    # Dedup in memoria per (data_riferimento, orario) prima dell'INSERT
    seen = set()
    dedup = []
    for p in params:
        k = (p[0], p[1])
        if k in seen:
            continue
        seen.add(k)
        dedup.append(p)
    if len(dedup) < len(params):
        logger.info(f"Dedup: {len(params) - len(dedup)} duplicati in memoria")
    ok, msg = bgy_db.execute_many(sql, dedup)
    if not ok:
        logger.error(f"Errore salvataggio METAR: {msg}")
        return 0
    return len(dedup)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Data singola (YYYY-MM-DD)")
    parser.add_argument("--from", dest="from_date", help="Data inizio range")
    parser.add_argument("--to", dest="to_date", help="Data fine range")
    parser.add_argument("--awc-only", action="store_true", help="Solo AWC (ultimi 15 giorni)")
    args = parser.parse_args()

    records = []

    # 1. AWC: ultimi 15 giorni
    logger.info("Scarico AWC (ultimi ~15 giorni)...")
    awc = fetch_awc()
    records.extend(awc)

    # 2. IEM: storico, escluso il periodo già coperto da AWC
    if not args.awc_only:
        if args.date:
            iem = fetch_iem(args.date, args.date)
        elif args.from_date and args.to_date:
            iem = fetch_iem(args.from_date, args.to_date)
        else:
            iem = []
        records.extend(iem)

    # 3. Filtra per il range richiesto (se specificato)
    if args.date:
        records = [r for r in records if r["data_riferimento"] == args.date]
    elif args.from_date and args.to_date:
        records = [r for r in records if args.from_date <= r["data_riferimento"] <= args.to_date]

    n = save_metar_to_db(records)
    print(f"Totale: {len(records)} METAR (di cui {n} inseriti, {len(records) - n} duplicati)")
    return 0


if __name__ == "__main__":
    sys.exit(main())