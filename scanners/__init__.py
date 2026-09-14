"""
scanners - Moduli per l'acquisizione dei dati.
"""
from .bgy_scanner_day import run_scan as run_day_scan
from .bgy_scanner_night import run_night_scan

__all__ = [
    'run_day_scan',
    'run_night_scan'
]