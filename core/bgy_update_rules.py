"""
core/bgy_update_rules.py - Arricchimento dati da file JSON.
Auto-classificazione destinazioni e compagnie cargo.
Esteso v2.3.5: posti, load factor, centraline rumore, curve NPD.
"""
import os
import json
from core.bgy_logger import get_logger
from core.bgy_paths import (
    RULES_AIRLINES, RULES_COUNTRIES,
    RULES_AIRCRAFT_MODELS, RULES_NOISE_IMPACT
)

logger = get_logger("UpdateRules")

# Cache globale
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

_NEW_DESTINATIONS_BUFFER = set()


# -----------------------------------------------------------------------------
# LOAD / RELOAD
# -----------------------------------------------------------------------------

def _load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Errore lettura {path}: {e}")
        return default if default is not None else {}


def load_rules():
    """Carica tutte le regole dai file JSON."""
    global _AIRLINES, _COUNTRIES, _AIRCRAFT_MODELS, _CARGO_AIRLINES
    global _SEATS, _LOAD_FACTORS, _DEFAULT_LOAD_FACTOR
    global _NOISE_STATIONS, _NOISE_CURVES, _DEFAULT_NOISE_CURVES

    # --- Airlines ---
    raw_airlines = _load_json(RULES_AIRLINES)
    _CARGO_AIRLINES = raw_airlines.pop("_cargo_airlines", {})
    _AIRLINES = raw_airlines

    # --- Countries ---
    _COUNTRIES = _load_json(RULES_COUNTRIES)

    # --- Aircraft models (con _seats e _load_factors) ---
    raw_models = _load_json(RULES_AIRCRAFT_MODELS)
    _SEATS = raw_models.pop("_seats", {})
    lf_data = raw_models.pop("_load_factors", {})
    _DEFAULT_LOAD_FACTOR = lf_data.pop("_default", 0.85)
    _LOAD_FACTORS = lf_data
    _AIRCRAFT_MODELS = raw_models

    # --- Noise (con _stations e _curves) ---
    raw_noise = _load_json(RULES_NOISE_IMPACT)
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
    load_rules()
    logger.info("🔄 Regole ricaricate")


# -----------------------------------------------------------------------------
# AIRLINE
# -----------------------------------------------------------------------------

def get_airline(callsign):
    if not callsign or not isinstance(callsign, str):
        return "N/D"
    prefix3 = callsign.strip().upper()[:3]
    prefix2 = callsign.strip().upper()[:2]
    for prefix in (prefix3, prefix2):
        if prefix in _AIRLINES:
            return _AIRLINES[prefix]
    _auto_add_airline(prefix3)
    return f"Compagnia {prefix3}"


def _auto_add_airline(prefix):
    if not prefix or len(prefix) < 2:
        return
    if prefix in _AIRLINES:
        return
    _AIRLINES[prefix] = f"Compagnia {prefix}"
    try:
        full_data = _load_json(RULES_AIRLINES)
        full_data[prefix] = f"Compagnia {prefix}"
        with open(RULES_AIRLINES, "w", encoding="utf-8") as f:
            json.dump(full_data, f, ensure_ascii=False, indent=4)
        logger.info(f"📝 Nuova compagnia aggiunta: {prefix}")
    except Exception as e:
        logger.error(f"Errore salvataggio compagnia {prefix}: {e}")


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
    _auto_add_destination(dest_clean)
    return "DA CLASSIFICARE"


def _auto_add_destination(destination):
    if not destination or len(destination) < 2:
        return
    if destination.upper() in _COUNTRIES or destination in _COUNTRIES:
        return
    if destination in _NEW_DESTINATIONS_BUFFER:
        return
    _NEW_DESTINATIONS_BUFFER.add(destination)
    _COUNTRIES[destination.upper()] = "DA CLASSIFICARE"
    try:
        with open(RULES_COUNTRIES, "r", encoding="utf-8") as f:
            full_data = json.load(f)
        full_data[destination.upper()] = "DA CLASSIFICARE"
        with open(RULES_COUNTRIES, "w", encoding="utf-8") as f:
            json.dump(full_data, f, ensure_ascii=False, indent=4)
        logger.info(f"📝 Nuova destinazione aggiunta: {destination} (DA CLASSIFICARE)")
    except Exception as e:
        logger.error(f"Errore salvataggio destinazione {destination}: {e}")


# -----------------------------------------------------------------------------
# AIRCRAFT MODEL
# -----------------------------------------------------------------------------

def get_aircraft_model(callsign):
    if not callsign or not isinstance(callsign, str):
        return "N/D"
    prefix3 = callsign.strip().upper()[:3]
    prefix2 = callsign.strip().upper()[:2]
    for prefix in (prefix3, prefix2):
        if prefix in _AIRCRAFT_MODELS:
            return _AIRCRAFT_MODELS[prefix]
    return "N/D"


# -----------------------------------------------------------------------------
# PAX (posti + load factor)
# -----------------------------------------------------------------------------

def get_seats(model):
    """Restituisce i posti del modello."""
    if not model or model == "N/D":
        return 0
    data = _SEATS.get(model, {})
    return data.get("posti_default", 0)


def get_load_factor(airline_code):
    """Restituisce il load factor per compagnia (default 0.85)."""
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

def get_noise_impact(model, phase):
    """Retro-compatibilità: ritorna dB per modello e fase (senza distanza)."""
    curves = _NOISE_CURVES.get(model, _DEFAULT_NOISE_CURVES)
    phase_key = {"Atterraggio": "atterraggio", "Decollo": "decollo",
                 "Avvicinamento": "atterraggio", "Sorvolo": "sorvolo"}.get(phase, "sorvolo")
    curve = curves.get(phase_key, {})
    valori = curve.get("valori", [])
    return valori[2] if len(valori) > 2 else None  # valore a 1000m


def get_noise_category(decibel):
    if decibel is None:
        return "N/D"
    if decibel < 70:
        return "Bassa"
    elif decibel < 80:
        return "Media"
    elif decibel < 90:
        return "Alta"
    else:
        return "Molto Alta"


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