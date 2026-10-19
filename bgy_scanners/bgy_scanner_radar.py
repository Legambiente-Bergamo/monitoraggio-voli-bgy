"""
bgy_scanners/bgy_scanner_radar.py - Scanner radar h24 multi-fonte.
Versione 1.3.1

Novità v1.3.1 (INFRA-18, 19/10/2026):
- Circuit breaker per adsb.lol: dopo N errori HTTP 429
  (config: scanner_radar.adsb_lol_max_429_before_cooldown, default 1),
  adsb.lol viene saltato per adsb_lol_cooldown_min minuti
  (default 30). Durante il cooldown, la cascata parte da adsb.fi.
- Contatore 429 resettato al primo fetch adsb.lol riuscito.
- Nuove funzioni: _get_adsb_lol_cooldown_min(), _get_adsb_lol_max_429(),
  _set_adsb_lol_cooldown().

Novità v1.3.0 (BUG-02, 14/10/2026):
- detect_runway_and_phase(): fix discriminazione D/A quando baro_rate
  è nullo o non significativo. Usa bearing verso BGY.
- Nuove funzioni: _bearing_to_bgy(), _angular_difference().
- Soglia baro_rate configurabile in
  config_data.json > scanner_radar.baro_rate_threshold_fpm (default 500).

Novità v1.2.0 (DST-01, 10/10/2026):
- Campo timestamp_utc a tutti i rilevamenti (ISO 8601 con offset).
- Dedup differenziata: timestamp_utc se valorizzato, altrimenti
  fallback a (icao24, floor 1min di timestamp).

Novità v1.1.2: dedup floor 1 min.
Novità v1.1.1: esclusi RWY 16 e RWY 34 da detect_runway_and_phase().
Novità v1.1.0: baro_rate + conversione OpenSky m→ft.
Novità v1.0.0: primo rilascio.
"""
import os
import sys
import json
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from math import radians, degrees, sin, cos, sqrt, atan2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import RAW_DIR, CONFIG_OPENSKY
from bgy_core.bgy_retry import retry_on_failure
from bgy_core.bgy_config_manager import config_manager
from bgy_core.bgy_dates import radar_filename

logger = get_logger("ScannerRadar")

try:
    import urllib3
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    urllib3.disable_warnings(InsecureRequestWarning)
except Exception:
    pass


BARO_RATE_THRESHOLD_FPM_DEFAULT = 500
INCERT_DEAD_ZONE_DEG = 5

# v1.3.1 (INFRA-18): stato circuit breaker adsb.lol
_adsb_lol_cooldown_until = None
_adsb_lol_429_count = 0


def _cfg():
    return config_manager.get_scanner_radar_config()


def _get_baro_rate_threshold():
    """v1.3.0 (BUG-02): legge la soglia baro_rate da config, con default."""
    try:
        cfg = _cfg()
        return int(cfg.get("baro_rate_threshold_fpm", BARO_RATE_THRESHOLD_FPM_DEFAULT))
    except Exception:
        return BARO_RATE_THRESHOLD_FPM_DEFAULT


def _get_adsb_lol_cooldown_min():
    """v1.3.1 (INFRA-18): minuti di cooldown dopo 429 su adsb.lol."""
    try:
        cfg = _cfg()
        return int(cfg.get("adsb_lol_cooldown_min", 30))
    except Exception:
        return 30


def _get_adsb_lol_max_429():
    """v1.3.1 (INFRA-18): numero di 429 prima di attivare il cooldown."""
    try:
        cfg = _cfg()
        return int(cfg.get("adsb_lol_max_429_before_cooldown", 1))
    except Exception:
        return 1


def _set_adsb_lol_cooldown(minutes):
    """v1.3.1 (INFRA-18): attiva il cooldown per adsb.lol."""
    global _adsb_lol_cooldown_until
    _adsb_lol_cooldown_until = datetime.now() + timedelta(minutes=minutes)


def _utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S%z")


def load_opensky_credentials():
    if os.path.exists(CONFIG_OPENSKY):
        try:
            with open(CONFIG_OPENSKY, "r", encoding="utf-8") as f:
                creds = json.load(f)
                return creds.get("opensky_username", ""), creds.get("opensky_password", "")
        except Exception as e:
            logger.error(f"Errore lettura credenziali OpenSky: {e}")
    return None, None


def _get_session_date(now):
    return now.strftime("%Y-%m-%d")


def _bearing_in_range(bearing, low, high):
    if low <= high:
        return low <= bearing <= high
    return bearing >= low or bearing <= high


def _bearing_to_bgy(lat, lon, bgy_lat, bgy_lon):
    """
    v1.3.0 (BUG-02): calcola il bearing (azimuth) dall'aereo verso BGY,
    in gradi [0, 360). Formula standard (great-circle initial bearing).
    """
    try:
        lat1_r = radians(float(lat))
        lat2_r = radians(float(bgy_lat))
        dlon_r = radians(float(bgy_lon) - float(lon))
    except (TypeError, ValueError):
        return None
    y = sin(dlon_r) * cos(lat2_r)
    x = cos(lat1_r) * sin(lat2_r) - sin(lat1_r) * cos(lat2_r) * cos(dlon_r)
    if x == 0 and y == 0:
        return None
    bearing = degrees(atan2(y, x))
    return (bearing + 360) % 360


def _angular_difference(a, b):
    """v1.3.0 (BUG-02): differenza angolare minima tra due bearing, in [0, 180]."""
    try:
        d = abs(float(a) - float(b)) % 360
    except (TypeError, ValueError):
        return None
    return d if d <= 180 else 360 - d


def _discrimina_da_track(lat, lon, track, cfg, fase_se_verso_bgy, fase_se_via_da_bgy):
    """
    v1.3.0 (BUG-02): helper. Usa bearing_to_bgy per discriminare tra due
    fasi possibili quando il baro_rate non è significativo.

    Ritorna:
      - fase_se_verso_bgy se l'aereo punta VERSO BGY (diff < 85°)
      - fase_se_via_da_bgy se l'aereo punta VIA DA BGY (diff > 95°)
      - "Incerto" nella fascia ambigua (85° ≤ diff ≤ 95°)
      - "Incerto" se lat/lon/track sono invalidi
    """
    if track is None or lat is None or lon is None:
        return "Incerto"

    bgy_lat = cfg["bgy_lat"]
    bgy_lon = cfg["bgy_lon"]
    bearing = _bearing_to_bgy(lat, lon, bgy_lat, bgy_lon)
    if bearing is None:
        return "Incerto"

    diff = _angular_difference(track, bearing)
    if diff is None:
        return "Incerto"

    soglia_bassa = 90 - INCERT_DEAD_ZONE_DEG
    soglia_alta = 90 + INCERT_DEAD_ZONE_DEG

    if diff < soglia_bassa:
        return fase_se_verso_bgy
    if diff > soglia_alta:
        return fase_se_via_da_bgy
    return "Incerto"


def detect_runway_and_phase(lat, lon, track, alt, cfg, baro_rate=None):
    """
    Determina pista, fase, direzione e distanza da BGY.

    baro_rate: velocità verticale in ft/min (positiva = salita,
               negativa = discesa). None se non disponibile.

    v1.3.0 (BUG-02): quando baro_rate è nullo o non significativo, usa
    il bearing verso BGY per discriminare D/A. Prima usava solo il track
    (> 180° → Atterraggio), che è sbagliato: il track NON distingue
    decollo da atterraggio sulla stessa pista.
    """
    if lat is None or lon is None:
        return "N/D", "N/D", "N/D", 999

    bgy_lat = cfg["bgy_lat"]
    bgy_lon = cfg["bgy_lon"]
    max_distance = cfg["max_distance_km"]
    thresholds = cfg["phase_thresholds"]
    runways = {
        k: v for k, v in cfg["runway_bearings"].items()
        if k not in ("RWY 16", "RWY 34")
    }
    distance = haversine(lat, lon, bgy_lat, bgy_lon)
    alt_val = alt if alt is not None else 0

    threshold = _get_baro_rate_threshold()

    if distance < thresholds["landing_max_distance_km"] \
            and alt_val < thresholds["landing_max_altitude_ft"]:
        if baro_rate is not None and abs(baro_rate) > threshold:
            phase = "Decollo" if baro_rate > 0 else "Atterraggio"
        else:
            phase = _discrimina_da_track(
                lat, lon, track, cfg,
                fase_se_verso_bgy="Atterraggio",
                fase_se_via_da_bgy="Decollo",
            )
    elif distance < thresholds["approach_max_distance_km"] \
            and alt_val < thresholds["approach_max_altitude_ft"]:
        if baro_rate is not None and baro_rate > threshold:
            phase = "Decollo"
        elif baro_rate is not None and baro_rate < -threshold:
            phase = "Avvicinamento"
        else:
            phase = _discrimina_da_track(
                lat, lon, track, cfg,
                fase_se_verso_bgy="Avvicinamento",
                fase_se_via_da_bgy="Decollo",
            )
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


def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    lat1_r, lon1_r = radians(lat1), radians(lon1)
    lat2_r, lon2_r = radians(lat2), radians(lon2)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = sin(dlat/2)**2 + cos(lat1_r) * cos(lat2_r) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))


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


def _fetch_adsblol():
    global _adsb_lol_429_count
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
    if resp.status_code == 429:
        _adsb_lol_429_count += 1
        max_429 = _get_adsb_lol_max_429()
        if _adsb_lol_429_count >= max_429:
            cooldown_min = _get_adsb_lol_cooldown_min()
            _set_adsb_lol_cooldown(cooldown_min)
            _adsb_lol_429_count = 0
            logger.warning(
                f"⚠️ adsb.lol: rate limit 429, cooldown {cooldown_min} min"
            )
        else:
            logger.warning(
                f"⚠️ adsb.lol: rate limit 429 ({_adsb_lol_429_count}/{max_429})"
            )
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
    # successo: reset contatore 429
    _adsb_lol_429_count = 0
    logger.info(f"📡 adsb.lol: ricevuti {len(aircraft)} stati (primaria)")
    return _parse_adsb_generic(aircraft, "adsb.lol")


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
    logger.info(f"📡 adsb.fi: ricevuti {len(aircraft)} stati (fallback 1)")
    return _parse_adsb_generic(aircraft, "adsb.fi")


def _fetch_airplaneslive():
    cfg = _cfg()
    if not cfg.get("airplanes_live_enabled", False):
        logger.debug("⏭️ airplanes.live disattivato in config")
        return None
    url = (f"https://api.airplanes.live/v2/point/"
           f"{cfg['bgy_lat']}/{cfg['bgy_lon']}/{cfg['airplanes_live_radius_nm']}")
    resp, ok = _http_get_robusto(url, timeout=cfg["http_timeout"])
    if not ok or resp is None:
        return None
    if resp.status_code != 200:
        logger.warning(f"⚠️ airplanes.live HTTP {resp.status_code}")
        return None
    try:
        data = resp.json()
    except Exception:
        return None
    aircraft = data.get("ac") or []
    if not aircraft:
        return None
    logger.info(f"📡 airplanes.live: ricevuti {len(aircraft)} stati (fallback 2)")
    return _parse_adsb_generic(aircraft, "airplanes.live")


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
    logger.info(f"📡 OpenSky: ricevuti {len(states)} stati (fallback 3)")
    return _parse_opensky(states)


def _parse_opensky(states):
    cfg = _cfg()
    max_distance = cfg["max_distance_km"]
    now = datetime.now()
    now_utc_iso = _utc_now_iso()
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

        alt_m = s[7]
        alt_ft = int(alt_m * 3.28084) if alt_m is not None else 0

        vrate_ms = s[11] if len(s) > 11 else None
        if vrate_ms is not None:
            try:
                baro_rate = int(float(vrate_ms) * 196.85)
            except (ValueError, TypeError):
                baro_rate = None
        else:
            baro_rate = None

        runway, direction, phase, distance = detect_runway_and_phase(
            s[6], s[5], s[10], alt_ft, cfg, baro_rate=baro_rate)
        if distance > max_distance:
            discarded_far += 1
            continue

        flights.append({
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "callsign": callsign, "icao24": icao24,
            "pista": runway, "fase_volo": phase, "direzione": direction,
            "quota_ft": alt_ft,
            "rotta_deg": float(s[10]) if s[10] else 0,
            "distanza_km": round(distance, 2),
            "paese": s[2] or "N/D",
            "baro_rate": baro_rate if baro_rate is not None else 0,
            "fonte": "opensky",
            "timestamp_utc": now_utc_iso,
        })

    if discarded_far > 0:
        logger.info(f"🗑️ Scartati {discarded_far} voli oltre {max_distance} km")
    if discarded_unknown > 0:
        logger.debug(f"🗑️ Scartati {discarded_unknown} stati senza callsign/posizione")
    return flights


def _parse_adsb_generic(aircraft, source_name):
    cfg = _cfg()
    max_distance = cfg["max_distance_km"]
    now = datetime.now()
    now_utc_iso = _utc_now_iso()
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
        track = ac.get("track") or ac.get("calc_track")
        baro_rate = ac.get("baro_rate") or ac.get("geom_rate")

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

        try:
            baro_rate_fpm = int(baro_rate) if baro_rate is not None else None
        except (ValueError, TypeError):
            baro_rate_fpm = None

        runway, direction, phase, distance = detect_runway_and_phase(
            lat, lon, track_deg, alt_ft, cfg, baro_rate=baro_rate_fpm)
        if distance > max_distance:
            discarded_far += 1
            continue

        flights.append({
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "callsign": callsign, "icao24": icao24,
            "pista": runway, "fase_volo": phase, "direzione": direction,
            "quota_ft": alt_ft,
            "rotta_deg": track_deg if track_deg is not None else 0,
            "distanza_km": round(distance, 2),
            "paese": ac.get("country") or "N/D",
            "baro_rate": baro_rate_fpm if baro_rate_fpm is not None else 0,
            "fonte": source_name,
            "timestamp_utc": now_utc_iso,
        })

    if discarded_far > 0:
        logger.info(f"🗑️ {source_name}: scartati {discarded_far} voli oltre {max_distance} km")
    if discarded_unknown > 0:
        logger.debug(f"🗑️ {source_name}: scartati {discarded_unknown} stati senza posizione")
    return flights


def _run_parallel_test():
    logger.info("=" * 60)
    logger.info("🧪 MODALITÀ TEST PARALLELO - Interrogo tutte le fonti")
    logger.info("=" * 60)

    results = {}
    sources = [
        ("adsb.lol", _fetch_adsblol),
        ("adsb.fi", _fetch_adsbfi),
        ("airplanes.live", _fetch_airplaneslive),
        ("opensky", _fetch_opensky),
    ]

    for name, fetch_fn in sources:
        try:
            flights = fetch_fn()
            n = len(flights) if flights else 0
            results[name] = {"count": n, "flights": flights or []}
            logger.info(f"  {name}: {n} aerei")
        except Exception as e:
            logger.error(f"  {name}: errore - {e}")
            results[name] = {"count": 0, "flights": [], "error": str(e)}

    now = datetime.now()
    session_date = _get_session_date(now)
    summary_file = os.path.join(
        RAW_DIR, f"radar_test_{session_date}_{now.strftime('%H-%M')}.json"
    )
    os.makedirs(RAW_DIR, exist_ok=True)
    try:
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                "results": {k: {"count": v["count"]} for k, v in results.items()},
            }, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Riepilogo test salvato: {summary_file}")
    except Exception as e:
        logger.error(f"Errore salvataggio riepilogo test: {e}")

    logger.info("-" * 60)
    logger.info("RIEPILOGO COPERTURA:")
    for name, r in results.items():
        logger.info(f"  {name:20s}: {r['count']:3d} aerei")
    logger.info("=" * 60)

    return results


@retry_on_failure(max_retries=2, delay=2)
def run_radar_scan(parallel_test=False):
    cfg = _cfg()
    now = datetime.now()

    if parallel_test:
        _run_parallel_test()
        return None

    logger.info("📡 Avvio scansione radar h24...")
    os.makedirs(RAW_DIR, exist_ok=True)
    session_date = _get_session_date(now)

    flights = None
    source = None

    # v1.3.1 (INFRA-18): rispetta il cooldown di adsb.lol
    if _adsb_lol_cooldown_until and datetime.now() < _adsb_lol_cooldown_until:
        logger.info(
            f"⏭️ adsb.lol in cooldown fino a "
            f"{_adsb_lol_cooldown_until.strftime('%H:%M:%S')}, salto"
        )
    else:
        flights = _fetch_adsblol()
        source = "adsb.lol"

    if not flights:
        if source is None:
            logger.warning("⚠️ adsb.lol in cooldown, tento adsb.fi...")
        else:
            logger.warning("⚠️ adsb.lol non disponibile, tento adsb.fi...")
        flights = _fetch_adsbfi()
        source = "adsb.fi"
    if not flights:
        logger.warning("⚠️ adsb.fi non disponibile, tento airplanes.live...")
        flights = _fetch_airplaneslive()
        source = "airplanes.live"
    if not flights:
        logger.warning("⚠️ airplanes.live non disponibile, tento OpenSky...")
        flights = _fetch_opensky()
        source = "opensky"
    if not flights:
        logger.error("❌ Nessuna fonte dati disponibile")
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

    if "icao24" in df.columns and "timestamp" in df.columns:
        before = len(df)
        ts_min = pd.to_datetime(df["timestamp"], errors="coerce").dt.floor("1min")
        if "timestamp_utc" in df.columns:
            ts_utc = pd.to_datetime(df["timestamp_utc"], errors="coerce", utc=True)
        else:
            ts_utc = pd.Series([pd.NaT] * len(df), index=df.index)
        key_utc = df["icao24"].astype(str) + "|UTC|" + ts_utc.astype(str)
        key_naive = df["icao24"].astype(str) + "|NAIVE|" + ts_min.astype(str)
        df["_dedup_key"] = key_utc.where(ts_utc.notna(), key_naive)
        df = df.drop_duplicates(subset=["_dedup_key"], keep="first")
        df = df.drop(columns=["_dedup_key"])
        removed = before - len(df)
        if removed > 0:
            logger.info(f"🔀 Deduplicati {removed} rilevamenti ridondanti ({len(df)} unici)")

    df = df.sort_values("timestamp", ascending=True).reset_index(drop=True)
    df.to_csv(out_file, index=False, encoding="utf-8-sig")
    logger.info(f"💾 File salvato: {out_file} - {len(df)} aerei (fonte: {source})")
    return out_file


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--parallel-test", action="store_true",
                        help="Interroga tutte le fonti e salva un riepilogo")
    args = parser.parse_args()
    run_radar_scan(parallel_test=args.parallel_test)