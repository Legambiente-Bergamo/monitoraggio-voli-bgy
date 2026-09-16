"""
bgy_core - Pacchetto funzionalità di base della BGY Monitoring Suite.
Versione 2.5.0
- rimossi get_noise_impact e get_noise_category (dead code)
"""
from bgy_core.bgy_config_manager import config_manager
from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import ensure_directories
from bgy_core.bgy_update_rules import (
    load_rules,
    reload_rules,
    get_airline,
    get_country,
    get_aircraft_model,
    is_cargo_flight,
    get_seats,
    get_load_factor,
    estimate_passengers,
    get_noise_stations,
    get_noise_curves,
)

__all__ = [
    "config_manager",
    "get_logger",
    "ensure_directories",
    "load_rules",
    "reload_rules",
    "get_airline",
    "get_country",
    "get_aircraft_model",
    "is_cargo_flight",
    "get_seats",
    "get_load_factor",
    "estimate_passengers",
    "get_noise_stations",
    "get_noise_curves",
]