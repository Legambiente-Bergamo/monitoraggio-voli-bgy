"""
bgy_tools/data06_fase_a.py - DATA-06 Fase A: verifica borderline vs N/D.
Versione 1.0.0

Obiettivo:
  Incrociare i casi con pista N/D (nei report notturni) con i casi
  borderline (nei file borderline_*.csv). Determinare quanti N/D
  sono in realtà movimenti operati fuori dalla finestra notturna
  (borderline travestiti) e quanti sono N/D veri (radar ha catturato
  il movimento ma non ha determinato la pista).

Input:
  - bgy_data/bgy_output/bgy_csv/report_nightly_YYYY-MM-DD.csv
  - bgy_data/bgy_output/bgy_csv/borderline_YYYY-MM-DD.csv

Output:
  - Report su schermo
  - File CSV: bgy_data/bgy_output/bgy_csv/data06_fase_a_YYYY-MM-DD.csv

Uso:
    py -3.12 -m bgy_tools.data06_fase_a
    py -3.12 -m bgy_tools.data06_fase_a 2026-09-30 2026-10-06
"""
import os
import re
import sys
import csv
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import OUTPUT_CSV_DIR

logger = get_logger("DATA06FaseA")


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
    """
    Normalizza un orario a HH:MM, tollerando:
      - '05:45'
      - '05:45:00'
      - '5:45'
      - '' / None / NaN
    Ritorna '' se non parsabile.
    """
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


def _list_report_files():
    """Ritorna lista di (data, path) per tutti i report_nightly_*.csv."""
    if not os.path.isdir(OUTPUT_CSV_DIR):
        return []
    out = []
    for f in sorted(os.listdir(OUTPUT_CSV_DIR)):
        m = re.match(r'^report_nightly_(\d{4}-\d{2}-\d{2})\.csv$', f)
        if m:
            out.append((m.group(1), os.path.join(OUTPUT_CSV_DIR, f)))
    return out


def _list_borderline_files():
    """Ritorna dict {data: path} per tutti i borderline_YYYY-MM-DD.csv
    (esclude il cumulativo mensile borderline_YYYY-MM.csv)."""
    if not os.path.isdir(OUTPUT_CSV_DIR):
        return {}
    out = {}
    for f in sorted(os.listdir(OUTPUT_CSV_DIR)):
        m = re.match(r'^borderline_(\d{4}-\d{2}-\d{2})\.csv$', f)
        if m:
            out[m.group(1)] = os.path.join(OUTPUT_CSV_DIR, f)
    return out


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


# -----------------------------------------------------------------------------
# CARICAMENTO
# -----------------------------------------------------------------------------

def _load_borderline_index():
    """
    Ritorna dict con chiave (data, callsign_norm, hhmm_norm) → categoria_borderline.
    """
    files = _list_borderline_files()
    idx = {}
    for data, path in files.items():
        rows = _read_csv(path)
        for r in rows:
            cs = _normalize_callsign(r.get("callsign", ""))
            sched = _normalize_hhmm(r.get("orario_schedulato", ""))
            cat = (r.get("categoria_borderline") or "").strip()
            key = (data, cs, sched)
            idx[key] = cat
    return idx


def _load_nd_cases(date_from, date_to):
    """
    Ritorna lista di dict con i casi N/D scheduled nei report notturni
    nel range [date_from, date_to].
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
                "direzione_sacbo": r.get("direzione_sacbo", ""),
                "orario_schedulato": _normalize_hhmm(r.get("orario_schedulato", "")),
                "timestamp": r.get("timestamp", ""),
                "fase_volo": r.get("fase_volo", ""),
                "fonte_scheduled": r.get("fonte_scheduled", ""),
                "is_borderline": False,
                "categoria_borderline": "",
            })
    return nd_cases


# -----------------------------------------------------------------------------
# ANALISI
# -----------------------------------------------------------------------------

def _classify_nd_cases(nd_cases, borderline_idx):
    """
    Arricchisce ogni caso N/D con is_borderline e categoria_borderline.
    """
    for c in nd_cases:
        key = (c["data"], c["callsign"], c["orario_schedulato"])
        if key in borderline_idx:
            c["is_borderline"] = True
            c["categoria_borderline"] = borderline_idx[key]
    return nd_cases


def _group_by_date(nd_cases):
    """Raggruppa per data_riferimento."""
    out = {}
    for c in nd_cases:
        out.setdefault(c["data"], []).append(c)
    return out


# -----------------------------------------------------------------------------
# STAMPA
# -----------------------------------------------------------------------------

def _print_header():
    print()
    print("=" * 90)
    print("  DATA-06 FASE A — Analisi borderline vs N/D veri")
    print("=" * 90)
    print()


def _print_per_night(date_str, cases):
    total = len(cases)
    n_bl = sum(1 for c in cases if c["is_borderline"])
    n_real = total - n_bl

    icon = "✅" if n_real == 0 else ("⚠️ " if n_real <= 2 else "❌")

    print(f"{icon}  {date_str}   N/D totali: {total}  "
          f"→ borderline: {n_bl}  |  N/D veri: {n_real}")

    # Elenco dei casi N/D veri (quelli che restano dopo il filtro)
    real_cases = [c for c in cases if not c["is_borderline"]]
    if real_cases:
        for c in real_cases:
            dir_label = c.get("direzione_sacbo", "?") or "?"
            tipo = c.get("tipo_movimento", "") or "?"
            sched = c.get("orario_schedulato", "") or "—"
            fonte = c.get("fonte_scheduled", "") or "radar-only"
            print(f"      · {c['callsign_orig']:12s} {dir_label}  "
                  f"sched {sched:8s}  {tipo:28s}  {fonte}")

    # Riepilogo delle categorie borderline
    if n_bl > 0:
        cats = {}
        for c in cases:
            if c["is_borderline"]:
                k = c["categoria_borderline"] or "altro"
                cats[k] = cats.get(k, 0) + 1
        cats_str = ", ".join(f"{k}={v}" for k, v in sorted(cats.items()))
        print(f"      borderline: {cats_str}")


def _print_summary(nd_cases):
    total = len(nd_cases)
    n_bl = sum(1 for c in nd_cases if c["is_borderline"])
    n_real = total - n_bl

    print()
    print("=" * 90)
    print("  RIEPILOGO GENERALE")
    print("=" * 90)
    print()
    print(f"  Casi N/D totali (scheduled):     {total}")
    print(f"  Di cui borderline travestiti:    {n_bl}  "
          f"({round(100.0 * n_bl / total, 1) if total > 0 else 0}%)")
    print(f"  Di cui N/D veri da indagare:     {n_real}  "
          f"({round(100.0 * n_real / total, 1) if total > 0 else 0}%)")
    print()

    # Breakdown per direzione
    print("  Breakdown N/D veri per direzione:")
    by_dir = {}
    for c in nd_cases:
        if c["is_borderline"]:
            continue
        d = c.get("direzione_sacbo", "?") or "?"
        by_dir.setdefault(d, []).append(c)
    for d in sorted(by_dir.keys()):
        label = {"D": "Decolli", "A": "Atterraggi", "?": "Altro"}.get(d, d)
        print(f"    · {label}: {len(by_dir[d])}")

    # Breakdown per categoria
    print()
    print("  Breakdown N/D veri per categoria:")
    by_cat = {}
    for c in nd_cases:
        if c["is_borderline"]:
            continue
        tipo = c.get("tipo_movimento", "") or "?"
        cat = tipo.split(" ")[0] if tipo else "?"
        by_cat[cat] = by_cat.get(cat, 0) + 1
    for cat in sorted(by_cat.keys()):
        print(f"    · {cat}: {by_cat[cat]}")

    # Top callsign ricorrenti
    print()
    print("  Top 10 callsign con N/D veri ricorrenti:")
    by_cs = {}
    for c in nd_cases:
        if c["is_borderline"]:
            continue
        cs = c["callsign_orig"]
        by_cs[cs] = by_cs.get(cs, 0) + 1
    sorted_cs = sorted(by_cs.items(), key=lambda x: (-x[1], x[0]))
    for cs, n in sorted_cs[:10]:
        print(f"    · {cs:15s} {n} occorrenze")

    print()


# -----------------------------------------------------------------------------
# EXPORT
# -----------------------------------------------------------------------------

def _export_csv(nd_cases, path):
    if not nd_cases:
        return None
    cols = [
        "data", "callsign_orig", "direzione_sacbo", "orario_schedulato",
        "timestamp", "tipo_movimento", "fase_volo", "fonte_scheduled",
        "is_borderline", "categoria_borderline",
    ]
    try:
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            writer.writeheader()
            for c in nd_cases:
                writer.writerow(c)
        return path
    except Exception as e:
        logger.error(f"Errore export CSV: {e}")
        return None


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="DATA-06 Fase A: borderline vs N/D veri.")
    parser.add_argument("date_from", nargs="?", default=None,
                        help="Data inizio (YYYY-MM-DD), opzionale")
    parser.add_argument("date_to", nargs="?", default=None,
                        help="Data fine (YYYY-MM-DD), opzionale")
    args = parser.parse_args()

    _print_header()

    print("Caricamento file borderline...")
    borderline_idx = _load_borderline_index()
    print(f"  Indice borderline: {len(borderline_idx)} casi")
    print()

    print("Caricamento report notturni...")
    nd_cases = _load_nd_cases(args.date_from, args.date_to)
    print(f"  Casi N/D scheduled totali: {len(nd_cases)}")
    print()

    nd_cases = _classify_nd_cases(nd_cases, borderline_idx)

    by_date = _group_by_date(nd_cases)

    for date_str in sorted(by_date.keys()):
        _print_per_night(date_str, by_date[date_str])

    _print_summary(nd_cases)

    # Export
    today = datetime.now().strftime("%Y-%m-%d")
    out_path = os.path.join(
        OUTPUT_CSV_DIR, f"data06_fase_a_{today}.csv"
    )
    result = _export_csv(nd_cases, out_path)
    if result:
        print(f"📄 Export CSV: {result}")
    print()


if __name__ == "__main__":
    main()