"""
scanners - Moduli per l'acquisizione dei dati.
Versione 1.2.0

- bgy_scanner_day.py: scansione SACBO (con failover Avionio).
- bgy_scanner_radar.py: radar h24 multi-fonte (adsb.lol → adsb.fi → OpenSky).
- bgy_scanner_alt.py: Avionio (confronto + fallback).

Nota: bgy_scanner_night.py è stato rimosso. Il suo ruolo è stato
assorbito da bgy_scanner_radar.py (v2.9.5).
"""
from .bgy_scanner_day import run_scan as run_day_scan
from .bgy_scanner_radar import run_radar_scan

__all__ = [
    'run_day_scan',
    'run_radar_scan',
]