"""
scanners - Moduli per l'acquisizione dei dati.
Versione 1.1.0

- bgy_scanner_radar.py sostituisce bgy_scanner_night.py (h24 multi-fonte).
- Alias run_night_scan -> run_radar_scan per retrocompatibilità con la GUI
  (verrà rimosso quando la GUI sarà aggiornata).
"""
from .bgy_scanner_day import run_scan as run_day_scan
from .bgy_scanner_radar import run_radar_scan

# Alias retrocompatibile: la GUI importa ancora run_night_scan.
# Quando bgy_gui_dashboard.py sarà aggiornato per usare run_radar_scan,
# questa riga può essere rimossa.
run_night_scan = run_radar_scan

__all__ = [
    'run_day_scan',
    'run_radar_scan',
    'run_night_scan',
]