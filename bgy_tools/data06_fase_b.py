"""
bgy_tools/data06_fase_b.py - DATA-06 Fase B: pattern ricorrenti N/D.
Versione 1.0.0

Obiettivo:
  Per ogni caso N/D scheduled (dai report notturni), estrarre dal radar
  tutte le osservazioni dello stesso icao24 in una finestra +/- 10 minuti
  dal timestamp del match. Determinare se la pista era "recuperabile"
  (osservazione vicina con track/pista valida) o "persa" (nessun campione
  con track valido). Classificare ogni caso e produrre report aggregato.

Classificazione:
  - RECUPERABILE  : esiste >=1 osservazione icao24 con pista valida
                    (RWY 28 o RWY 10) nella finestra, di fase compatibile
                    con la direzione del caso.
  - PERSO         : nessuna osservazione icao24 con pista valida nella
                    finestra. L'aereo e' stato visto solo con N/D o
                    non e' stato visto affatto.
  - SOLO_ND       : esistono osservazioni ma tutte con pista N/D.
  - TIMING        : esiste un'osservazione con pista valida ma fuori dalla
                    finestra +/- 10 min (problematico del matcher, non del
                    radar).
  - NO_ICAO       : il caso non ha icao24 (radar non ha catturato nulla).

Input:
  - bgy_data/bgy_output/bgy_csv/report_nightly_YYYY-MM-DD.csv
  - bgy_data/bgy_raw/radar_YYYY-MM-DD.csv
  - bgy_data/bgy_raw/radar_YYYY-MM-DD+1.csv

Output:
  - Report su schermo
  - CSV: bgy_data/bgy_output/bgy_csv/data06_fase_b_YYYY-MM-DD.csv

Uso:
    py -3.12 -m bgy_tools.data06_fase_b
    py -3.12 -m bgy_tools.data06_fase_b 2026-09-30 2026-10-07
"""
import os
import re
import sys
import csv
import argparse
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import RAW_DIR, OUTPUT_CSV_DIR

logger = get_logger("DATA06FaseB")


WINDOW_MIN = 10  # +/- minuti
VALID_RUNWAYS = ("RWY 28", "RWY 10")


# -----------------------------------------------------------------------------
# UTILITY
# -----------------------------------------------------------------------------

def _normalize_callsign(cs):
    if not cs:
        return ""
    s = str(cs).strip().upper()
    s = re.sub(r'[\s\u00A0\u200B\u200C\u200D\uFEFF]+', '', s)
    return s


def _normalize_hhmm(hhmm):
    if not hhmm:
        return ""
    s = str(hhmm).strip()
    if not s or s.lower() in ('nan', 'none', 'n/d'):
        return ""
    m = re.match(r'^(\d{1,2}):(\d{2})(?::\d{2})?$', s)
    if not m:
        return ""
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def _is_nd_pista(p):
    if p is None:
        return True
    s = str(p).strip()
    return s in ('', 'N/D', 'nan', 'None', 'NaN')


def _parse_ts(ts):
    if ts is None:
        return None
    try:
        return pd.to_datetime(ts)
    except Exception:
        return None


def _phase_compatible(direzione, fase):
    d = (direzione or "").strip().upper()
    f = (fase or "").strip()
    if d == "D":
        return f == "Decollo"
    if d == "A":
        return f in ("Atterraggio", "Avvicinamento")
    return False


def _list_report_files():
    if not os.path.isdir(OUTPUT_CSV_DIR):
        return []
    out = []
    for f in sorted(os.listdir(OUTPUT_CSV_DIR)):
        m = re.match(r'^report_nightly_(\d{4}-\d{2}-\d{2})\.csv$', f)
        if m:
            out.append((m.group(1), os.path.join(OUTPUT_CSV_DIR, f)))
    return out


# -----------------------------------------------------------------------------
# CARICAMENTO
# -----------------------------------------------------------------------------

def _read_csv(path):
    rows = []
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(r)
    except Exception as e:
        logger.warning(f"Errore lettura {path}: {e}")
    return rows


def _load_nd_cases(date_from=None, date_to=None):
    """
    Ritorna lista di dict con i casi N/D scheduled, con icao24 e timestamp.
    Filtra su date_from/date_to se passati.
    """
    files = _list_report_files()
    nd_cases = []
    for data, path in files:
        if date_from and data < date_from:
            continue
        if date_to and data > date_to:
            continue
        rows = _read_csv(path)
        for r in rows:
            is_sched = str(r.get("is_scheduled", "")).strip().lower()
            if is_sched not in ("true", "1", "yes"):
                continue
            if not _is_nd_pista(r.get("pista", "")):
                continue
            nd_cases.append({
                "data": data,
                "callsign": _normalize_callsign(r.get("callsign", "")),
                "callsign_orig": r.get("callsign", ""),
                "tipo_movimento": r.get("tipo_movimento", ""),
                "direzione_sacbo": (r.get("direzione_sacbo", "") or "").strip().upper(),
                "orario_schedulato": _normalize_hhmm(r.get("orario_schedulato", "")),
                "timestamp": (r.get("timestamp", "") or "").strip(),
                "icao24": (r.get("icao24", "") or "").strip().lower(),
                "fase_volo": r.get("fase_volo", ""),
                "fonte_scheduled": r.get("fonte_scheduled", ""),
            })
    return nd_cases


def _load_radar_window(date_ref, ts_center, icao24):
    """
    Carica dal radar tutte le osservazioni dello stesso icao24
    in una finestra +/- WINDOW_MIN dal ts_center.

    Cerca in radar_<date_ref>.csv e radar_<date_ref+1>.csv.

    Ritorna lista di dict con le colonne utili.
    """
    if not icao24:
        return []
    if ts_center is None:
        return []

    next_date = (datetime.strptime(date_ref, "%Y-%m-%d")
                 + timedelta(days=1)).strftime("%Y-%m-%d")

    files_to_load = []
    for d in (date_ref, next_date):
        p = os.path.join(RAW_DIR, f"radar_{d}.csv")
        if os.path.exists(p):
            files_to_load.append(p)

    if not files_to_load:
        return []

    dfs = []
    for p in files_to_load:
        try:
            dfs.append(pd.read_csv(p))
        except Exception as e:
            logger.warning(f"Errore lettura {p}: {e}")

    if not dfs:
        return []

    df = pd.concat(dfs, ignore_index=True)
    if "icao24" not in df.columns or "timestamp" not in df.columns:
        return []

    df["_icao_norm"] = df["icao24"].astype(str).str.strip().str.lower()
    df = df[df["_icao_norm"] == icao24].copy()
    if df.empty:
        return []

    df["_ts"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df[df["_ts"].notna()].copy()
    if df.empty:
        return []

    window = timedelta(minutes=WINDOW_MIN)
    mask = (df["_ts"] >= ts_center - window) & (df["_ts"] <= ts_center + window)
    df = df[mask].sort_values("_ts")

    rows = []
    for _, r in df.iterrows():
        rows.append({
            "timestamp": str(r.get("timestamp", "")),
            "callsign": str(r.get("callsign", "") or ""),
            "icao24": str(r.get("icao24", "") or ""),
            "pista": str(r.get("pista", "") or ""),
            "fase_volo": str(r.get("fase_volo", "") or ""),
            "rotta_deg": r.get("rotta_deg", None),
            "quota_ft": r.get("quota_ft", None),
            "distanza_km": r.get("distanza_km", None),
        })
    return rows


# -----------------------------------------------------------------------------
# CLASSIFICAZIONE
# -----------------------------------------------------------------------------

def _classify_case(case, observations):
    """
    Ritorna (verdict, dettaglio).

    verdict ∈ {
      'RECUPERABILE', 'PERSO', 'SOLO_ND', 'TIMING', 'NO_ICAO',
    }
    """
    if not case.get("icao24"):
        return "NO_ICAO", "nessun icao24 nel report (radar non catturato)"

    if not observations:
        return "PERSO", "nessuna osservazione nella finestra"

    # Conta osservazioni per fase
    has_valid_pista = False
    has_compatible_phase = False
    has_nd_only = True
    for o in observations:
        if o["pista"] in VALID_RUNWAYS:
            has_valid_pista = True
            has_nd_only = False
            if _phase_compatible(case["direzione_sacbo"], o["fase_volo"]):
                has_compatible_phase = True
        elif not _is_nd_pista(o["pista"]):
            has_nd_only = False

    if has_valid_pista and has_compatible_phase:
        return "RECUPERABILE", (
            f"{len(observations)} oss., di cui con pista valida e fase "
            f"compatibile"
        )
    if has_valid_pista and not has_compatible_phase:
        return "TIMING", (
            f"{len(observations)} oss. con pista valida ma fase non "
            f"compatibile (match ha scelto fase sbagliata)"
        )
    if has_nd_only:
        return "SOLO_ND", (
            f"{len(observations)} oss. tutte con pista N/D"
        )
    return "PERSO", f"{len(observations)} oss. senza pista valida"


# -----------------------------------------------------------------------------
# ANALISI
# -----------------------------------------------------------------------------

def _analyze_cases(cases):
    """
    Per ogni caso, carica osservazioni radar e classifica.
    Ritorna (results, summary).
    """
    results = []
    summary = {
        "RECUPERABILE": 0,
        "PERSO": 0,
        "SOLO_ND": 0,
        "TIMING": 0,
        "NO_ICAO": 0,
    }

    total = len(cases)
    for i, case in enumerate(cases, 1):
        ts_str = case.get("timestamp", "")
        ts_center = _parse_ts(ts_str) if ts_str else None
        obs = _load_radar_window(case["data"], ts_center, case["icao24"])

        verdict, detail = _classify_case(case, obs)
        summary[verdict] = summary.get(verdict, 0) + 1

        results.append({
            "data": case["data"],
            "callsign": case["callsign_orig"],
            "direzione_sacbo": case["direzione_sacbo"],
            "orario_schedulato": case["orario_schedulato"],
            "timestamp": case["timestamp"],
            "icao24": case["icao24"],
            "fase_volo": case["fase_volo"],
            "fonte_scheduled": case["fonte_scheduled"],
            "n_obs_window": len(obs),
            "verdict": verdict,
            "dettaglio": detail,
            "observations": obs,
        })

        if i % 5 == 0 or i == total:
            print(f"  ...analizzati {i}/{total}")

    return results, summary


# -----------------------------------------------------------------------------
# STAMPA
# -----------------------------------------------------------------------------

def _print_header():
    print()
    print("=" * 90)
    print("  DATA-06 FASE B — Pattern N/D: recuperabile, perso, timing")
    print("=" * 90)
    print()


def _print_case(case_result, show_obs=False):
    v = case_result["verdict"]
    icon = {
        "RECUPERABILE": "🟢",
        "PERSO": "🔴",
        "SOLO_ND": "🟡",
        "TIMING": "🟠",
        "NO_ICAO": "⚪",
    }.get(v, "❓")

    print(f"  {icon} [{v:12s}] {case_result['data']}  "
          f"{case_result['callsign']:12s} {case_result['direzione_sacbo']}  "
          f"sched {case_result['orario_schedulato']:8s}  "
          f"icao {case_result['icao24'] or '?':8s}  "
          f"obs={case_result['n_obs_window']}")
    print(f"                 {case_result['dettaglio']}")

    if show_obs and case_result["observations"]:
        for o in case_result["observations"]:
            track_str = f"{o['rotta_deg']}" if o['rotta_deg'] is not None else "?"
            quota_str = f"{o['quota_ft']}" if o['quota_ft'] is not None else "?"
            print(f"       · {o['timestamp']}  {o['callsign']:10s}  "
                  f"{o['fase_volo']:14s}  pista={o['pista']:8s}  "
                  f"track={track_str:>8s}  quota={quota_str:>6s}")


def _print_summary(summary, results):
    total = sum(summary.values())
    print()
    print("=" * 90)
    print("  RIEPILOGO")
    print("=" * 90)
    print()
    print(f"  Casi N/D analizzati:  {total}")
    print()
    for key in ("RECUPERABILE", "TIMING", "SOLO_ND", "PERSO", "NO_ICAO"):
        n = summary.get(key, 0)
        pct = round(100.0 * n / total, 1) if total > 0 else 0
        print(f"    {key:15s} {n:3d}  ({pct}%)")
    print()

    # Top callsign ricorrenti tra i RECUPERABILE e TIMING
    focus = [r for r in results if r["verdict"] in ("RECUPERABILE", "TIMING")]
    if focus:
        print("  Top callsign con problema recuperabile/timing:")
        by_cs = defaultdict(int)
        for r in focus:
            by_cs[r["callsign"]] += 1
        for cs, n in sorted(by_cs.items(), key=lambda x: (-x[1], x[0]))[:10]:
            print(f"    · {cs:15s} {n}")
    print()


# -----------------------------------------------------------------------------
# EXPORT
# -----------------------------------------------------------------------------

def _export_csv(results, path):
    if not results:
        return None
    cols = [
        "data", "callsign", "direzione_sacbo", "orario_schedulato",
        "timestamp", "icao24", "fase_volo", "fonte_scheduled",
        "n_obs_window", "verdict", "dettaglio",
    ]
    try:
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            writer.writeheader()
            for r in results:
                writer.writerow(r)
        return path
    except Exception as e:
        logger.error(f"Errore export CSV: {e}")
        return None


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="DATA-06 Fase B: pattern ricorrenti N/D.")
    parser.add_argument("date_from", nargs="?", default=None,
                        help="Data inizio (YYYY-MM-DD), opzionale")
    parser.add_argument("date_to", nargs="?", default=None,
                        help="Data fine (YYYY-MM-DD), opzionale")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Mostra tutte le osservazioni di ogni caso")
    args = parser.parse_args()

    _print_header()

    print("Caricamento casi N/D...")
    cases = _load_nd_cases(args.date_from, args.date_to)
    print(f"  Casi N/D scheduled: {len(cases)}")
    print()

    if not cases:
        print("Nessun caso da analizzare.")
        sys.exit(0)

    print("Analisi osservazioni radar...")
    results, summary = _analyze_cases(cases)

    print()
    print("=" * 90)
    print("  DETTAGLIO CASI")
    print("=" * 90)
    print()

    for r in results:
        _print_case(r, show_obs=args.verbose)

    _print_summary(summary, results)

    today = datetime.now().strftime("%Y-%m-%d")
    out_path = os.path.join(
        OUTPUT_CSV_DIR, f"data06_fase_b_{today}.csv"
    )
    result = _export_csv(results, out_path)
    if result:
        print(f"📄 Export CSV: {result}")
    print()


if __name__ == "__main__":
    main()