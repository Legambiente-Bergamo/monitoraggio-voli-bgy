"""
bgy_tools/confronto_sacbo_avionio.py - Confronto tra dati SACBO e Avionio.
Versione 0.1.1

Scopo:
  - Confrontare i dati dello scanner SACBO con quelli di Avionio.
  - Rilevare:
      * Voli comuni (confermati da entrambe le fonti)
      * Voli solo SACBO (che Avionio non vede)
      * Voli solo Avionio (che SACBO non vede)
  - Non modificare il report: solo diagnostica.

Logica di matching:
  - Callsign: confronto su "prefisso + cifre senza padding"
    (es. 'FR 0460' == 'FR 460')
  - Orario: match se differenza ≤ 15 minuti

Novità v0.1.1:
- Avviso se lo scan SACBO è più vecchio di 2 ore (Avionio copre solo
  le prossime 4-6h, quindi il confronto sarebbe distorto).
- Metriche corrette: invece della fuorviante "% accordo totale",
  mostra:
    * "% Avionio confermato da SACBO" (metrica principale)
    * "% SACBO confermato da Avionio" (metrica complementare)

Uso:
    py -3.12 -m bgy_tools.confronto_sacbo_avionio
    py -3.12 -m bgy_tools.confronto_sacbo_avionio --scan-file <path>
"""
import os
import re
import sys
import glob
import argparse
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import RAW_DIR

logger = get_logger("Confronto")

# Tolleranza match orario (minuti)
TIME_TOLERANCE_MIN = 15

# Soglia di avviso per scan troppo vecchio (minuti)
SCAN_AGE_WARN_MIN = 120


# -----------------------------------------------------------------------------
# UTILITY
# -----------------------------------------------------------------------------

def _normalize_callsign_key(callsign):
    """
    Crea una chiave di confronto robusta per il callsign.
    Es. 'FR 0460' e 'FR 460' → 'FR_460'
    """
    if not callsign or pd.isna(callsign):
        return ""
    s = str(callsign).strip().upper()
    # Estrai prefisso (lettere/cifre non numeriche) e parte numerica
    m = re.match(r'^([A-Z][A-Z0-9]?[A-Z]?)\s*0*(\d+)$', s.replace(" ", ""))
    if m:
        return f"{m.group(1)}_{m.group(2)}"
    # Fallback: rimuovi spazi
    return s.replace(" ", "")


def _parse_time_to_min(hhmm):
    """Converte 'HH:MM' in minuti dalla mezzanotte."""
    if not hhmm or pd.isna(hhmm):
        return None
    try:
        h, m = str(hhmm).strip().split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def _times_match(t1, t2, tolerance=TIME_TOLERANCE_MIN):
    """True se i due orari distano <= tolerance minuti."""
    m1 = _parse_time_to_min(t1)
    m2 = _parse_time_to_min(t2)
    if m1 is None or m2 is None:
        return False
    diff = abs(m1 - m2)
    # Gestione passaggio mezzanotte
    if diff > 12 * 60:
        diff = 24 * 60 - diff
    return diff <= tolerance


# -----------------------------------------------------------------------------
# CARICAMENTO DATI
# -----------------------------------------------------------------------------

def _find_latest_scan():
    """Trova l'ultimo file scan_*.csv in RAW_DIR."""
    files = sorted(glob.glob(os.path.join(RAW_DIR, "scan_2026-*.csv")))
    if not files:
        return None
    return files[-1]


def _find_latest_avionio(movement_type):
    """
    Trova l'ultimo file avionio_*.csv per il tipo dato.
    movement_type: 'arrivals' o 'departures'
    """
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    avionio_dir = os.path.join(_PROJECT_ROOT, "bgy_data", "bgy_avionio")
    if not os.path.isdir(avionio_dir):
        return None
    files = sorted(glob.glob(os.path.join(avionio_dir, f"avionio_{movement_type}_*.csv")))
    if not files:
        return None
    return files[-1]


def _load_sacbo(scan_file=None):
    """
    Carica i voli SACBO dall'ultimo scan (o da file specificato).
    Avvisa se lo scan è più vecchio di SCAN_AGE_WARN_MIN minuti.
    """
    path = scan_file or _find_latest_scan()
    if not path or not os.path.exists(path):
        logger.error("❌ Nessun file scan SACBO trovato")
        return None, None
    try:
        df = pd.read_csv(path)

        # Avviso se lo scan è più vecchio di 2 ore
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        age_min = (datetime.now() - mtime).total_seconds() / 60
        if age_min > SCAN_AGE_WARN_MIN:
            logger.warning(
                f"⚠️  Scan SACBO vecchio di {int(age_min)} min. "
                f"Alcuni voli Avionio potrebbero non essere visibili. "
                f"Considera di lanciare prima: "
                f"py -3.12 -m bgy_scanners.bgy_scanner_day"
            )

        logger.info(f"📄 SACBO: {os.path.basename(path)} ({len(df)} voli)")
        return df, path
    except Exception as e:
        logger.error(f"❌ Errore lettura {path}: {e}")
        return None, None


def _load_avionio(movement_type):
    """Carica l'ultimo file Avionio del tipo dato."""
    path = _find_latest_avionio(movement_type)
    if not path:
        logger.warning(f"⚠️  Nessun file Avionio per {movement_type}")
        return None, None
    try:
        df = pd.read_csv(path)
        logger.info(f"📄 Avionio {movement_type}: {os.path.basename(path)} ({len(df)} voli)")
        return df, path
    except Exception as e:
        logger.error(f"❌ Errore lettura {path}: {e}")
        return None, None


# -----------------------------------------------------------------------------
# CONFRONTO
# -----------------------------------------------------------------------------

def confronta_direzionale(df_sacbo, df_avionio, tipo):
    """
    Confronta i voli di un tipo (D o A) tra SACBO e Avionio.

    Ritorna dict:
      {
        "tipo": tipo,
        "sacbo_count": N,
        "avionio_count": M,
        "comuni": [(callsign, sched_sacbo, sched_avionio, time_match), ...],
        "solo_sacbo": [(callsign, sched), ...],
        "solo_avionio": [(callsign, sched), ...],
      }
    """
    result = {
        "tipo": tipo,
        "sacbo_count": 0,
        "avionio_count": 0,
        "comuni": [],
        "solo_sacbo": [],
        "solo_avionio": [],
    }

    if df_sacbo is None or df_avionio is None or df_sacbo.empty or df_avionio.empty:
        return result

    # Filtra per tipo movimento
    s = df_sacbo[df_sacbo["tipo_movimento"].astype(str).str.upper() == tipo].copy()
    a = df_avionio[df_avionio["tipo_movimento"].astype(str).str.upper() == tipo].copy()

    result["sacbo_count"] = len(s)
    result["avionio_count"] = len(a)

    # Chiave normalizzata
    s["_key"] = s["callsign_volo"].apply(_normalize_callsign_key)
    a["_key"] = a["callsign_volo"].apply(_normalize_callsign_key)

    # Set di chiavi
    s_keys = set(s["_key"]) - {""}
    a_keys = set(a["_key"]) - {""}

    comuni_keys = s_keys & a_keys
    solo_sacbo_keys = s_keys - a_keys
    solo_avionio_keys = a_keys - s_keys

    # Dettagli comuni (con verifica orario)
    for k in sorted(comuni_keys):
        s_row = s[s["_key"] == k].iloc[0]
        a_row = a[a["_key"] == k].iloc[0]
        s_sched = str(s_row.get("orario_schedulato", ""))
        a_sched = str(a_row.get("orario_schedulato", ""))
        time_ok = _times_match(s_sched, a_sched)
        result["comuni"].append({
            "callsign": s_row["callsign_volo"],
            "sched_sacbo": s_sched,
            "sched_avionio": a_sched,
            "time_match": time_ok,
        })

    # Solo SACBO
    for k in sorted(solo_sacbo_keys):
        s_row = s[s["_key"] == k].iloc[0]
        result["solo_sacbo"].append({
            "callsign": s_row["callsign_volo"],
            "sched": str(s_row.get("orario_schedulato", "")),
        })

    # Solo Avionio
    for k in sorted(solo_avionio_keys):
        a_row = a[a["_key"] == k].iloc[0]
        result["solo_avionio"].append({
            "callsign": a_row["callsign_volo"],
            "sched": str(a_row.get("orario_schedulato", "")),
        })

    return result


def format_report_text(confronti):
    """
    Formatta il risultato del confronto come testo multi-riga.
    Ritorna (testo, summary_dict).
    """
    lines = []
    lines.append("=" * 60)
    lines.append("CONFRONTO SACBO vs AVIONIO")
    lines.append("=" * 60)
    lines.append("")

    total_comuni = 0
    total_solo_sacbo = 0
    total_solo_avionio = 0
    total_mismatch_time = 0

    for c in confronti:
        tipo_label = "DECOLLI" if c["tipo"] == "D" else "ARRIVI"
        lines.append(f"═══ {tipo_label} ═══")
        lines.append(f"  SACBO:   {c['sacbo_count']:3d} voli")
        lines.append(f"  Avionio: {c['avionio_count']:3d} voli")
        lines.append(f"  Comuni:  {len(c['comuni']):3d}")
        lines.append(f"  Solo SACBO:   {len(c['solo_sacbo']):3d}")
        lines.append(f"  Solo Avionio: {len(c['solo_avionio']):3d}")
        lines.append("")

        # Comuni con mismatch orario
        mismatch = [x for x in c["comuni"] if not x["time_match"]]
        if mismatch:
            total_mismatch_time += len(mismatch)
            lines.append(f"  ⚠️  {len(mismatch)} voli comuni con ORARIO DIVERSO:")
            for x in mismatch[:5]:
                lines.append(f"     • {x['callsign']}: "
                             f"SACBO {x['sched_sacbo']} vs "
                             f"Avionio {x['sched_avionio']}")
            lines.append("")

        if c["solo_sacbo"]:
            lines.append(f"  Solo SACBO (Avionio non li vede):")
            for x in c["solo_sacbo"][:10]:
                lines.append(f"     • {x['callsign']} @ {x['sched']}")
            if len(c["solo_sacbo"]) > 10:
                lines.append(f"     ... e altri {len(c['solo_sacbo']) - 10}")
            lines.append("")

        if c["solo_avionio"]:
            lines.append(f"  Solo Avionio (SACBO non li vede):")
            for x in c["solo_avionio"][:10]:
                lines.append(f"     • {x['callsign']} @ {x['sched']}")
            if len(c["solo_avionio"]) > 10:
                lines.append(f"     ... e altri {len(c['solo_avionio']) - 10}")
            lines.append("")

        total_comuni += len(c["comuni"])
        total_solo_sacbo += len(c["solo_sacbo"])
        total_solo_avionio += len(c["solo_avionio"])

    # Riepilogo finale (metriche corrette)
    lines.append("=" * 60)
    lines.append("RIEPILOGO")
    lines.append("=" * 60)
    lines.append(f"  Totale comuni:        {total_comuni}")
    lines.append(f"  Totale solo SACBO:    {total_solo_sacbo}")
    lines.append(f"  Totale solo Avionio:  {total_solo_avionio}")

    if total_mismatch_time > 0:
        lines.append(f"  ⚠️  Mismatch orario:    {total_mismatch_time}")
    lines.append("")

    # Metrica principale: % di voli Avionio confermati da SACBO
    totale_avionio = total_comuni + total_solo_avionio
    pct_avionio_confermato = 0.0
    if totale_avionio > 0:
        pct_avionio_confermato = round(100 * total_comuni / totale_avionio, 1)
        lines.append(f"  📊 Avionio confermato da SACBO: "
                     f"{total_comuni}/{totale_avionio} ({pct_avionio_confermato}%)")

    # Metrica complementare: % di voli SACBO confermati da Avionio
    totale_sacbo = total_comuni + total_solo_sacbo
    pct_sacbo_confermato = 0.0
    if totale_sacbo > 0:
        pct_sacbo_confermato = round(100 * total_comuni / totale_sacbo, 1)
        lines.append(f"  📊 SACBO confermato da Avionio: "
                     f"{total_comuni}/{totale_sacbo} ({pct_sacbo_confermato}%)")

    lines.append("")
    lines.append("  ℹ️  Nota: Avionio copre solo le prossime 4-6 ore, mentre SACBO")
    lines.append("     copre h24. La metrica principale da osservare è la prima.")
    lines.append("     'Solo SACBO' elevato è normale. 'Solo Avionio' elevato")
    lines.append("     o 'Mismatch orario' elevati meritano investigazione.")

    return "\n".join(lines), {
        "comuni": total_comuni,
        "solo_sacbo": total_solo_sacbo,
        "solo_avionio": total_solo_avionio,
        "mismatch_time": total_mismatch_time,
        "pct_avionio_confermato": pct_avionio_confermato,
        "pct_sacbo_confermato": pct_sacbo_confermato,
    }


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Confronto SACBO vs Avionio")
    parser.add_argument("--scan-file", type=str, default=None,
                        help="Path specifico dello scan SACBO (default: ultimo)")
    args = parser.parse_args()

    # Carica SACBO
    df_sacbo, sacbo_path = _load_sacbo(args.scan_file)
    if df_sacbo is None:
        sys.exit(1)

    # Carica Avionio
    arr_avionio, _ = _load_avionio("arrivals")
    dep_avionio, _ = _load_avionio("departures")

    # Confronta
    confronti = []
    if dep_avionio is not None:
        confronti.append(confronta_direzionale(df_sacbo, dep_avionio, "D"))
    if arr_avionio is not None:
        confronti.append(confronta_direzionale(df_sacbo, arr_avionio, "A"))

    if not confronti:
        logger.error("❌ Nessun confronto possibile (Avionio non disponibile)")
        sys.exit(1)

    # Formatta e stampa
    text, summary = format_report_text(confronti)
    print()
    print(text)
    print()

    # Salva report su file
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    report_dir = os.path.join(_PROJECT_ROOT, "bgy_data", "bgy_avionio")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(
        report_dir,
        f"confronto_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.txt"
    )
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"📄 Report salvato: {report_path}")
    except Exception as e:
        logger.warning(f"Impossibile salvare report: {e}")

    # Summary machine-readable (utile per future integrazioni)
    print()
    print("=" * 60)
    print("SUMMARY (machine-readable)")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()