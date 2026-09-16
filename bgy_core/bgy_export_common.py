"""
bgy_core/bgy_export_common.py - Funzioni comuni per gli exporter.
Versione 2.5.0

Centralizza:
  - calcolo statistiche da un DataFrame
  - selezione colonne da mostrare (config_data.json → export.columns)
  - limite righe (config_data.json → export.max_rows)
  - tema colori (config_data.json → export.theme)
  - footer comune
"""
import os
from datetime import datetime

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_config_manager import config_manager
from bgy_core.bgy_version import version_string

logger = get_logger("ExportCommon")


def get_theme():
    cfg = config_manager.get_export_config()
    return cfg.get("theme", {
        "primary_color": "1a2a6c",
        "text_color": "FFFFFF",
        "border_color": "grey",
        "alternate_row_color": "f0f4f8",
    })


def get_columns(report_type):
    """Ritorna la lista di colonne da mostrare per un tipo di report."""
    cfg = config_manager.get_export_config()
    cols_by_type = cfg.get("columns", {})
    cols = cols_by_type.get(report_type) or cols_by_type.get("daily") or []
    return list(cols)


def get_max_rows(fmt):
    """Ritorna il numero massimo di righe per un formato. 0 = nessun limite."""
    cfg = config_manager.get_export_config()
    max_rows = cfg.get("max_rows", {})
    try:
        return int(max_rows.get(fmt, 0))
    except (ValueError, TypeError):
        return 0


def get_available_columns(df, report_type):
    """Ritorna solo le colonne configurate che esistono nel DataFrame."""
    wanted = get_columns(report_type)
    return [c for c in wanted if c in df.columns]


def compute_stats(df, report_type):
    """Ritorna una lista di tuple (label, valore) per il riepilogo."""
    stats = [("Totale Voli", len(df))]

    if 'tipo_movimento' in df.columns:
        atterraggi = len(df[df['tipo_movimento'].str.contains('Atterraggio|A', na=False)])
        decolli = len(df[df['tipo_movimento'].str.contains('Decollo|D', na=False)])
        if atterraggi or decolli:
            stats.append(("Atterraggi", atterraggi))
            stats.append(("Decolli", decolli))

    if 'minuti_ritardo' in df.columns:
        ritardi = len(df[df['minuti_ritardo'] > 15])
        in_orario = len(df[df['minuti_ritardo'] <= 15])
        try:
            ritardo_medio = df['minuti_ritardo'].mean()
        except Exception:
            ritardo_medio = 0
        stats.append(("Voli in Ritardo (>15m)", ritardi))
        stats.append(("Voli in Orario", in_orario))
        stats.append(("Ritardo Medio (min)", f"{ritardo_medio:.1f}"))

    if 'stima_passeggeri' in df.columns:
        try:
            pax_tot = int(df['stima_passeggeri'].sum())
            stats.append(("PAX stimati", pax_tot))
        except Exception:
            pass

    if 'stima_rumore_db' in df.columns:
        try:
            rumore_df = df[df['stima_rumore_db'] > 0]
            if len(rumore_df) > 0:
                stats.append(("Rumore max (dB)", int(rumore_df['stima_rumore_db'].max())))
        except Exception:
            pass

    return stats


def footer_lines():
    """Righe di footer comuni a tutti gli exporter."""
    now = datetime.now()
    return [
        f"Report generato automaticamente il {now.strftime('%d/%m/%Y %H:%M')}",
        "Dati elaborati da fonti pubbliche (SACBO e OpenSky Network)",
        version_string(),
    ]