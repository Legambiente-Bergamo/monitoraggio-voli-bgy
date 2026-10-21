"""
bgy_reports/bgy_report_common.py - Logica condivisa tra bgy_report_night e bgy_report_h24.
Versione 1.1.0

Novita v1.1.0 (21/10/2026, RADAR-14):
- propagate_runway_in_session riscritta: per ogni (callsign, direzione) seleziona
  UN SOLO record valido invece della moda. Criterio:
    * filtro stretto: quota_ft > pista_min_quota_ft (default 100),
      distanza_km < pista_max_distanza_km (default 5.0), pista != 'N/D'
    * se vuoto, rilassa a quota_ft > 0
    * se ancora vuoto, fallback a distanza < 5 senza filtro quota
    * se direzione == 'D': primo record (timestamp ASC)
    * se direzione == 'A': ultimo record (timestamp DESC)
    * la pista del record selezionato viene propagata a TUTTI i record
      dello stesso (callsign, direzione)
- Nuove chiavi config (scanner_radar):
    pista_min_quota_ft     (default 100)
    pista_max_distanza_km  (default 5.0)
- fill_unknown_runways_geometric invariata (identica a v1.0.0).

Novita v1.0.0 (21/10/2026, ARCH-01):
- Estrazione della logica pista da bgy_report_night v2.9.35 e bgy_report_h24 v1.0.7.
- Zero modifiche di comportamento rispetto a v2.9.35/v1.0.7.
"""
import pandas as pd

from bgy_core.bgy_config_manager import config_manager
from bgy_core.bgy_logger import get_logger

logger = get_logger("ReportCommon")

VALID_RUNWAYS = ('RWY 28', 'RWY 10')

_DEFAULT_PISTA_MIN_QUOTA_FT = 100
_DEFAULT_PISTA_MAX_DISTANZA_KM = 5.0
_MAX_QUOTA_FT = 2000


def _get_runway_cfg():
    """Ritorna i parametri pista da config (con fallback ai default)."""
    try:
        cfg = config_manager.get_scanner_radar_config() or {}
    except Exception:
        cfg = {}
    return {
        "pista_min_quota_ft": cfg.get("pista_min_quota_ft", _DEFAULT_PISTA_MIN_QUOTA_FT),
        "pista_max_distanza_km": cfg.get("pista_max_distanza_km", _DEFAULT_PISTA_MAX_DISTANZA_KM),
    }


def _clean_pista(p):
    if p is None:
        return ""
    try:
        if pd.isna(p):
            return ""
    except Exception:
        pass
    s = str(p).strip()
    return "" if s in ("", "N/D", "nan", "None", "NaN") else s


def _phase_to_dir(fase):
    f = str(fase).strip()
    return 'D' if f == 'Decollo' else ('A' if f in ('Atterraggio', 'Avvicinamento') else '')


def _select_valid_record(traccia, direzione, min_quota, max_dist):
    """
    Seleziona UN record valido per la pista, con criterio direzione-dipendente.

    Args:
        traccia: DataFrame dei record dello stesso (callsign, direzione),
                 già ordinati per timestamp ASC.
        direzione: 'D' o 'A'.
        min_quota: soglia quota minima (ft) per il filtro stretto.
        max_dist: soglia distanza massima (km).

    Returns:
        pista (str) o None se nessun record valido.
    """
    if traccia.empty:
        return None

    # Filtro stretto: quota > min_quota, distanza < max_dist, pista valida
    stretto = traccia[
        (traccia['_pista_clean'].isin(VALID_RUNWAYS))
        & (traccia['quota_ft'].fillna(0) > min_quota)
        & (traccia['distanza_km'].fillna(999) < max_dist)
    ]
    # Rilassato 1: quota > 0 (include takeoff roll / touchdown)
    if stretto.empty:
        stretto = traccia[
            (traccia['_pista_clean'].isin(VALID_RUNWAYS))
            & (traccia['quota_ft'].fillna(0) > 0)
            & (traccia['distanza_km'].fillna(999) < max_dist)
        ]
    # Rilassato 2: solo distanza < max_dist (include rullaggio, ultima spiaggia)
    if stretto.empty:
        stretto = traccia[
            (traccia['_pista_clean'].isin(VALID_RUNWAYS))
            & (traccia['distanza_km'].fillna(999) < max_dist)
        ]

    if stretto.empty:
        return None

    if direzione == 'D':
        # Primo record (timestamp minore) = più allineato alla pista al liftoff
        record = stretto.sort_values('timestamp', ascending=True).iloc[0]
    else:
        # Ultimo record (timestamp maggiore) = più allineato alla pista in finale corta
        record = stretto.sort_values('timestamp', ascending=True).iloc[-1]

    return record['_pista_clean']


def propagate_runway_in_session(radar_df, cfg=None):
    """
    Propaga la pista tra i record radar dello stesso callsign e direzione.

    Comportamento v1.1.0 (RADAR-14):
    - Per ogni (callsign, direzione) seleziona UN record valido con criterio
      "primo per D, ultimo per A" sui record filtrati per quota/distanza.
    - La pista del record selezionato viene propagata a tutti i record dello
      stesso (callsign, direzione).
    - Se nessun record valido, la pista resta invariata.

    Args:
        radar_df: DataFrame dei rilevamenti radar (deve avere le colonne
                  callsign, pista, fase_volo, quota_ft, distanza_km, timestamp).
        cfg: dict opzionale {pista_min_quota_ft, pista_max_distanza_km}.
             Se None, letto da config_manager con fallback ai default.

    Returns:
        DataFrame con la pista propagata.
    """
    if radar_df.empty or 'callsign' not in radar_df.columns or 'pista' not in radar_df.columns:
        return radar_df
    if cfg is None:
        cfg = _get_runway_cfg()

    min_quota = cfg.get("pista_min_quota_ft", _DEFAULT_PISTA_MIN_QUOTA_FT)
    max_dist = cfg.get("pista_max_distanza_km", _DEFAULT_PISTA_MAX_DISTANZA_KM)

    df = radar_df.copy()
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

    df['_pista_clean'] = df['pista'].apply(_clean_pista)
    df['_dir'] = df['fase_volo'].apply(_phase_to_dir)

    # Azzera la pista per i record a terra sotto la soglia (track inaffidabile)
    if 'quota_ft' in df.columns:
        df.loc[df['quota_ft'].fillna(0) < min_quota, '_pista_clean'] = ''

    # Per ogni (callsign, direzione): seleziona un record valido e propaga la pista
    pista_map = {}
    for (cs, d), group in df.groupby(
        [df['callsign'].str.strip().str.upper(), df['_dir']],
        sort=False
    ):
        if not cs or not d:
            continue
        pista_scelta = _select_valid_record(group, d, min_quota, max_dist)
        if pista_scelta:
            pista_map[(cs, d)] = pista_scelta

    n_filled = 0
    for idx, row in df.iterrows():
        if row['_pista_clean']:
            continue
        cs = str(row.get('callsign', '') or '').strip().upper()
        if not cs:
            continue
        d = row['_dir']
        if not d:
            continue
        p = pista_map.get((cs, d))
        if p:
            df.at[idx, 'pista'] = p
            n_filled += 1

    df = df.drop(columns=['_pista_clean', '_dir'])
    if n_filled:
        logger.debug(f"RADAR-14: propagate {n_filled} record (pista dedotta da record valido per direzione)")
    return df


def fill_unknown_runways_geometric(df, cfg=None):
    """
    Fallback geometrico per piste N/D sui decolli (RADAR-07).

    Comportamento v1.0.0 (invariato):
    - Solo per i decolli con pista N/D, distanza 2-5 km, rotta valida.
    - Track 70-170°  → RWY 10
    - Track 190-290° → RWY 28
    - Altrimenti resta N/D.
    """
    if df.empty or 'pista' not in df.columns or 'rotta_deg' not in df.columns:
        return df
    df = df.copy()
    mask = (
        (
            (df['pista'].isna())
            | (df['pista'].astype(str).str.strip() == 'N/D')
            | (df['pista'].astype(str).str.strip() == '')
        )
        & (df['fase_volo'] == 'Decollo')
        & (df['distanza_km'] > 2.0)
        & (df['distanza_km'] <= 5.0)
        & (df['rotta_deg'].notna())
    )
    n_filled = 0
    for idx, row in df[mask].iterrows():
        try:
            rotta = float(row['rotta_deg'])
            if 70.0 <= rotta <= 170.0:
                df.at[idx, 'pista'] = 'RWY 10'
                n_filled += 1
            elif 190.0 <= rotta <= 290.0:
                df.at[idx, 'pista'] = 'RWY 28'
                n_filled += 1
        except Exception:
            continue
    return df