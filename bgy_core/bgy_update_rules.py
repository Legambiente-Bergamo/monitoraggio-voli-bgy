"""
bgy_core/bgy_update_rules.py - Arricchimento dati da regole JSON.
Versione 2.5.3
- Aggiunta mappa IATA -> ICAO caricata da config_rules_airlines.json
- Nuova funzione iata_to_icao() per il matching notturno
- extract_callsign_prefix gestisce prefissi misti lettera+numero (W4, W6, 3F, V7)
- get_airline() controlla anche i cargo prima di auto-aggiungere
"""
from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_config_manager import config_manager

logger = get_logger("UpdateRules")

_AIRLINES = {}
_COUNTRIES = {}
_AIRCRAFT_MODELS = {}
_CARGO_AIRLINES = {}
_IATA_TO_ICAO = {}
_SEATS = {}
_LOAD_FACTORS = {}
_DEFAULT_LOAD_FACTOR = 0.85
_NOISE_STATIONS = {}
_NOISE_CURVES = {}
_DEFAULT_NOISE_CURVES = {}


def load_rules():
    """Ricarica le regole da config_manager e ripopola le cache locali."""
    global _AIRLINES, _COUNTRIES, _AIRCRAFT_MODELS, _CARGO_AIRLINES, _IATA_TO_ICAO
    global _SEATS, _LOAD_FACTORS, _DEFAULT_LOAD_FACTOR
    global _NOISE_STATIONS, _NOISE_CURVES, _DEFAULT_NOISE_CURVES

    raw_airlines = dict(config_manager.get_airlines())

    # Estrai le sezioni speciali
    _IATA_TO_ICAO = raw_airlines.pop("_iata_to_icao", {})
    _CARGO_AIRLINES = raw_airlines.pop("_cargo_airlines", {})
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
# IATA / ICAO
# -----------------------------------------------------------------------------

def iata_to_icao(iata_code):
    """
    Converte un codice IATA (2 caratteri) in codice ICAO (3 lettere).
    Ritorna None se la conversione non è disponibile.
    """
    if not iata_code or not isinstance(iata_code, str):
        return None
    code = iata_code.strip().upper()
    return _IATA_TO_ICAO.get(code)


def extract_callsign_prefix(callsign, length=2):
    """
    Estrae il prefisso di un callsign, gestendo sia prefissi alfabetici puri
    (es. 'FR', 'RYR') che prefissi misti lettera+numero (es. 'W4', 'W6', '3F', 'V7').

    Esempi:
      extract_callsign_prefix('FR 3480', 2)   -> 'FR'
      extract_callsign_prefix('W4 3136', 2)   -> 'W4'
      extract_callsign_prefix('RYR115D', 3)   -> 'RYR'
      extract_callsign_prefix('UNKNOWN', 3)   -> 'UNK'
    """
    if not callsign or not isinstance(callsign, str):
        return ""
    s = callsign.strip().upper().replace(" ", "")
    if len(s) < length:
        return ""
    prefix = s[:length]
    # Verifica: almeno una lettera e solo caratteri alfanumerici
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

    # 1. Match nei passeggeri
    for prefix in (prefix3, prefix2):
        if prefix in _AIRLINES:
            return _AIRLINES[prefix]

    # 2. Match nei cargo (NON aggiungere ai passeggeri)
    for prefix in (prefix3, prefix2):
        if prefix in _CARGO_AIRLINES:
            return _CARGO_AIRLINES[prefix]

    # 3. Auto-add
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
    prefix3 = callsign.strip().upper()[:3]
    prefix2 = callsign.strip().upper()[:2]
    for prefix in (prefix3, prefix2):
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