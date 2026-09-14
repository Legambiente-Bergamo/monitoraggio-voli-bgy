"""
bgy_utils_noise.py - Stima rumore aeromobili alle centraline ARPA.
Legge configurazione da core.bgy_update_rules (file unificato).
"""
from math import radians, sin, cos, sqrt, atan2

from core.bgy_logger import get_logger
from core import get_noise_stations, get_noise_curves, load_rules

logger = get_logger("NoiseEstimator")


def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    lat1_r, lon1_r = radians(lat1), radians(lon1)
    lat2_r, lon2_r = radians(lat2), radians(lon2)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = sin(dlat/2)**2 + cos(lat1_r) * cos(lat2_r) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))


def slant_distance(lat, lon, alt_ft, st_lat, st_lon):
    ground = haversine(lat, lon, st_lat, st_lon)
    alt_km = (alt_ft or 0) * 0.0003048
    return sqrt(ground**2 + alt_km**2)


def _interpolate(dist_km, curve):
    distanze = curve.get("distanze", [])
    valori = curve.get("valori", [])
    if not distanze or not valori:
        return None
    dist_m = dist_km * 1000
    if dist_m <= distanze[0]:
        return valori[0]
    if dist_m >= distanze[-1]:
        return valori[-1]
    for i in range(len(distanze) - 1):
        if distanze[i] <= dist_m <= distanze[i+1]:
            f = (dist_m - distanze[i]) / (distanze[i+1] - distanze[i])
            return round(valori[i] + f * (valori[i+1] - valori[i]), 1)
    return None


def estimate_noise(model, phase, aircraft_lat, aircraft_lon, aircraft_alt_ft):
    """
    Ritorna {nome_centralina: {"distanza_km": ..., "db_stimato": ...}}.
    """
    stations = get_noise_stations()
    if not stations:
        load_rules()
        stations = get_noise_stations()

    curves = get_noise_curves(model)

    phase_map = {
        "Atterraggio": "atterraggio",
        "Decollo": "decollo",
        "Avvicinamento": "atterraggio",
        "Sorvolo": "sorvolo",
    }
    phase_key = phase_map.get(phase, "sorvolo")
    curve = curves.get(phase_key, {})

    results = {}
    for name, st in stations.items():
        d = slant_distance(aircraft_lat, aircraft_lon, aircraft_alt_ft,
                           st["lat"], st["lon"])
        db = _interpolate(d, curve)
        if db is not None:
            results[name] = {"distanza_km": round(d, 2), "db_stimato": db}
    return results


def get_max_noise(model, phase, lat, lon, alt_ft):
    """Ritorna il dB massimo tra tutte le centraline."""
    noise = estimate_noise(model, phase, lat, lon, alt_ft)
    if not noise:
        return 0
    return max((v["db_stimato"] for v in noise.values()), default=0)