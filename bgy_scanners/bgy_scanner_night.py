"""
bgy_scanners/bgy_scanner_night.py - Scanner notturno multi-fonte.
Versione 2.5.0

- Fonte primaria: OpenSky Network
- Fallback 1: adsb.lol
- Fallback 2: adsb.fi
- Finestra notturna: 23:00 - 05:59
- Bounding box, coordinate, soglie, UA, timeout: da config_data.json (scanner_night)
"""
import os
import sys
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
from bgy_utils.bgy_utils_noise import haversine

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import RAW_DIR, CONFIG_OPENSKY
from bgy_core.bgy_retry import retry_on_failure
from bgy_core.bgy_config_manager import config_manager
from bgy_core.bgy_dates import radar_filename

logger = get_logger("ScannerNight")

# Sopprimi warning SSL per ambienti con SSL inspection
try:
    import urllib3
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    urllib3.disable_warnings(InsecureRequestWarning)
except Exception:
    pass


# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------

def _cfg():
    """Ritorna la config scanner_night con default applicati."""
    return config_manager.get_scanner_night_config()


# -----------------------------------------------------------------------------
# UTILITY
# -----------------------------------------------------------------------------

def load_opensky_credentials():
    if os.path.exists(CONFIG_OPENSKY):
        try:
            with open(CONFIG_OPENSKY, "r", encoding="utf-8") as f:
                creds = json.load(f)
                return creds.get("opensky_username", ""), creds.get("opensky_password", "")
        except Exception as e:
            logger.error(f"Errore lettura credenziali OpenSky: {e}")
    return None, None


def _get_session_date(now, start_hour):
    if now.hour >= start_hour:
        return now.strftime("%Y-%m-%d")
    return (now - timedelta(days=1)).strftime("%Y-%m-%d")


def _is_in_night_window(now, start_hour, end_hour):
    return now.hour >= start_hour or now.hour < end_hour


def _bearing_in_range(bearing, low, high):
    """Gestisce il wrap-around (es. RWY 34: 340-10)."""
    if low <= high:
        return low <= bearing <= high
    return bearing >= low or bearing <= high


def detect_runway_and_phase(lat, lon, track, alt, cfg):
    if lat is None or lon is None:
        return "N/D", "N/D", "N/D", 999

    bgy_lat = cfg["bgy_lat"]
    bgy_lon = cfg["bgy_lon"]
    max_distance = cfg["max_distance_km"]
    thresholds = cfg["phase_thresholds"]
    runways = cfg["runway_bearings"]

    distance = haversine(lat, lon, bgy_lat, bgy_lon)
    alt_val = alt if alt is not None else 0

    if distance < thresholds["landing_max_distance_km"] \
            and alt_val < thresholds["landing_max_altitude_ft"]:
        phase = "Atterraggio" if (track is not None and track > 180) else "Decollo"
    elif distance < thresholds["approach_max_distance_km"] \
            and alt_val < thresholds["approach_max_altitude_ft"]:
        phase = "Avvicinamento"
    elif distance < max_distance:
        phase = "Sorvolo"
    else:
        phase = "Transito"

    if track is not None and phase in ('Atterraggio', 'Decollo', 'Avvicinamento'):
        runway, direction = "N/D", f"Rotta {track:.1f}°"
        for rwy_name, (low, high) in runways.items():
            if _bearing_in_range(track, low, high):
                runway = rwy_name
                directions = {
                    "RWY 28": "Est -> Ovest", "RWY 10": "Ovest -> Est",
                    "RWY 16": "Nord -> Sud", "RWY 34": "Sud -> Nord",
                }
                direction = directions.get(rwy_name, "N/D")
                break
    else:
        runway, direction = "N/D", "N/D"

    return runway, direction, phase, distance


def _http_get_robusto(url, timeout=15, auth=None):
    cfg = _cfg()
    headers = {"User-Agent": cfg["user_agent"]}
    try:
        resp = requests.get(url, headers=headers, auth=auth, timeout=timeout)
        return resp, True
    except requests.exceptions.SSLError as e:
        logger.warning(f"⚠️ SSL error (tentativo 1): {e}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"⚠️ Errore HTTP (tentativo 1): {e}")
        return None, False

    try:
        logger.info("🔄 Riprovo con verify=False (SSL inspection?)...")
        resp = requests.get(url, headers=headers, auth=auth, timeout=timeout, verify=False)
        return resp, True
    except Exception as e:
        logger.error(f"❌ Errore HTTP (tentativo 2): {e}")
        return None, False


# -----------------------------------------------------------------------------
# FETCH: OPENSKY
# -----------------------------------------------------------------------------

def _fetch_opensky():
    cfg = _cfg()
    username, password = load_opensky_credentials()
    auth = (username, password) if username and password else None

    bbox = cfg["bbox"]
    url = (f"https://opensky-network.org/api/states/all?"
           f"lamin={bbox['lamin']}&lamax={bbox['lamax']}"
           f"&lomin={bbox['lomin']}&lomax={bbox['lomax']}")

    resp, ok = _http_get_robusto(url, timeout=cfg["http_timeout"], auth=auth)
    if not ok or resp is None:
        return None
    if resp.status_code == 429:
        logger.warning("⚠️ OpenSky: rate limit 429")
        return None
    if resp.status_code != 200:
        logger.error(f"❌ OpenSky HTTP {resp.status_code}")
        return None
    try:
        data = resp.json()
    except Exception as e:
        logger.error(f"❌ OpenSky JSON error: {e}")
        return None

    states = data.get("states")
    if states is None:
        logger.warning("⚠️ OpenSky: states=None")
        return None
    if not isinstance(states, list):
        logger.warning("⚠️ OpenSky: formato inatteso")
        return None

    logger.info(f"📡 OpenSky: ricevuti {len(states)} stati")
    return _parse_opensky(states)


def _parse_opensky(states):
    cfg = _cfg()
    max_distance = cfg["max_distance_km"]
    now = datetime.now()
    flights = []
    discarded_far = 0
    discarded_unknown = 0

    for s in states:
        if not isinstance(s, list) or len(s) < 17:
            continue
        callsign = s[1].strip() if s[1] else "UNKNOWN"
        icao24 = s[0] or None

        if callsign == "UNKNOWN" and s[5] is None and s[6] is None:
            discarded_unknown += 1
            continue
        if icao24 is None:
            continue

        runway, direction, phase, distance = detect_runway_and_phase(
            s[6], s[5], s[10], s[7], cfg)
        if distance > max_distance:
            discarded_far += 1
            continue

        flights.append({
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "callsign": callsign,
            "icao24": icao24,
            "pista": runway,
            "fase_volo": phase,
            "direzione": direction,
            "quota_ft": int(s[7]) if s[7] else 0,
            "rotta_deg": float(s[10]) if s[10] else 0,
            "distanza_km": round(distance, 2),
            "paese": s[2] or "N/D",
        })

    if discarded_far > 0:
        logger.info(f"🗑️ Scartati {discarded_far} voli oltre {max_distance} km")
    if discarded_unknown > 0:
        logger.debug(f"🗑️ Scartati {discarded_unknown} stati senza callsign/posizione")
    return flights


# -----------------------------------------------------------------------------
# FETCH: ADSB.LOL
# -----------------------------------------------------------------------------

def _fetch_adsblol():
    cfg = _cfg()
    url = (f"https://api.adsb.lol/v2/point/"
           f"{cfg['bgy_lat']}/{cfg['bgy_lon']}/{cfg['adsb_lol_radius_nm']}")
    resp, ok = _http_get_robusto(url, timeout=cfg["http_timeout"])
    if not ok or resp is None:
        logger.error("❌ adsb.lol: nessuna risposta valida")
        return None
    if resp.status_code == 403:
        logger.warning("⚠️ adsb.lol: HTTP 403 (forbidden)")
        return None
    if resp.status_code != 200:
        logger.error(f"❌ adsb.lol HTTP {resp.status_code}")
        return None
    try:
        data = resp.json()
    except Exception as e:
        logger.error(f"❌ adsb.lol JSON error: {e}")
        return None

    aircraft = data.get("ac") or data.get("aircraft") or []
    if not aircraft:
        logger.warning("⚠️ adsb.lol: nessun aereo nell'area")
        return None
    logger.info(f"📡 adsb.lol: ricevuti {len(aircraft)} stati (fallback 1)")
    return _parse_adsb_generic(aircraft, "adsb.lol")


# -----------------------------------------------------------------------------
# FETCH: ADSB.FI
# -----------------------------------------------------------------------------

def _fetch_adsbfi():
    cfg = _cfg()
    url = (f"https://opendata.adsb.fi/api/v3/lat/"
           f"{cfg['bgy_lat']}/lon/{cfg['bgy_lon']}/dist/{cfg['adsb_fi_radius_nm']}")
    resp, ok = _http_get_robusto(url, timeout=cfg["http_timeout"])
    if not ok or resp is None:
        logger.error("❌ adsb.fi: nessuna risposta valida")
        return None
    if resp.status_code == 403:
        logger.warning("⚠️ adsb.fi: HTTP 403 (forbidden)")
        return None
    if resp.status_code != 200:
        logger.error(f"❌ adsb.fi HTTP {resp.status_code}")
        return None
    try:
        data = resp.json()
    except Exception as e:
        logger.error(f"❌ adsb.fi JSON error: {e}")
        return None

    aircraft = data.get("ac") or data.get("aircraft") or []
    if not aircraft:
        logger.warning("⚠️ adsb.fi: nessun aereo nell'area")
        return None
    logger.info(f"📡 adsb.fi: ricevuti {len(aircraft)} stati (fallback 2)")
    return _parse_adsb_generic(aircraft, "adsb.fi")


# -----------------------------------------------------------------------------
# PARSER GENERICO
# -----------------------------------------------------------------------------

def _parse_adsb_generic(aircraft, source_name):
    cfg = _cfg()
    max_distance = cfg["max_distance_km"]
    now = datetime.now()
    flights = []
    discarded_far = 0
    discarded_unknown = 0

    for ac in aircraft:
        if not isinstance(ac, dict):
            continue
        callsign = (ac.get("flight") or "").strip().upper() or "UNKNOWN"
        icao24 = ac.get("hex") or None
        lat = ac.get("lat")
        lon = ac.get("lon")
        alt = ac.get("alt_baro")
        track = ac.get("track")

        if icao24 is None or lat is None or lon is None:
            discarded_unknown += 1
            continue

        if isinstance(alt, str) and alt.lower() == "ground":
            alt_ft = 0
        else:
            try:
                alt_ft = int(alt) if alt is not None else 0
            except (ValueError, TypeError):
                alt_ft = 0

        try:
            track_deg = float(track) if track is not None else None
        except (ValueError, TypeError):
            track_deg = None

        runway, direction, phase, distance = detect_runway_and_phase(
            lat, lon, track_deg, alt_ft, cfg)
        if distance > max_distance:
            discarded_far += 1
            continue

        flights.append({
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "callsign": callsign,
            "icao24": icao24,
            "pista": runway,
            "fase_volo": phase,
            "direzione": direction,
            "quota_ft": alt_ft,
            "rotta_deg": track_deg if track_deg is not None else 0,
            "distanza_km": round(distance, 2),
            "paese": ac.get("country") or "N/D",
        })

    if discarded_far > 0:
        logger.info(f"🗑️ {source_name}: scartati {discarded_far} voli oltre {max_distance} km")
    if discarded_unknown > 0:
        logger.debug(f"🗑️ {source_name}: scartati {discarded_unknown} stati senza posizione")
    return flights


# -----------------------------------------------------------------------------
# SCANSIONE PRINCIPALE
# -----------------------------------------------------------------------------

@retry_on_failure(max_retries=2, delay=2)
def run_night_scan(check_night_window=True):
    cfg = _cfg()
    now = datetime.now()

    if check_night_window and not _is_in_night_window(
            now, cfg["night_start_hour"], cfg["night_end_hour"]):
        logger.info("🌙 Fuori dalla finestra notturna (23:00-05:59). Scansione ignorata.")
        return None

    logger.info("🌙 Avvio scansione notturna...")
    os.makedirs(RAW_DIR, exist_ok=True)

    session_date = _get_session_date(now, cfg["night_start_hour"])

    flights = _fetch_opensky()
    source = "OpenSky"
    if not flights:
        logger.warning("⚠️ OpenSky non disponibile, tento adsb.lol...")
        flights = _fetch_adsblol()
        source = "adsb.lol"
    if not flights:
        logger.warning("⚠️ adsb.lol non disponibile, tento adsb.fi...")
        flights = _fetch_adsbfi()
        source = "adsb.fi"
    if not flights:
        logger.error("❌ Nessuna fonte dati disponibile (OpenSky + adsb.lol + adsb.fi)")
        return None

    logger.info(f"✅ Fonte dati: {source} ({len(flights)} voli nell'area)")

    df_new = pd.DataFrame(flights)
    df_new["sessione_notturna"] = session_date

    out_file = os.path.join(RAW_DIR, radar_filename(session_date))

    if os.path.exists(out_file):
        try:
            existing = pd.read_csv(out_file)
            df = pd.concat([existing, df_new], ignore_index=True)
        except Exception as e:
            logger.warning(f"Errore lettura file esistente: {e}")
            df = df_new
    else:
        df = df_new

    if "icao24" in df.columns and "distanza_km" in df.columns:
        before = len(df)
        df = df.sort_values("distanza_km", ascending=True)
        df = df.drop_duplicates(subset=["icao24"], keep="first")
        df = df.sort_values("timestamp", ascending=True).reset_index(drop=True)
        removed = before - len(df)
        if removed > 0:
            logger.info(f"🔀 Deduplicati {removed} rilevamenti ridondanti ({len(df)} aerei unici)")

    df.to_csv(out_file, index=False, encoding="utf-8-sig")
    logger.info(f"💾 File salvato: {out_file} - {len(df)} aerei unici (fonte: {source})")
    return out_file


if __name__ == "__main__":
    run_night_scan(check_night_window=False)