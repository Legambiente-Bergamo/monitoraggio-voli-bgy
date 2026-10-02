"""
bgy_core/bgy_export_web.py - Esportazione dati aggregati per il web (F17).
Versione 1.0.1

Scopo:
  - Leggere dal DB (PostgreSQL) e dai CSV e produrre un JSON aggregato con:
      * Movimenti giornalieri (D/A, ritardi, cancellati)
      * Puntualità giornaliera
      * Sconfinamenti notturni
      * Rumore massimo notturno
      * Top compagnie per ritardi (aggregato)
  - Salvare il JSON in bgy_data/bgy_output/bgy_web/bgy-data.txt.
  - Pubblicarlo su WordPress via bgy_core.bgy_wordpress.

Formato JSON:
  {
    "generated_at": "2026-10-01T16:00:00",
    "period": {"from": "2026-07-01", "to": "2026-10-01"},
    "summary": { ... },
    "daily": [ {...}, ... ],
    "nightly": [ {...}, ... ],
    "top_airlines": [ {...}, ... ]
  }

Novità v1.0.1 (fix lettura tipo_movimento):
- Il CSV report_daily_*.csv contiene tipo_movimento = "Decollo (D)" o
  "Atterraggio (A)", non "D"/"A". Il conteggio usa .str[:1] per estrarre
  il primo carattere (come fanno gli altri moduli della suite).

Novità v1.0.0:
- Prima versione. Output .txt (per aggirare il blocco MIME di WordPress).

Uso:
    py -3.12 -m bgy_core.bgy_export_web --days 90
    py -3.12 -m bgy_core.bgy_export_web --days 90 --publish
    py -3.12 -m bgy_core.bgy_export_web --days 90 --dry-run
"""
import os
import sys
import json
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import DATA_DIR, OUTPUT_CSV_DIR
from bgy_core import bgy_db

logger = get_logger("ExportWeb")

WEB_OUTPUT_DIR = os.path.join(DATA_DIR, "bgy_output", "bgy_web")
WEB_OUTPUT_FILE = os.path.join(WEB_OUTPUT_DIR, "bgy-data.csv")


# -----------------------------------------------------------------------------
# AGGREGAZIONE
# -----------------------------------------------------------------------------

def _query(sql, params=None):
    ok, rows = bgy_db.execute_query(sql, params)
    if not ok:
        logger.error(f"Errore query: {rows}")
        return []
    return rows or []


def build_daily_data(date_from, date_to):
    """
    Movimenti giornalieri + puntualità dal CSV report_daily_*.
    Il CSV è la fonte più affidabile per i ritardi.

    Fix v1.0.1: la colonna tipo_movimento contiene "Decollo (D)" o
    "Atterraggio (A)". Il conteggio usa .str[:1] per estrarre il primo
    carattere, come get_hourly_distribution in bgy_db_migrate.py.
    """
    import pandas as pd

    daily = []
    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date()
    d = start
    while d <= end:
        ds = d.strftime("%Y-%m-%d")
        csv_path = os.path.join(OUTPUT_CSV_DIR, f"report_daily_{ds}.csv")
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path)
                if not df.empty:
                    if "stato_volo" in df.columns:
                        mask_canc = (
                            df["stato_volo"].astype(str).str.upper()
                            .str.contains("CANCEL", na=False)
                        )
                        cancellati = int(mask_canc.sum())
                        df = df[~mask_canc]
                    else:
                        cancellati = 0

                    # Fix v1.0.1: tipo_movimento = "Decollo (D)" o "Atterraggio (A)"
                    if "tipo_movimento" in df.columns:
                        tipo = df["tipo_movimento"].astype(str).str.upper().str[:1]
                        d_count = int((tipo == "D").sum())
                        a_count = int((tipo == "A").sum())
                    else:
                        d_count = 0
                        a_count = 0

                    if "minuti_ritardo" in df.columns:
                        rit = pd.to_numeric(
                            df["minuti_ritardo"], errors="coerce"
                        ).fillna(0)
                        in_rit = int((rit > 0).sum())
                        in_oro = int((rit == 0).sum())
                        in_ant = int((rit < 0).sum())
                        rit_medio = round(float(rit[rit > 0].mean()), 1) if in_rit > 0 else 0
                        rit_max = int(rit.max()) if len(rit) > 0 else 0
                    else:
                        in_rit = in_oro = in_ant = 0
                        rit_medio = rit_max = 0

                    daily.append({
                        "date": ds,
                        "decolli": d_count,
                        "atterraggi": a_count,
                        "totale": d_count + a_count,
                        "ritardi_count": in_rit,
                        "in_orario": in_oro,
                        "in_anticipo": in_ant,
                        "ritardo_medio": rit_medio,
                        "ritardo_max": rit_max,
                        "cancellati": cancellati,
                    })
            except Exception as e:
                logger.warning(f"Errore lettura {csv_path}: {e}")
        d += timedelta(days=1)

    return daily


def build_nightly_data(date_from, date_to):
    """Sconfinamenti notturni + rumore massimo dal DB."""
    rows = _query(
        """SELECT
              data_riferimento,
              COUNT(*) FILTER (WHERE notte_categoria = 'regolare') AS regolari,
              COUNT(*) FILTER (WHERE notte_categoria = 'sconfinamento') AS sconfinamenti,
              COUNT(*) FILTER (WHERE notte_categoria = 'sconfinamento_grave') AS sconfinamenti_gravi,
              COUNT(*) FILTER (WHERE notte_categoria = 'anomalia') AS anomalie,
              MAX(stima_rumore_db) AS rumore_max,
              SUM(stima_passeggeri) AS pax_stimati
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND tipo_movimento = 'Passeggeri'
           GROUP BY data_riferimento
           ORDER BY data_riferimento""",
        (date_from, date_to),
    )

    nightly = []
    for r in rows:
        data_rif = r[0]
        ds = data_rif.strftime("%Y-%m-%d") if hasattr(data_rif, "strftime") else str(data_rif)
        nightly.append({
            "date": ds,
            "regolari": int(r[1] or 0),
            "sconfinamenti": int(r[2] or 0),
            "sconfinamenti_gravi": int(r[3] or 0),
            "anomalie": int(r[4] or 0),
            "rumore_max_db": int(r[5] or 0),
            "pax_stimati": int(r[6] or 0),
        })
    return nightly


def build_top_airlines(date_from, date_to, top_n=10):
    """Top compagnie per ritardi, aggregato su tutto il periodo."""
    import pandas as pd

    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date()

    all_rows = []
    d = start
    while d <= end:
        ds = d.strftime("%Y-%m-%d")
        csv_path = os.path.join(OUTPUT_CSV_DIR, f"report_daily_{ds}.csv")
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path)
                if not df.empty and "compagnia_aerea" in df.columns:
                    df["_date"] = ds
                    all_rows.append(df)
            except Exception:
                pass
        d += timedelta(days=1)

    if not all_rows:
        return []

    df = pd.concat(all_rows, ignore_index=True)

    if "stato_volo" in df.columns:
        mask_canc = (
            df["stato_volo"].astype(str).str.upper()
            .str.contains("CANCEL", na=False)
        )
        df = df[~mask_canc]

    if "minuti_ritardo" not in df.columns:
        return []

    df["_rit"] = pd.to_numeric(df["minuti_ritardo"], errors="coerce").fillna(0)
    df["_comp"] = df["compagnia_aerea"].astype(str).str.strip()
    df = df[~df["_comp"].str.match(r"^Compagnia ", na=False)]
    df = df[~df["_comp"].isin(["", "N/D", "nan"])]

    result = []
    for comp, group in df.groupby("_comp"):
        delayed = group[group["_rit"] > 0]
        n_delayed = len(delayed)
        if n_delayed == 0:
            continue
        result.append({
            "compagnia": str(comp),
            "delayed": int(n_delayed),
            "total": int(len(group)),
            "avg_delay": round(float(delayed["_rit"].mean()), 1),
            "max_delay": int(delayed["_rit"].max()),
        })

    result.sort(key=lambda x: (-x["delayed"], -x["avg_delay"]))
    return result[:top_n]


def build_summary(daily, nightly):
    """Riepilogo generale del periodo."""
    if not daily:
        return {}

    tot_d = sum(x["decolli"] for x in daily)
    tot_a = sum(x["atterraggi"] for x in daily)
    tot_rit = sum(x["ritardi_count"] for x in daily)
    tot_voli = tot_d + tot_a

    sconf_tot = sum(x["sconfinamenti"] + x["sconfinamenti_gravi"] for x in nightly)
    rumore_max = max((x["rumore_max_db"] for x in nightly), default=0)

    return {
        "giorni": len(daily),
        "decolli_totali": tot_d,
        "atterraggi_totali": tot_a,
        "movimenti_totali": tot_voli,
        "ritardi_totali": tot_rit,
        "pct_ritardi": round(100.0 * tot_rit / tot_voli, 1) if tot_voli > 0 else 0,
        "sconfinamenti_totali": sconf_tot,
        "rumore_max_db": rumore_max,
    }


# -----------------------------------------------------------------------------
# BUILD E SALVATAGGIO
# -----------------------------------------------------------------------------

def build_web_json(days=90):
    """
    Costruisce il JSON aggregato per il web.
    Ritorna il dizionario Python (non ancora serializzato).
    """
    today = datetime.now().date()
    date_to = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    date_from = (today - timedelta(days=days)).strftime("%Y-%m-%d")

    logger.info(f"📊 Costruzione JSON web: {date_from} → {date_to} ({days} giorni)")

    daily = build_daily_data(date_from, date_to)
    nightly = build_nightly_data(date_from, date_to)
    top_airlines = build_top_airlines(date_from, date_to, top_n=10)
    summary = build_summary(daily, nightly)

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "period": {"from": date_from, "to": date_to},
        "summary": summary,
        "daily": daily,
        "nightly": nightly,
        "top_airlines": top_airlines,
    }

    logger.info(
        f"✅ JSON web: {len(daily)} giorni, {len(nightly)} notti, "
        f"{len(top_airlines)} compagnie"
    )
    return payload


def save_web_json(payload):
    """Salva il JSON in bgy_data/bgy_output/bgy_web/bgy-data.txt."""
    os.makedirs(WEB_OUTPUT_DIR, exist_ok=True)
    try:
        with open(WEB_OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        size_kb = round(os.path.getsize(WEB_OUTPUT_FILE) / 1024, 1)
        logger.info(f"💾 JSON salvato: {WEB_OUTPUT_FILE} ({size_kb} KB)")
        return WEB_OUTPUT_FILE
    except Exception as e:
        logger.error(f"❌ Errore salvataggio JSON: {e}")
        return None


def export_and_publish(days=90):
    """
    Build + save + publish su WordPress.
    Ritorna (ok, msg).
    """
    from bgy_core import bgy_wordpress

    payload = build_web_json(days=days)
    if not payload:
        return False, "JSON vuoto"

    local_path = save_web_json(payload)
    if not local_path:
        return False, "Errore salvataggio JSON locale"

    if not bgy_wordpress.is_enabled():
        logger.info("⏭️ WordPress disabilitato, salto pubblicazione")
        return True, f"JSON locale salvato ({local_path}), WordPress disabilitato"

    ok, msg, url = bgy_wordpress.publish_json(local_path)
    if ok:
        return True, f"Pubblicato: {url}"
    return False, f"Errore pubblicazione: {msg}"


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Esportazione dati aggregati per il web (F17)"
    )
    parser.add_argument("--days", type=int, default=90,
                        help="Giorni da includere (default: 90)")
    parser.add_argument("--publish", action="store_true",
                        help="Pubblica anche su WordPress")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo build locale, senza pubblicare")
    args = parser.parse_args()

    if not bgy_db.is_enabled():
        print("❌ DB non abilitato")
        sys.exit(1)

    if args.dry_run or not args.publish:
        payload = build_web_json(days=args.days)
        path = save_web_json(payload)
        if path:
            print(f"✅ JSON salvato: {path}")
            print(f"   Dimensione: {round(os.path.getsize(path)/1024, 1)} KB")
        else:
            print("❌ Errore salvataggio JSON")
            sys.exit(1)
        sys.exit(0)

    ok, msg = export_and_publish(days=args.days)
    print(f"{'✅' if ok else '❌'} {msg}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()