"""
bgy_core/bgy_update_rules.py - Arricchimento dati da regole JSON.
Versione 2.6.1
- Aggiunto supporto OpenFlights per lookup compagnie aeree
- Mappa IATA -> ICAO caricata da config_rules_airlines.json
- extract_callsign_prefix gestisce prefissi misti (W4, W6, 3F, V7)
- get_airline() controlla OpenFlights prima di auto-aggiungere
- Aggiunta _charter_airlines e is_charter_flight()
"""
import os
import requests
from datetime import datetime
from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_config_manager import config_manager
from bgy_core.bgy_paths import DATA_DIR

logger = get_logger("UpdateRules")

_AIRLINES = {}
_COUNTRIES = {}
_AIRCRAFT_MODELS = {}
_CARGO_AIRLINES = {}
_CHARTER_AIRLINES = {}
_IATA_TO_ICAO = {}
_SEATS = {}
_LOAD_FACTORS = {}
_DEFAULT_LOAD_FACTOR = 0.85
_NOISE_STATIONS = {}
_NOISE_CURVES = {}
_DEFAULT_NOISE_CURVES = {}

_OPENFLIGHTS_DATA = {}
_OPENFLIGHTS_LOADED = False


def load_rules():
    """Ricarica le regole da config_manager e ripopola le cache locali."""
    global _AIRLINES, _COUNTRIES, _AIRCRAFT_MODELS, _CARGO_AIRLINES, _CHARTER_AIRLINES, _IATA_TO_ICAO
    global _SEATS, _LOAD_FACTORS, _DEFAULT_LOAD_FACTOR
    global _NOISE_STATIONS, _NOISE_CURVES, _DEFAULT_NOISE_CURVES

    raw_airlines = dict(config_manager.get_airlines())

    _IATA_TO_ICAO = raw_airlines.pop("_iata_to_icao", {})
    _CARGO_AIRLINES = raw_airlines.pop("_cargo_airlines", {})
    _CHARTER_AIRLINES = raw_airlines.pop("_charter_airlines", {})
    _AIRLINES = raw_airlines

    _COUNTRIES = dict(config_manager.get_countries())

    raw_models = dict(config_manager.get_aircraft_models())
    _SEATS = raw_models.pop("_seats", {})
    lf_data = raw_models.pop("_load_factors", {})
    _DEFAULT_LOAD_FACTOR = lf_data.pop("_default", 0.85)
    _LOAD_FACTORS = lf_data
    _AIRCRAFT_MODELS = raw_models

    raw_noise = dict(config_manager.get_noise_impact())
    _NOISE_STATIONS = raw_noise.pop("_stations", {})
    curves_data = raw_noise.pop("_curves", {})
    _DEFAULT_NOISE_CURVES = curves_data.pop("_default", {})
    _NOISE_CURVES = curves_data

    logger.info(
        f"📚 Regole caricate: {len(_AIRLINES)} compagnie, "
        f"{len(_COUNTRIES)} destinazioni, "
        f"{len(_AIRCRAFT_MODELS)} modelli, "
        f"{len(_IATA_TO_ICAO)} conversioni IATA->ICAO, "
        f"{len(_CARGO_AIRLINES)} cargo, "
        f"{len(_CHARTER_AIRLINES)} charter, "
        f"{len(_SEATS)} posti, "
        f"{len(_LOAD_FACTORS)} load factors, "
        f"{len(_NOISE_STATIONS)} centraline, "
        f"{len(_NOISE_CURVES)} curve NPD"
    )


def reload_rules():
    config_manager.reload_rules()
    load_rules()
    logger.info("🔄 Regole ricaricate")


# -----------------------------------------------------------------------------
# OPENFLIGHTS
# -----------------------------------------------------------------------------

def _get_openflights_config():
    cfg = config_manager.get_data_config()
    of_cfg = cfg.get("openflights", {})
    return {
        "enabled": of_cfg.get("enabled", True),
        "url": of_cfg.get("url",
                          "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat"),
        "cache_file": of_cfg.get("cache_file", "airlines.dat"),
        "update_interval_days": int(of_cfg.get("update_interval_days", 7)),
        "http_timeout": int(of_cfg.get("http_timeout", 30)),
    }


def _get_openflights_path():
    cfg = _get_openflights_config()
    assets_dir = os.path.join(DATA_DIR, "bgy_assets")
    os.makedirs(assets_dir, exist_ok=True)
    return os.path.join(assets_dir, cfg["cache_file"])


def _download_openflights():
    cfg = _get_openflights_config()
    if not cfg["enabled"]:
        return False

    path = _get_openflights_path()

    if os.path.exists(path):
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        age_days = (datetime.now() - mtime).days
        if age_days < cfg["update_interval_days"]:
            logger.info(f"📦 OpenFlights cache aggiornata ({age_days} giorni)")
            return True

    try:
        logger.info("📥 Download OpenFlights airlines.dat...")
        resp = requests.get(cfg["url"], timeout=cfg["http_timeout"])
        if resp.status_code != 200:
            logger.error(f"❌ OpenFlights HTTP {resp.status_code}")
            return False
        with open(path, "w", encoding="utf-8") as f:
            f.write(resp.text)
        logger.info(f"💾 OpenFlights salvato: {path}")
        return True
    except Exception as e:
        logger.error(f"❌ Errore download OpenFlights: {e}")
        return False


def _load_openflights():
    global _OPENFLIGHTS_DATA, _OPENFLIGHTS_LOADED

    if _OPENFLIGHTS_LOADED:
        return

    path = _get_openflights_path()
    if not os.path.exists(path):
        if not _download_openflights():
            _OPENFLIGHTS_LOADED = True
            return

    try:
        import csv
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 6:
                    continue
                name = row[1].strip()
                icao = row[4].strip().upper()
                if icao and icao != "\\N" and name:
                    _OPENFLIGHTS_DATA[icao] = name
        logger.info(f"📚 OpenFlights: {len(_OPENFLIGHTS_DATA)} compagnie caricate")
    except Exception as e:
        logger.error(f"❌ Errore parsing OpenFlights: {e}")

    _OPENFLIGHTS_LOADED = True


def lookup_openflights(icao_code):
    if not icao_code or not isinstance(icao_code, str):
        return None
    _load_openflights()
    code = icao_code.strip().upper()
    return _OPENFLIGHTS_DATA.get(code)


def refresh_openflights():
    global _OPENFLIGHTS_LOADED, _OPENFLIGHTS_DATA
    _OPENFLIGHTS_LOADED = False
    _OPENFLIGHTS_DATA = {}
    ok = _download_openflights()
    if ok:
        _load_openflights()
    return ok


# -----------------------------------------------------------------------------
# IATA / ICAO
# -----------------------------------------------------------------------------

def iata_to_icao(iata_code):
    if not iata_code or not isinstance(iata_code, str):
        return None
    code = iata_code.strip().upper()
    return _IATA_TO_ICAO.get(code)


def extract_callsign_prefix(callsign, length=2):
    if not callsign or not isinstance(callsign, str):
        return ""
    s = callsign.strip().upper().replace(" ", "")
    if len(s) < length:
        return ""
    prefix = s[:length]
    if not any(c.isalpha() for c in prefix):
        return ""
    if not all(c.isalnum() for c in prefix):
        return ""
    return prefix


# -----------------------------------------------------------------------------
# AIRLINE
# -----------------------------------------------------------------------------

def get_airline(callsign):
    if not callsign or not isinstance(callsign, str):
        return "N/D"
    cs = callsign.strip().upper()
    prefix3 = cs[:3]
    prefix2 = cs[:2]

    for prefix in (prefix3, prefix2):
        if prefix in _AIRLINES:
            return _AIRLINES[prefix]

    for prefix in (prefix3, prefix2):
        if prefix in _CARGO_AIRLINES:
            return _CARGO_AIRLINES[prefix]

    for prefix in (prefix3, prefix2):
        if prefix in _CHARTER_AIRLINES:
            return _CHARTER_AIRLINES[prefix]

    openflights_name = lookup_openflights(prefix3)
    if openflights_name:
        logger.info(f"🌐 OpenFlights: {prefix3} -> {openflights_name}")
        if config_manager.add_airline(prefix3, openflights_name):
            _AIRLINES[prefix3] = openflights_name
        return openflights_name

    new_name = f"Compagnia {prefix3}"
    if config_manager.add_airline(prefix3, new_name):
        _AIRLINES[prefix3] = new_name
    return new_name


# -----------------------------------------------------------------------------
# CARGO / CHARTER
# -----------------------------------------------------------------------------

def is_cargo_flight(callsign):
    if not callsign or not isinstance(callsign, str):
        return False, None
    prefix3 = callsign.strip().upper()[:3]
    prefix2 = callsign.strip().upper()[:2]
    for prefix in (prefix3, prefix2):
        if prefix in _CARGO_AIRLINES:
            return True, _CARGO_AIRLINES[prefix]
    return False, None


def is_charter_flight(callsign):
    """Ritorna (bool, nome_charter) se il callsign è di una compagnia charter nota."""
    if not callsign or not isinstance(callsign, str):
        return False, None
    prefix3 = callsign.strip().upper()[:3]
    prefix2 = callsign.strip().upper()[:2]
    for prefix in (prefix3, prefix2):
        if prefix in _CHARTER_AIRLINES:
            return True, _CHARTER_AIRLINES[prefix]
    return False, None


# -----------------------------------------------------------------------------
# COUNTRY
# -----------------------------------------------------------------------------

def get_country(destination):
    if not destination or not isinstance(destination, str):
        return "N/D"
    dest_clean = destination.strip()
    dest_upper = dest_clean.upper()
    if dest_clean in _COUNTRIES:
        return _COUNTRIES[dest_clean]
    if dest_upper in _COUNTRIES:
        return _COUNTRIES[dest_upper]
    for key, val in _COUNTRIES.items():
        if key.upper() == dest_upper:
            return val
    for key, val in _COUNTRIES.items():
        if len(key) >= 4:
            if key in dest_upper or dest_upper in key.upper():
                return val
    if config_manager.add_destination(dest_upper, "DA CLASSIFICARE"):
        _COUNTRIES[dest_upper] = "DA CLASSIFICARE"
    return "DA CLASSIFICARE"


# -----------------------------------------------------------------------------
# AIRCRAFT MODEL
# -----------------------------------------------------------------------------

def get_aircraft_model(callsign):
    if not callsign or not isinstance(callsign, str):
        return "N/D"
    cs = callsign.strip().upper()
    for prefix in (cs[:3], cs[:2]):
        if prefix in _AIRCRAFT_MODELS:
            return _AIRCRAFT_MODELS[prefix]
    return "N/D"


# -----------------------------------------------------------------------------
# PAX
# -----------------------------------------------------------------------------

def get_seats(model):
    if not model or model == "N/D":
        return 0
    data = _SEATS.get(model, {})
    return data.get("posti_default", 0)


def get_load_factor(airline_code):
    if not airline_code:
        return _DEFAULT_LOAD_FACTOR
    return _LOAD_FACTORS.get(airline_code, _DEFAULT_LOAD_FACTOR)


def estimate_passengers(model, airline_code):
    seats = get_seats(model)
    lf = get_load_factor(airline_code)
    pax = int(seats * lf)
    return pax, seats, round(lf, 3)


# -----------------------------------------------------------------------------
# NOISE
# -----------------------------------------------------------------------------

def get_noise_stations():
    return _NOISE_STATIONS


def get_noise_curves(model):
    return _NOISE_CURVES.get(model, _DEFAULT_NOISE_CURVES)


# -----------------------------------------------------------------------------
# INIT
# -----------------------------------------------------------------------------

load_rules()