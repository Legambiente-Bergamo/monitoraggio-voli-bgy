"""
bgy_reports/bgy_report_common.py - Logica condivisa tra bgy_report_night e bgy_report_h24.
Versione 1.0.0

Novita v1.0.0 (21/10/2026, ARCH-01):
- Estrazione della logica pista da bgy_report_night v2.9.35 e bgy_report_h24 v1.0.7.
- Zero modifiche di comportamento rispetto a v2.9.35/v1.0.7: stessi default,
  stesso ordine di operazioni, stesso output.
- Funzioni esportate:
    propagate_runway_in_session(radar_df, cfg=None)
    fill_unknown_runways_geometric(df, cfg=None)
- Config keys predisposte per RADAR-14 (default compatibili con il comportamento
  attuale):
    scanner_radar.pista_min_quota_ft   (default 100)
    scanner_radar.pista_max_distanza_km (default 5.0)
  In v1.0.0 i default replicano esattamente i valori hardcoded delle versioni
  precedenti. Le chiavi verranno effettivamente usate in v1.1.0 (RADAR-14).
"""
import pandas as pd

from bgy_core.bgy_config_manager import config_manager
from bgy_core.bgy_logger import get_logger

logger = get_logger("ReportCommon")

VALID_RUNWAYS = ('RWY 28', 'RWY 10')

_DEFAULT_PISTA_MIN_QUOTA_FT = 100
_DEFAULT_PISTA_MAX_DISTANZA_KM = 5.0


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


def propagate_runway_in_session(radar_df, cfg=None):
    """
    Propaga la pista tra i record radar dello stesso callsign e direzione.

    Comportamento v1.0.0 (identico a bgy_report_night v2.9.35 e
    bgy_report_h24 v1.0.7):
    - I record con quota_ft < pista_min_quota_ft (default 100) sono esclusi
      dal calcolo della moda (track a terra inaffidabile).
    - Solo i record con pista valida, distanza < pista_max_distanza_km
      (default 5.0) e quota < 2000 ft contribuiscono alla moda.
    - Per ogni (callsign, direzione) senza pista valida, viene applicata
      la moda dei record validi.

    Args:
        radar_df: DataFrame dei rilevamenti radar (deve avere le colonne
                  callsign, pista, fase_volo, quota_ft, distanza_km).
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
    df['_pista_clean'] = df['pista'].apply(_clean_pista)
    df['_dir'] = df['fase_volo'].apply(_phase_to_dir)

    # Azzera la pista per i record a terra (track inaffidabile)
    if 'quota_ft' in df.columns:
        df.loc[df['quota_ft'] < min_quota, '_pista_clean'] = ''

    valid_mask = df['_pista_clean'].isin(VALID_RUNWAYS)
    if 'distanza_km' in df.columns:
        valid_mask &= (df['distanza_km'] < max_dist)
    if 'quota_ft' in df.columns:
        valid_mask &= (df['quota_ft'] < 2000)

    pista_map = {}
    for (cs, d), group in df[valid_mask].groupby(
        [df['callsign'].str.strip().str.upper(), df['_dir']]
    ):
        if not cs or not d:
            continue
        mode_series = group['_pista_clean'].mode()
        if not mode_series.empty:
            pista_map[(cs, d)] = mode_series.iloc[0]

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
    return df


def fill_unknown_runways_geometric(df, cfg=None):
    """
    Fallback geometrico per piste N/D sui decolli (RADAR-07).

    Comportamento v1.0.0 (identico a bgy_report_night v2.9.35 e
    bgy_report_h24 v1.0.7):
    - Solo per i decolli con pista N/D, distanza 2-5 km, rotta valida.
    - Track 70-170°  → RWY 10
    - Track 190-290° → RWY 28
    - Altrimenti resta N/D.

    Nota: nella v2.9.35 questa funzione NON è chiamata da nessun punto del
    modulo bgy_report_night. È stata mantenuta per compatibilità con
    RADAR-07 e verrà eventualmente riattivata in una sessione dedicata.
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