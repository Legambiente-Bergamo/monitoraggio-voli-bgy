"""
bgy_core/bgy_charts.py - Generazione figure matplotlib per la GUI.
Versione 2.5.1

Ogni funzione ritorna una matplotlib.figure.Figure (non salva su file).
Accettano filtri opzionali:
  - movement_filter: 'all' | 'departures' | 'arrivals'
  - flight_type_filter: 'all' | 'pax' | 'cargo'

I filtri agiscono sul DataFrame in ingresso (già arricchito dalla GUI).
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
from datetime import datetime

from bgy_core.bgy_logger import get_logger

logger = get_logger("Charts")


# =============================================================================
# PALETTE COLORI
# =============================================================================

COLOR_PRIMARY = '#1a2a6c'
COLOR_DAILY = '#3498db'
COLOR_NIGHTLY = '#8e44ad'
COLOR_ORANGE = '#e67e22'
COLOR_PURPLE = '#9b59b6'
COLOR_GRAY = '#95a5a6'
COLOR_RED = '#e74c3c'
COLOR_GREEN = '#2ecc71'
COLOR_YELLOW = '#f39c12'


# =============================================================================
# APPLICAZIONE FILTRI
# =============================================================================

def apply_filters(df, report_type, movement_filter='all', flight_type_filter='all'):
    """
    Applica i filtri movimento e tipo volo al DataFrame.
    Ritorna il DataFrame filtrato.
    """
    if df is None or df.empty:
        return df

    # Filtro movimento
    if movement_filter == 'all':
        pass  # nessun filtro aggiuntivo
    elif movement_filter == 'departures':
        if report_type == 'daily':
            df = df[df['tipo_movimento'].astype(str).str.startswith('D')]
        else:
            df = df[df['fase_volo'].astype(str).isin(['Decollo'])]
    elif movement_filter == 'arrivals':
        if report_type == 'daily':
            df = df[df['tipo_movimento'].astype(str).str.startswith('A')]
        else:
            df = df[df['fase_volo'].astype(str).isin(['Atterraggio', 'Avvicinamento'])]

    # Filtro tipo volo (solo notturno)
    if flight_type_filter != 'all' and report_type == 'nightly':
        if 'tipo_movimento' in df.columns:
            if flight_type_filter == 'pax':
                df = df[df['tipo_movimento'].astype(str).str.startswith('Passeggeri')]
            elif flight_type_filter == 'cargo':
                df = df[df['tipo_movimento'].astype(str).str.startswith('Cargo')]

    return df


def apply_default_night_filter(df, report_type):
    """
    Per il notturno, esclude sorvoli/transiti anche quando movement_filter='all'.
    Tiene solo: Atterraggio, Decollo, Avvicinamento.
    """
    if report_type != 'nightly' or df is None or df.empty:
        return df
    if 'fase_volo' not in df.columns:
        return df
    return df[df['fase_volo'].astype(str).isin(
        ['Atterraggio', 'Decollo', 'Avvicinamento'])]


# =============================================================================
# GRAFICO 1 - MOVIMENTI GIORNALIERI
# =============================================================================

def chart_daily_flights(df, year_month="", report_type='daily',
                        movement_filter='all', flight_type_filter='all'):
    """Bar chart: numero di voli per giorno nel periodo."""
    try:
        df = apply_default_night_filter(df, report_type)
        df = apply_filters(df, report_type, movement_filter, flight_type_filter)

        if df is None or df.empty or 'data_report' not in df.columns:
            logger.warning("chart_daily_flights: dati insufficienti")
            return None

        daily_counts = df.groupby('data_report').size().reset_index(name='totale_voli')
        if daily_counts.empty:
            return None

        fig, ax = plt.subplots(figsize=(12, 6))
        color = COLOR_DAILY if report_type == 'daily' else COLOR_NIGHTLY
        if movement_filter == 'departures':
            color = COLOR_ORANGE
        elif movement_filter == 'arrivals':
            color = COLOR_GREEN

        ax.bar(daily_counts['data_report'], daily_counts['totale_voli'],
               color=color, alpha=0.85, edgecolor='white')

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))

        titolo = "Andamento Voli Giornalieri" if report_type == 'daily' else "Andamento Voli Notturni"
        if movement_filter == 'departures':
            titolo += " - Decolli"
        elif movement_filter == 'arrivals':
            titolo += " - Atterraggi"
        if flight_type_filter == 'pax':
            titolo += " (Passeggeri)"
        elif flight_type_filter == 'cargo':
            titolo += " (Cargo)"

        ax.set_title(f"{titolo} - {year_month}", fontsize=14, fontweight='bold')
        ax.set_xlabel('Data', fontsize=11)
        ax.set_ylabel('Numero Voli', fontsize=11)
        ax.grid(axis='y', alpha=0.3)

        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        plt.tight_layout()
        return fig
    except Exception as e:
        logger.error(f"Errore chart_daily_flights: {e}")
        return None


# =============================================================================
# GRAFICO 2 - RITARDI (daily) / FASI DI VOLO (nightly)
# =============================================================================

def chart_daily_delays(df, year_month="", report_type='daily',
                       movement_filter='all', flight_type_filter='all'):
    """Ritardo medio giornaliero (daily) o distribuzione fasi (nightly)."""
    try:
        df = apply_default_night_filter(df, report_type)
        df = apply_filters(df, report_type, movement_filter, flight_type_filter)

        if df is None or df.empty:
            return None

        if report_type == 'daily':
            if 'minuti_ritardo' not in df.columns:
                return None
            delay_df = df[df['minuti_ritardo'].notna()].copy()
            if delay_df.empty:
                return None

            daily_delays = delay_df.groupby('data_report').agg(
                ritardo_medio=('minuti_ritardo', 'mean')
            ).reset_index()

            fig, ax = plt.subplots(figsize=(12, 6))
            colors = [COLOR_RED if x > 15 else COLOR_YELLOW if x > 5 else COLOR_GREEN
                      for x in daily_delays['ritardo_medio']]
            ax.bar(daily_delays['data_report'], daily_delays['ritardo_medio'],
                   color=colors, alpha=0.85, edgecolor='white')
            ax.axhline(y=15, color=COLOR_RED, linestyle='--', linewidth=2,
                       label='Soglia ritardo (15 min)')
            titolo = f"Ritardi Medi Giornalieri - {year_month}"
            if movement_filter == 'departures':
                titolo += " - Decolli"
            elif movement_filter == 'arrivals':
                titolo += " - Atterraggi"
            ax.set_title(titolo, fontsize=14, fontweight='bold')
            ax.set_xlabel('Data', fontsize=11)
            ax.set_ylabel('Ritardo Medio (minuti)', fontsize=11)
            ax.legend()
            ax.grid(axis='y', alpha=0.3)

        else:
            # Notturno: distribuzione fasi di volo
            if 'fase_volo' not in df.columns:
                return None
            pivot = df.groupby(['data_report', 'fase_volo']).size().unstack(fill_value=0)
            if pivot.empty:
                return None

            fig, ax = plt.subplots(figsize=(12, 6))
            bottom = None
            colori = {
                'Atterraggio': COLOR_DAILY,
                'Decollo': COLOR_ORANGE,
                'Avvicinamento': COLOR_PURPLE,
                'Sorvolo': COLOR_GRAY,
                'Non rilevato': '#bdc3c7',
            }
            for fase in pivot.columns:
                vals = pivot[fase].values
                ax.bar(pivot.index, vals, bottom=bottom,
                       label=fase, color=colori.get(fase, '#7f8c8d'),
                       alpha=0.85, edgecolor='white')
                bottom = vals if bottom is None else bottom + vals
            titolo = f"Distribuzione Fasi di Volo - {year_month}"
            if flight_type_filter == 'pax':
                titolo += " (Passeggeri)"
            elif flight_type_filter == 'cargo':
                titolo += " (Cargo)"
            ax.set_title(titolo, fontsize=14, fontweight='bold')
            ax.set_xlabel('Data', fontsize=11)
            ax.set_ylabel('Numero Voli', fontsize=11)
            ax.legend()
            ax.grid(axis='y', alpha=0.3)

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        plt.tight_layout()
        return fig
    except Exception as e:
        logger.error(f"Errore chart_daily_delays: {e}")
        return None


# =============================================================================
# GRAFICO 3 - TOP COMPAGNIE
# =============================================================================

def chart_airlines(df, year_month="", report_type='daily',
                   movement_filter='all', flight_type_filter='all'):
    """Bar chart orizzontale: top 10 compagnie aeree."""
    try:
        df = apply_default_night_filter(df, report_type)
        df = apply_filters(df, report_type, movement_filter, flight_type_filter)

        if df is None or df.empty or 'compagnia_aerea' not in df.columns:
            logger.warning("chart_airlines: dati insufficienti")
            return None

        airline_counts = df['compagnia_aerea'].value_counts().head(10)
        if airline_counts.empty:
            return None

        fig, ax = plt.subplots(figsize=(10, 6))
        cmap = plt.cm.Blues if report_type == 'daily' else plt.cm.Purples
        colors = cmap(np.linspace(0.4, 0.9, len(airline_counts)))[::-1]
        bars = ax.barh(airline_counts.index, airline_counts.values,
                       color=colors, edgecolor='white')
        for bar, value in zip(bars, airline_counts.values):
            ax.text(value + 0.5, bar.get_y() + bar.get_height()/2,
                    str(value), va='center', fontsize=10, fontweight='bold')

        tipo = "Compagnie Aeree" if report_type == 'daily' else "Compagnie Aeree (Notturno)"
        if movement_filter == 'departures':
            tipo += " - Decolli"
        elif movement_filter == 'arrivals':
            tipo += " - Atterraggi"
        if flight_type_filter == 'pax':
            tipo += " (Passeggeri)"
        elif flight_type_filter == 'cargo':
            tipo += " (Cargo)"

        ax.set_title(f"Top 10 {tipo} - {year_month}",
                     fontsize=14, fontweight='bold')
        ax.set_xlabel('Numero Voli', fontsize=11)
        ax.set_ylabel('Compagnia', fontsize=11)
        ax.grid(axis='x', alpha=0.3)
        plt.tight_layout()
        return fig
    except Exception as e:
        logger.error(f"Errore chart_airlines: {e}")
        return None


# =============================================================================
# GRAFICO 4 - TOP DESTINAZIONI
# =============================================================================

def chart_destinations(df, year_month="", report_type='daily',
                       movement_filter='all', flight_type_filter='all'):
    """Bar chart orizzontale: top 10 destinazioni."""
    try:
        df = apply_default_night_filter(df, report_type)
        df = apply_filters(df, report_type, movement_filter, flight_type_filter)

        if df is None or df.empty:
            return None

        if report_type == 'daily' and 'destinazione_origine' in df.columns:
            col = 'destinazione_origine'
        elif 'destinazione_finale' in df.columns:
            col = 'destinazione_finale'
        elif 'destinazione_origine' in df.columns:
            col = 'destinazione_origine'
        else:
            logger.warning("chart_destinations: nessuna colonna destinazione")
            return None

        dest_counts = df[col].value_counts().head(10)
        if dest_counts.empty:
            return None

        fig, ax = plt.subplots(figsize=(10, 6))
        cmap = plt.cm.Oranges if report_type == 'daily' else plt.cm.Reds
        colors = cmap(np.linspace(0.3, 0.9, len(dest_counts)))[::-1]
        bars = ax.barh(dest_counts.index, dest_counts.values,
                       color=colors, edgecolor='white')
        for bar, value in zip(bars, dest_counts.values):
            ax.text(value + 0.5, bar.get_y() + bar.get_height()/2,
                    str(value), va='center', fontsize=10, fontweight='bold')

        titolo = f"Top 10 Destinazioni - {year_month}"
        if movement_filter == 'departures':
            titolo += " - Decolli"
        elif movement_filter == 'arrivals':
            titolo += " - Atterraggi"
        if flight_type_filter == 'pax':
            titolo += " (Passeggeri)"
        elif flight_type_filter == 'cargo':
            titolo += " (Cargo)"

        ax.set_title(titolo, fontsize=14, fontweight='bold')
        ax.set_xlabel('Numero Voli', fontsize=11)
        ax.set_ylabel('Destinazione', fontsize=11)
        ax.grid(axis='x', alpha=0.3)
        plt.tight_layout()
        return fig
    except Exception as e:
        logger.error(f"Errore chart_destinations: {e}")
        return None


# =============================================================================
# MAPPA GRAFICI DISPONIBILI
# =============================================================================

CHART_FUNCTIONS = {
    'movimenti': {
        'label': "Movimenti giornalieri",
        'func': chart_daily_flights,
        'description': "Numero di voli per giorno nel periodo selezionato",
    },
    'ritardi_fasi': {
        'label': "Ritardi (diurno) / Fasi di volo (notturno)",
        'func': chart_daily_delays,
        'description': "Ritardo medio giornaliero o distribuzione fasi di volo",
    },
    'compagnie': {
        'label': "Top 10 compagnie",
        'func': chart_airlines,
        'description': "Compagnie con più voli nel periodo",
    },
    'destinazioni': {
        'label': "Top 10 destinazioni",
        'func': chart_destinations,
        'description': "Destinazioni con più voli nel periodo",
    },
}