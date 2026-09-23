"""
bgy_core/bgy_charts.py - Generazione figure matplotlib per la GUI.
Versione 2.5.4

Ogni funzione ritorna una matplotlib.figure.Figure (non salva su file).

Filtri supportati (v2.5.4):
- movement_filter: 'all' | 'departures' | 'arrivals'
- flight_type_filter: LISTA di categorie, es.
    ['Passeggeri', 'Cargo', 'Charter']
    ['Passeggeri']
    ['Cargo', 'Charter', 'Passeggeri (radar)', 'Non identificato']
  Se None o lista vuota → tutte le categorie.

Novità v2.5.4:
- flight_type_filter ora è una LISTA (compatibile col nuovo modello
  a 5 categorie introdotto in bgy_report_night v2.8.x).
- Retrocompatibile con la vecchia stringa ('all', 'pax', 'cargo').

Fix v2.5.3:
- apply_default_night_filter non esclude più i voli 'solo schedulato'.
- chart_airlines non esclude più i placeholder.
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
# COSTANTI
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

# Categorie notturne (v2.8.x)
CATEGORY_PAX = 'Passeggeri'
CATEGORY_CARGO = 'Cargo'
CATEGORY_CHARTER = 'Charter'
CATEGORY_PAX_RADAR = 'Passeggeri (radar)'
CATEGORY_NON_ID = 'Non identificato'

ALL_NIGHT_CATEGORIES = [
    CATEGORY_PAX,
    CATEGORY_CARGO,
    CATEGORY_CHARTER,
    CATEGORY_PAX_RADAR,
    CATEGORY_NON_ID,
]


# =============================================================================
# FILTRI
# =============================================================================

def _normalize_flight_type_filter(flight_type_filter):
    """
    Normalizza flight_type_filter in una lista di categorie.

    Accetta:
    - None o [] → tutte le categorie
    - 'all' → tutte
    - 'pax' → ['Passeggeri'] (retrocompatibilità)
    - 'cargo' → ['Cargo'] (retrocompatibilità)
    - 'charter' → ['Charter']
    - lista di stringhe → normalizzata
    """
    if flight_type_filter is None:
        return None
    if isinstance(flight_type_filter, str):
        s = flight_type_filter.strip().lower()
        if s in ('all', ''):
            return None
        if s == 'pax':
            return [CATEGORY_PAX, CATEGORY_PAX_RADAR]
        if s == 'cargo':
            return [CATEGORY_CARGO]
        if s == 'charter':
            return [CATEGORY_CHARTER]
        # singola categoria passata come stringa
        return [flight_type_filter]
    if isinstance(flight_type_filter, (list, tuple, set)):
        result = [str(x) for x in flight_type_filter if x]
        return result if result else None
    return None


def _match_tipo_movimento(tipo_movimento, categorie):
    """
    Ritorna True se `tipo_movimento` appartiene a una delle categorie.
    Gestisce il prefisso "Cargo (Nome)" e "Charter (Nome)".
    """
    if not isinstance(tipo_movimento, str):
        return False
    t = tipo_movimento.strip()

    for cat in categorie:
        if cat == CATEGORY_PAX:
            if t == 'Passeggeri' or t.startswith('Passeggeri (schedulato'):
                return True
        elif cat == CATEGORY_CARGO:
            if t.startswith('Cargo'):
                return True
        elif cat == CATEGORY_CHARTER:
            if t.startswith('Charter'):
                return True
        elif cat == CATEGORY_PAX_RADAR:
            if t == 'Passeggeri (radar)':
                return True
        elif cat == CATEGORY_NON_ID:
            if t == 'Non identificato':
                return True
    return False


def apply_filters(df, report_type, movement_filter='all', flight_type_filter=None):
    """
    Applica i filtri movimento e tipo volo al DataFrame.
    """
    if df is None or df.empty:
        return df

    # --- Filtro movimento ---
    if movement_filter == 'all':
        pass
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

    # --- Filtro tipo volo ---
    if report_type == 'nightly':
        categorie = _normalize_flight_type_filter(flight_type_filter)
        if categorie is not None and 'tipo_movimento' in df.columns:
            mask = df['tipo_movimento'].apply(
                lambda x: _match_tipo_movimento(x, categorie)
            )
            df = df[mask]

    return df


def apply_default_night_filter(df, report_type, movement_filter='all'):
    """
    Per il notturno, esclude sorvoli/transiti SOLO se l'utente ha
    esplicitamente chiesto decolli o atterraggi.
    """
    if report_type != 'nightly' or df is None or df.empty:
        return df
    if movement_filter == 'all':
        return df
    if 'fase_volo' not in df.columns:
        return df
    return df[df['fase_volo'].astype(str).isin(
        ['Atterraggio', 'Decollo', 'Avvicinamento'])]


# =============================================================================
# GRAFICO 1 - MOVIMENTI GIORNALIERI
# =============================================================================

def chart_daily_flights(df, year_month="", report_type='daily',
                        movement_filter='all', flight_type_filter=None):
    """Bar chart: numero di voli per giorno nel periodo."""
    try:
        df = apply_default_night_filter(df, report_type, movement_filter)
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
        titolo += _suffix_categorie(flight_type_filter)

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
                       movement_filter='all', flight_type_filter=None):
    """Ritardo medio giornaliero (daily) o distribuzione fasi (nightly)."""
    try:
        df = apply_default_night_filter(df, report_type, movement_filter)
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

            df_viz = df.copy()
            df_viz['fase_volo'] = df_viz['fase_volo'].fillna('Non rilevato')

            pivot = df_viz.groupby(['data_report', 'fase_volo']).size().unstack(fill_value=0)
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
            titolo += _suffix_categorie(flight_type_filter)
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
                   movement_filter='all', flight_type_filter=None):
    """Bar chart orizzontale: top 10 compagnie aeree."""
    try:
        df = apply_default_night_filter(df, report_type, movement_filter)
        df = apply_filters(df, report_type, movement_filter, flight_type_filter)

        if df is None or df.empty or 'compagnia_aerea' not in df.columns:
            logger.warning("chart_airlines: dati insufficienti")
            return None

        # Escludi solo i valori vuoti/N/D
        df = df[df['compagnia_aerea'].notna()]
        df = df[~df['compagnia_aerea'].astype(str).isin(['', 'nan', 'None', 'N/D'])]

        if df.empty:
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
        tipo += _suffix_categorie(flight_type_filter)

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
                       movement_filter='all', flight_type_filter=None):
    """Bar chart orizzontale: top 10 destinazioni."""
    try:
        df = apply_default_night_filter(df, report_type, movement_filter)
        df = apply_filters(df, report_type, movement_filter, flight_type_filter)

        if df is None or df.empty:
            return None

        # Per il notturno: prendi solo i voli schedulati (destinazione reale)
        if report_type == 'nightly':
            if 'is_scheduled' not in df.columns:
                return None
            df = df[df['is_scheduled'] == True]

        if df.empty:
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

        df = df[df[col].notna()]
        df = df[~df[col].astype(str).isin(['', 'N/D', 'nan', 'None'])]

        if df.empty:
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
        titolo += _suffix_categorie(flight_type_filter)

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
# UTILITY
# =============================================================================

def _suffix_categorie(flight_type_filter):
    """Costruisce il suffisso del titolo in base alle categorie selezionate."""
    if flight_type_filter is None:
        return ""
    if isinstance(flight_type_filter, str):
        if flight_type_filter.lower() in ('all', ''):
            return ""
        return f" [{flight_type_filter}]"
    if isinstance(flight_type_filter, (list, tuple, set)):
        cats = [str(x) for x in flight_type_filter if x]
        if not cats:
            return ""
        # Se sono tutte le categorie, non mostrare nulla
        if set(cats) >= set(ALL_NIGHT_CATEGORIES):
            return ""
        return f" [{' + '.join(cats)}]"
    return ""


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