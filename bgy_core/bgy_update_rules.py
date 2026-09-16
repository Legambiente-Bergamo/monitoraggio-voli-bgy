"""
bgy_core/bgy_update_rules.py - Arricchimento dati da regole JSON.
Versione 2.5.0
- Cache locale popolata da config_manager (fonte unica di verità).
- Auto-add (compagnie, destinazioni) via config_manager, non più scritture dirette.
"""
from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_config_manager import config_manager

logger = get_logger("UpdateRules")

# Cache locale (per lookup veloci)
_AIRLINES = {}
_COUNTRIES = {}
_AIRCRAFT_MODELS = {}
_CARGO_AIRLINES = {}
_SEATS = {}
_LOAD_FACTORS = {}
_DEFAULT_LOAD_FACTOR = 0.85
_NOISE_STATIONS = {}
_NOISE_CURVES = {}
_DEFAULT_NOISE_CURVES = {}


# -----------------------------------------------------------------------------
# LOAD / RELOAD
# -----------------------------------------------------------------------------

def load_rules():
    """Ricarica le regole da config_manager e ripopola le cache locali."""
    global _AIRLINES, _COUNTRIES, _AIRCRAFT_MODELS, _CARGO_AIRLINES
    global _SEATS, _LOAD_FACTORS, _DEFAULT_LOAD_FACTOR
    global _NOISE_STATIONS, _NOISE_CURVES, _DEFAULT_NOISE_CURVES

    # --- Airlines ---
    raw_airlines = dict(config_manager.get_airlines())
    _CARGO_AIRLINES = raw_airlines.pop("_cargo_airlines", {})
    _AIRLINES = raw_airlines

    # --- Countries ---
    _COUNTRIES = dict(config_manager.get_countries())

    # --- Aircraft models (con _seats e _load_factors) ---
    raw_models = dict(config_manager.get_aircraft_models())
    _SEATS = raw_models.pop("_seats", {})
    lf_data = raw_models.pop("_load_factors", {})
    _DEFAULT_LOAD_FACTOR = lf_data.pop("_default", 0.85)
    _LOAD_FACTORS = lf_data
    _AIRCRAFT_MODELS = raw_models

    # --- Noise (con _stations e _curves) ---
    raw_noise = dict(config_manager.get_noise_impact())
    _NOISE_STATIONS = raw_noise.pop("_stations", {})
    curves_data = raw_noise.pop("_curves", {})
    _DEFAULT_NOISE_CURVES = curves_data.pop("_default", {})
    _NOISE_CURVES = curves_data

    logger.info(
        f"📚 Regole caricate: {len(_AIRLINES)} compagnie, "
        f"{len(_COUNTRIES)} destinazioni, "
        f"{len(_AIRCRAFT_MODELS)} modelli, "
        f"{len(_SEATS)} posti, "
        f"{len(_LOAD_FACTORS)} load factors, "
        f"{len(_NOISE_STATIONS)} centraline, "
        f"{len(_NOISE_CURVES)} curve NPD"
    )


def reload_rules():
    """Forza il reload da disco tramite config_manager."""
    config_manager.reload_rules()
    load_rules()
    logger.info("🔄 Regole ricaricate")


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
    # Auto-add (una volta sola per prefisso)
    new_name = f"Compagnia {prefix3}"
    if config_manager.add_airline(prefix3, new_name):
        _AIRLINES[prefix3] = new_name
    return new_name


# -----------------------------------------------------------------------------
# CARGO
# -----------------------------------------------------------------------------

def is_cargo_flight(callsign):
    if not callsign or not isinstance(callsign, str):
        return False, None
    prefix = callsign.strip().upper()[:3]
    if prefix in _CARGO_AIRLINES:
        return True, _CARGO_AIRLINES[prefix]
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
    # Auto-add
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
# PAX (posti + load factor)
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
    """Ritorna (stima_pax, posti_totali, load_factor)."""
    seats = get_seats(model)
    lf = get_load_factor(airline_code)
    pax = int(seats * lf)
    return pax, seats, round(lf, 3)


# -----------------------------------------------------------------------------
# NOISE
# -----------------------------------------------------------------------------

def get_noise_stations():
    """Ritorna dict {nome: {lat, lon}} delle centraline."""
    return _NOISE_STATIONS


def get_noise_curves(model):
    """Ritorna le curve NPD per il modello (o default)."""
    return _NOISE_CURVES.get(model, _DEFAULT_NOISE_CURVES)


# -----------------------------------------------------------------------------
# INIT
# -----------------------------------------------------------------------------

load_rules()