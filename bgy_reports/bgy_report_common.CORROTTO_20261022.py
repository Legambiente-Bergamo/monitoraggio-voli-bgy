"""
bgy_reports/bgy_report_common.py - Logica condivisa per i report notturni e H24.
Versione 1.3.1

Novita v1.3.1 (22/10/2026):
- File ricostruito dopo corruzione (BUG-08): il file era stato sovrascritto
  con il contenuto di bgy_core/bgy_db.py, perdendo ogni logica di pista.
- propagate_runway_in_session: first-for-D / last-for-A (RADAR-14),
  fallback icao24 per callsign UNKNOWN (RADAR-14b), soglia distanza da
  config (RADAR-14c, default 7 km).
- fill_unknown_runways_geometric: fallback geometrico (RADAR-07),
  track 70-170 deg -> RWY 10, 190-290 deg -> RWY 28, distanza 2-5 km.
- Tracciamento pista_fonte: 'radar_diretto' | 'propagato' | 'geometrico' | 'N/D'
  (DATA-32).

Novita v1.3.0 (21/10/2026, DATA-32 - PERDUTA per corruzione):
- Aggiunto tracciamento pista_fonte.
"""
import pandas as pd

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_config_manager import config_manager

logger = get_logger("ReportCommon")

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------
VALID_RUNWAYS = ('RWY 28', 'RWY 10')

PISTA_FONTE_RADAR = 'radar_diretto'
PISTA_FONTE_PROPAGATO = 'propagato'
PISTA_FONTE_GEOMETRICO = 'geometrico'
PISTA_FONTE_ND = 'N/D'

# Soglie geometriche (RADAR-07)
GEOMETRIC_MIN_DISTANCE_KM = 2.0
GEOMETRIC_MAX_DISTANCE_KM = 5.0
GEOMETRIC_RWY10_TRACK = (70, 170)
GEOMETRIC_RWY28_TRACK = (190, 290)

# Soglia quota per record "validi" (RADAR-16: aerei in volo, non in rullaggio)
MAX_QUOTA_VALID_FT = 2000

UNKNOWN_CALLSIGNS = ('', 'UNKNOWN', 'NAN', 'NONE', 'N/D', 'NA', 'N.A.')


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _cfg_scanner_radar():
    try:
        return config_manager.get_scanner_radar_config() or {}
    except Exception:
        return {}


def _safe_float(value, default=None):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_str(value, default=''):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    s = str(value).strip()
    return s if s else default


def _normalize_callsign(cs):
    if not cs:
        return ''
    try:
        if pd.isna(cs):
            return ''
    except (TypeError, ValueError):
        pass
    return str(cs).strip().upper()


def _is_unknown_callsign(cs):
    return _normalize_callsign(cs) in UNKNOWN_CALLSIGNS


def _is_valid_pista(pista):
    return _safe_str(pista).strip() in VALID_RUNWAYS


def _phase_to_dir(fase):
    f = _safe_str(fase).strip()
    if f == 'Decollo':
        return 'D'
    if f in ('Atterraggio', 'Avvicinamento'):
        return 'A'
    return ''


def _is_valid_radar_record(row, max_distance_km):
    """
    Un record è "valido" per la propagazione se:
      - pista già assegnata e in VALID_RUNWAYS
      - quota < MAX_QUOTA_VALID_FT (esclude aerei in rullaggio)
      - distanza < max_distance_km (esclude aerei troppo lontani)
    """
    if not _is_valid_pista(row.get('pista')):
        return False
    quota = _safe_float(row.get('quota_ft'), None)
    if quota is None or quota >= MAX_QUOTA_VALID_FT:
        return False
    dist = _safe_float(row.get('distanza_km'), None)
    if dist is None or dist > max_distance_km:
        return False
    return True


# ---------------------------------------------------------------------------
# RADAR-14: propagazione pista per (callsign, direzione)
# ---------------------------------------------------------------------------
def _propagate_by_callsign(df, max_distance_km):
    """
    Per ogni (callsign_normalizzato, direzione):
      - Decollo (D): usa il PRIMO record valido (più allineato alla pista)
      - Atterraggio (A): usa l'ULTIMO record valido (fine pista)
    Propaga la pista ai record del gruppo che non ce l'hanno.
    Ritorna il numero di record propagati.
    """
    propagated = 0
    for (key_val, dir_val), group in df.groupby(['_callsign_norm', '_dir']):
        if not key_val or dir_val not in ('D', 'A'):
            continue
        valid_mask = group.apply(lambda r: _is_valid_radar_record(r, max_distance_km), axis=1)
        valid_idx = group[valid_mask].index
        if len(valid_idx) == 0:
            continue
        try:
            donors = group.loc[valid_idx].copy()
            donors['_ts'] = pd.to_datetime(donors['timestamp'], errors='coerce')
            donors = donors.dropna(subset=['_ts']).sort_values('_ts')
        except Exception:
            continue
        if len(donors) == 0:
            continue
        chosen = donors.iloc[0] if dir_val == 'D' else donors.iloc[-1]
        pista_val = _safe_str(chosen.get('pista')).strip()
        if not _is_valid_pista(pista_val):
            continue
        for idx in group.index:
            if _is_valid_pista(df.at[idx, 'pista']):
                continue
            df.at[idx, 'pista'] = pista_val
            df.at[idx, 'pista_fonte'] = PISTA_FONTE_PROPAGATO
            propagated += 1
    return propagated


# ---------------------------------------------------------------------------
# RADAR-14b: fallback via icao24 per callsign UNKNOWN
# ---------------------------------------------------------------------------
def _propagate_by_icao24(df, max_distance_km):
    """
    Per i record con callsign UNKNOWN (o comunque senza pista dopo il passo 1):
      - costruisce una mappa icao24 -> {D: [donatori], A: [donatori]}
      - per ogni record senza pista, se il suo icao24 ha un donatore
        con la stessa direzione, eredita la pista
    """
    if 'icao24' not in df.columns:
        return 0

    # Costruisci la mappa dei donatori
    mappa = {}
    for idx, row in df.iterrows():
        icao = _safe_str(row.get('icao24')).lower()
        if not icao or icao in ('nan', 'none', 'n/d'):
            continue
        if not _is_valid_pista(row.get('pista')):
            continue
        dir_val = _phase_to_dir(row.get('fase_volo'))
        if dir_val not in ('D', 'A'):
            continue
        mappa.setdefault(icao, {}).setdefault(dir_val, []).append(idx)

    if not mappa:
        return 0

    propagated = 0
    for idx, row in df.iterrows():
        if _is_valid_pista(row.get('pista')):
            continue
        icao = _safe_str(row.get('icao24')).lower()
        if not icao or icao not in mappa:
            continue
        dir_val = _phase_to_dir(row.get('fase_volo'))
        if dir_val not in ('D', 'A'):
            continue
        donor_idxs = mappa[icao].get(dir_val, [])
        if not donor_idxs:
            continue
        try:
            donor_rows = df.loc[donor_idxs].copy()
            donor_rows['_ts'] = pd.to_datetime(donor_rows['timestamp'], errors='coerce')
            donor_rows = donor_rows.dropna(subset=['_ts']).sort_values('_ts')
        except Exception:
            continue
        if len(donor_rows) == 0:
            continue
        chosen = donor_rows.iloc[0] if dir_val == 'D' else donor_rows.iloc[-1]
        pista_val = _safe_str(chosen.get('pista')).strip()
        if not _is_valid_pista(pista_val):
            continue
        df.at[idx, 'pista'] = pista_val
        df.at[idx, 'pista_fonte'] = PISTA_FONTE_PROPAGATO
        propagated += 1
    return propagated


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------
def propagate_runway_in_session(radar_df):
    """
    Propaga la pista dai record radar "validi" a quelli dello stesso
    (callsign, direzione) che non ce l'hanno.

    - Decollo: primo record valido (allineato alla pista)
    - Atterraggio: ultimo record valido (fine pista)
    - Fallback via icao24 per callsign UNKNOWN (RADAR-14b)
    - Soglia distanza da config (RADAR-14c, default 7 km)
    - Traccia pista_fonte: 'radar_diretto' | 'propagato' | 'N/D' (DATA-32)
    """
    if radar_df is None or radar_df.empty:
        return radar_df

    df = radar_df.copy()

    # Assicura colonne minime
    if 'pista' not in df.columns:
        df['pista'] = PISTA_FONTE_ND
    if 'pista_fonte' not in df.columns:
        df['pista_fonte'] = PISTA_FONTE_ND
    if 'callsign' not in df.columns:
        df['callsign'] = ''
    if 'timestamp' not in df.columns:
        df['timestamp'] = ''
    if 'fase_volo' not in df.columns:
        df['fase_volo'] = ''

    # Normalizza pista (solo RWY 10 / RWY 28 validi)
    df['pista'] = df['pista'].apply(
        lambda x: _safe_str(x).strip() if _is_valid_pista(x) else PISTA_FONTE_ND
    )

    # Normalizza pista_fonte
    df['pista_fonte'] = df['pista_fonte'].apply(
        lambda x: _safe_str(x, PISTA_FONTE_ND) or PISTA_FONTE_ND
    )

    # Record con pista valida e fonte non ancora impostata -> radar_diretto
    mask_direct = df['pista'].apply(_is_valid_pista) & (df['pista_fonte'] == PISTA_FONTE_ND)
    df.loc[mask_direct, 'pista_fonte'] = PISTA_FONTE_RADAR

    # Colonne temporanee per il raggruppamento
    df['_dir'] = df['fase_volo'].apply(_phase_to_dir)
    df['_callsign_norm'] = df['callsign'].apply(
        lambda x: '' if _is_unknown_callsign(x) else _normalize_callsign(x)
    )

    cfg = _cfg_scanner_radar()
    max_distance_km = _safe_float(cfg.get('pista_max_distanza_km'), 7.0) or 7.0

    try:
        n1 = _propagate_by_callsign(df, max_distance_km)
        n2 = _propagate_by_icao24(df, max_distance_km)
        if n1 or n2:
            logger.info(
                f"🛬 Pista propagata: {n1} via callsign, {n2} via icao24 "
                f"(soglia {max_distance_km:.1f} km)"
            )
    finally:
        df.drop(columns=['_dir', '_callsign_norm'], inplace=True, errors='ignore')

    return df


def fill_unknown_runways_geometric(radar_df):
    """
    RADAR-07: fallback geometrico per i record rimasti con pista N/D.
    Condizioni: distanza tra 2 e 5 km, rotta valida.
      - Track 70-170°  -> RWY 10
      - Track 190-290° -> RWY 28
      - Altri track    -> resta N/D (principio: meglio N/D che falso)
    Imposta pista_fonte = 'geometrico' sui record dedotti.
    """
    if radar_df is None or radar_df.empty:
        return radar_df

    df = radar_df.copy()
    if 'pista' not in df.columns:
        df['pista'] = PISTA_FONTE_ND
    if 'pista_fonte' not in df.columns:
        df['pista_fonte'] = PISTA_FONTE_ND
    if 'rotta_deg' not in df.columns:
        df['rotta_deg'] = None
    if 'distanza_km' not in df.columns:
        df['distanza_km'] = None

    n_filled = 0
    for idx, row in df.iterrows():
        if _is_valid_pista(row.get('pista')):
            continue
        dist = _safe_float(row.get('distanza_km'), None)
        if dist is None or dist < GEOMETRIC_MIN_DISTANCE_KM or dist > GEOMETRIC_MAX_DISTANCE_KM:
            continue
        track = _safe_float(row.get('rotta_deg'), None)
        if track is None:
            continue
        track = track % 360.0
        pista_new = None
        if GEOMETRIC_RWY10_TRACK[0] <= track <= GEOMETRIC_RWY10_TRACK[1]:
            pista_new = 'RWY 10'
        elif GEOMETRIC_RWY28_TRACK[0] <= track <= GEOMETRIC_RWY28_TRACK[1]:
            pista_new = 'RWY 28'
        if pista_new:
            df.at[idx, 'pista'] = pista_new
            df.at[idx, 'pista_fonte'] = PISTA_FONTE_GEOMETRICO
            n_filled += 1

    if n_filled:
        logger.info(f"🛬 Pista assegnata geometricamente: {n_filled} record")
    return df


__all__ = [
    'propagate_runway_in_session',
    'fill_unknown_runways_geometric',
    'VALID_RUNWAYS',
    'PISTA_FONTE_RADAR',
    'PISTA_FONTE_PROPAGATO',
    'PISTA_FONTE_GEOMETRICO',
    'PISTA_FONTE_ND',
]