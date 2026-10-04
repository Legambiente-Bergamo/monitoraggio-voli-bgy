"""
bgy_core/bgy_export_web.py - Esportazione dati aggregati per il web (F17).
Versione 1.2.8

Novità v1.2.8:
- Aggiunti totals.schedulato_D e totals.schedulato_A (e by_date).
- Aggiunto blocco block_night_anomalies con dettaglio voli anomali.

Novità v1.2.7:
- build_block_destinations_pax ora restituisce {D, A, note} con by_city /
  by_country separati per direzione (partenze / arrivi).

Novità v1.2.6:
- build_block_night_airlines ora restituisce anche D e A per ogni compagnia.

Novità v1.2.5:
- Aggiunto blocco block_destinations_pax.

Novità v1.2.4:
- D/A, side_* e by_side contano SOLO i voli a tabellone (is_scheduled=TRUE).

Novità v1.2.3:
- by_date[].{D,A}_{passeggeri,cargo,charter,non_classificato}

Uso:
    py -3.12 -m bgy_core.bgy_export_web --days 90 --dry-run
    py -3.12 -m bgy_core.bgy_export_web --days 90 --publish
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

WEB_PREFIX = "# BGY Monitoring Suite - dati JSON sotto questa riga\n"

MIN_DATE_DEFAULT = "2026-09-30"
TOP_N_PER_DATE_DEFAULT = 10

DISCLAIMER_MESSAGE = (
    "DATI DI PROVA NON REALI\n"
    "Siamo in fase di test del sistema di monitoraggio. I dati pubblicati "
    "sono il risultato di elaborazioni automatiche in corso di validazione "
    "e possono contenere errori. La raccolta dei dati per i grafici e' "
    "iniziata il 30 settembre 2026. Non e' possibile visualizzare periodi "
    "precedenti a questa data."
)

RUNWAY_SIDE_MAP = {
    "RWY 28": "Bergamo",
    "RWY 10": "Seriate",
}

RUNWAYS_TO_MONITOR = ["RWY 28", "RWY 10", "RWY 16", "RWY 34"]

CATEGORY_FILTERS = [
    ("passeggeri", "tipo_movimento = 'Passeggeri'"),
    ("cargo", "tipo_movimento LIKE 'Cargo%%'"),
    ("charter", "tipo_movimento LIKE 'Charter%%'"),
    ("non_classificato", "tipo_movimento = 'Non classificato'"),
]

NIGHT_HOURS = [23, 0, 1, 2, 3, 4, 5]


def _query(sql, params=None):
    ok, rows = bgy_db.execute_query(sql, params)
    if not ok:
        logger.error(f"Errore query: {rows}")
        return []
    return rows or []


def _get_web_config():
    from bgy_core.bgy_config_manager import config_manager
    try:
        cfg = config_manager.get_data_config().get("web_export", {}) or {}
    except Exception:
        cfg = {}
    return {
        "min_date": cfg.get("min_date", MIN_DATE_DEFAULT),
        "top_n_per_date": int(cfg.get("top_n_per_date", TOP_N_PER_DATE_DEFAULT)),
    }


def _wind_cardinal(deg):
    if deg is None:
        return None
    try:
        d = float(deg) % 360
    except (ValueError, TypeError):
        return None
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((d + 22.5) // 45) % 8
    return dirs[idx]


def _get_country(destination):
    try:
        from bgy_core.bgy_update_rules import get_country
        return get_country(destination) or "N/D"
    except Exception:
        return "N/D"


def _side_from_runway(runway):
    if not runway:
        return "N/D"
    r = str(runway).strip()
    return RUNWAY_SIDE_MAP.get(r, "N/D")


def _side_key(side):
    if side == "Bergamo":
        return "bergamo"
    if side == "Seriate":
        return "seriate"
    return "nd"


def _normalize_direction(dir_sacbo, fase_volo):
    d = (dir_sacbo or "").strip().upper()
    if d in ("D", "A"):
        return d
    f = (fase_volo or "").strip()
    if f == "Decollo":
        return "D"
    if f in ("Atterraggio", "Avvicinamento"):
        return "A"
    return "?"


def _category_from_tipo(tipo_movimento):
    t = str(tipo_movimento or "").strip()
    if t == "Passeggeri":
        return "passeggeri"
    if t.startswith("Cargo"):
        return "cargo"
    if t.startswith("Charter"):
        return "charter"
    if t == "Non classificato":
        return "non_classificato"
    return None


def _session_date_for_ts(ts, fallback_date):
    if ts is None:
        return fallback_date
    try:
        if isinstance(ts, str):
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        else:
            dt = ts
    except Exception:
        return fallback_date
    if dt.hour >= 12:
        return dt.strftime("%Y-%m-%d")
    return (dt - timedelta(days=1)).strftime("%Y-%m-%d")


def _date_str(v):
    if v is None:
        return None
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    return str(v)


def _empty_by_date_item(date_str):
    item = {
        "date": date_str,
        "totale": 0,
        "a_tabellone": 0,
        "solo_radar": 0,
        "schedulato": 0,
        "schedulato_D": 0,
        "schedulato_A": 0,
        "sconfinamenti": 0,
        "sconfinamenti_gravi": 0,
        "anomalie": 0,
        "D": 0, "A": 0,
        "D_radar": 0, "A_radar": 0,
        "side_bergamo": 0, "side_bergamo_D": 0, "side_bergamo_A": 0,
        "side_seriate": 0, "side_seriate_D": 0, "side_seriate_A": 0,
        "side_nd": 0, "side_nd_D": 0, "side_nd_A": 0,
    }
    for cat in ("passeggeri", "cargo", "charter", "non_classificato"):
        item["D_" + cat] = 0
        item["A_" + cat] = 0
    return item


def build_disclaimer(min_date):
    return {
        "test_phase": True,
        "min_date": min_date,
        "message": DISCLAIMER_MESSAGE,
    }


def build_summary(date_from, date_to):
    rows = _query(
        """SELECT
              COUNT(*) FILTER (WHERE notte_categoria = 'regolare' AND is_scheduled = TRUE) AS sched,
              COUNT(*) FILTER (WHERE notte_categoria = 'sconfinamento' AND is_scheduled = TRUE) AS sconf,
              COUNT(*) FILTER (WHERE notte_categoria = 'sconfinamento_grave' AND is_scheduled = TRUE) AS gravi,
              MAX(stima_rumore_db) AS rumore_max
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s""",
        (date_from, date_to))
    sched = sconf = gravi = 0
    rumore_max = 0
    if rows:
        sched = int(rows[0][0] or 0)
        sconf = int(rows[0][1] or 0)
        gravi = int(rows[0][2] or 0)
        rumore_max = int(rows[0][3] or 0)

    return {
        "giorni": (datetime.strptime(date_to, "%Y-%m-%d")
                    - datetime.strptime(date_from, "%Y-%m-%d")).days + 1,
        "schedulato": sched,
        "sconfinamenti": sconf,
        "sconfinamenti_gravi": gravi,
        "sconfinamenti_totali": sconf + gravi,
        "rumore_max_db": rumore_max,
    }


def build_block_night_movements(date_from, date_to):
    """
    Movimenti notturni. Tutti i campi pubblici contano SOLO is_scheduled=TRUE.
    I voli solo-radar sono tracciati separatamente (solo_radar, D_radar, A_radar).
    """
    rows = _query(
        """SELECT data_riferimento, pista, direzione_sacbo, fase_volo,
                  notte_categoria, is_scheduled, tipo_movimento, COUNT(*)
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
           GROUP BY data_riferimento, pista, direzione_sacbo, fase_volo,
                    notte_categoria, is_scheduled, tipo_movimento""",
        (date_from, date_to))

    by_date_acc = {}
    totals = {
        "totale": 0, "a_tabellone": 0, "solo_radar": 0,
        "schedulato": 0, "schedulato_D": 0, "schedulato_A": 0,
        "sconfinamenti": 0, "sconfinamenti_gravi": 0,
        "anomalie": 0, "D": 0, "A": 0, "D_radar": 0, "A_radar": 0,
    }
    by_side_acc = {
        "bergamo": {"totale": 0, "D": 0, "A": 0},
        "seriate": {"totale": 0, "D": 0, "A": 0},
        "nd": {"totale": 0, "D": 0, "A": 0},
    }

    for r in rows:
        ds = _date_str(r[0])
        pista = r[1]
        dir_sacbo = r[2]
        fase = r[3]
        notte_cat = r[4] or ""
        is_sched = r[5]
        tipo_mov = r[6] or ""
        n = int(r[7] or 0)

        d = _normalize_direction(dir_sacbo, fase)
        side = _side_from_runway(pista)
        sk = _side_key(side)

        item = by_date_acc.setdefault(ds, _empty_by_date_item(ds))
        item["totale"] += n
        totals["totale"] += n

        if is_sched is True:
            item["a_tabellone"] += n
            totals["a_tabellone"] += n

            if d == "D":
                item["D"] += n
                totals["D"] += n
            elif d == "A":
                item["A"] += n
                totals["A"] += n

            item["side_" + sk] += n
            if d == "D":
                item["side_" + sk + "_D"] += n
            elif d == "A":
                item["side_" + sk + "_A"] += n
            by_side_acc[sk]["totale"] += n
            if d == "D":
                by_side_acc[sk]["D"] += n
            elif d == "A":
                by_side_acc[sk]["A"] += n

            if notte_cat == "regolare":
                item["schedulato"] += n
                totals["schedulato"] += n
                if d == "D":
                    item["schedulato_D"] += n
                    totals["schedulato_D"] += n
                elif d == "A":
                    item["schedulato_A"] += n
                    totals["schedulato_A"] += n
            elif notte_cat == "sconfinamento":
                item["sconfinamenti"] += n
                totals["sconfinamenti"] += n
            elif notte_cat == "sconfinamento_grave":
                item["sconfinamenti_gravi"] += n
                totals["sconfinamenti_gravi"] += n
            elif notte_cat == "anomalia":
                item["anomalie"] += n
                totals["anomalie"] += n

            cat = _category_from_tipo(tipo_mov)
            if cat and d in ("D", "A"):
                item[d + "_" + cat] += n

        else:
            item["solo_radar"] += n
            totals["solo_radar"] += n
            if d == "D":
                item["D_radar"] += n
                totals["D_radar"] += n
            elif d == "A":
                item["A_radar"] += n
                totals["A_radar"] += n

    by_date = [by_date_acc[ds] for ds in sorted(by_date_acc.keys())]
    by_hour = _build_by_hour(date_from, date_to)

    return {
        "by_date": by_date,
        "totals": totals,
        "by_side": by_side_acc,
        "by_hour": by_hour,
    }


def build_block_night_anomalies(date_from, date_to):
    """
    Elenco voli classificati come 'anomalia' (a tabellone 3+ ore dopo
    l'orario previsto, non cancellati). Include dettagli per la UI.
    """
    rows = _query(
        """SELECT data_riferimento, callsign, compagnia_aerea,
                  direzione_sacbo, fase_volo, orario_schedulato
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND is_scheduled = TRUE
             AND notte_categoria = 'anomalia'
           ORDER BY data_riferimento, orario_schedulato""",
        (date_from, date_to))

    items = []
    for r in rows:
        ds = _date_str(r[0])
        callsign = r[1] or "N/D"
        airline = r[2] or "N/D"
        dir_sacbo = r[3]
        fase = r[4]
        sched = r[5]

        direction = _normalize_direction(dir_sacbo, fase)

        sched_str = None
        if sched is not None:
            if hasattr(sched, "strftime"):
                sched_str = sched.strftime("%H:%M")
            else:
                sched_str = str(sched)[:5]

        items.append({
            "date": ds,
            "callsign": callsign,
            "airline": airline,
            "direction": direction,
            "scheduled": sched_str,
        })

    return {"totals": len(items), "items": items}


def _build_by_hour(date_from, date_to):
    cat_selects = []
    for cat_key, cat_filter in CATEGORY_FILTERS:
        cat_selects.append(
            f"""COUNT(*) FILTER (WHERE {cat_filter}) AS {cat_key}_n"""
        )

    sql = f"""
        SELECT
          CASE
            WHEN timestamp IS NOT NULL
              THEN EXTRACT(HOUR FROM timestamp)
            WHEN orario_schedulato IS NOT NULL
              THEN EXTRACT(HOUR FROM orario_schedulato)
            ELSE NULL
          END AS h,
          CASE
            WHEN direzione_sacbo IN ('D', 'A') THEN direzione_sacbo
            WHEN fase_volo = 'Decollo' THEN 'D'
            WHEN fase_volo IN ('Atterraggio', 'Avvicinamento') THEN 'A'
            ELSE '?'
          END AS dir,
          {', '.join(cat_selects)},
          COUNT(*) AS total
        FROM nightly_reports
        WHERE data_riferimento BETWEEN %s AND %s
          AND is_scheduled = TRUE
          AND (tipo_movimento = 'Passeggeri'
               OR tipo_movimento LIKE 'Cargo%%'
               OR tipo_movimento LIKE 'Charter%%'
               OR tipo_movimento = 'Non classificato')
        GROUP BY h, dir
        ORDER BY h, dir
    """
    rows = _query(sql, (date_from, date_to))

    data = {}
    for hour in NIGHT_HOURS:
        data[hour] = {
            "hour": hour,
            "D": {"passeggeri": 0, "cargo": 0, "charter": 0, "non_classificato": 0, "total": 0},
            "A": {"passeggeri": 0, "cargo": 0, "charter": 0, "non_classificato": 0, "total": 0},
        }

    for r in rows or []:
        h = int(r[0]) if r[0] is not None else None
        if h is None or h not in data:
            continue
        d = r[1] or '?'
        if d not in ('D', 'A'):
            continue
        cats = ["passeggeri", "cargo", "charter", "non_classificato"]
        for i, cat in enumerate(cats):
            val = int(r[2 + i] or 0)
            data[h][d][cat] += val
        data[h][d]["total"] += int(r[6] or 0)

    return [data[h] for h in NIGHT_HOURS]


def build_block_night_destinations(date_from, date_to, top_n):
    rows = _query(
        """SELECT data_riferimento, destinazione_finale, COUNT(*) AS n
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND is_scheduled = TRUE
             AND destinazione_finale IS NOT NULL
             AND destinazione_finale != ''
             AND destinazione_finale != 'N/D'
             AND (tipo_movimento = 'Passeggeri'
                  OR tipo_movimento LIKE 'Cargo%%'
                  OR tipo_movimento LIKE 'Charter%%')
           GROUP BY data_riferimento, destinazione_finale
           ORDER BY data_riferimento, n DESC""",
        (date_from, date_to))

    by_date_map = {}
    for r in rows:
        ds = _date_str(r[0])
        dest = r[1]
        n = int(r[2] or 0)
        by_date_map.setdefault(ds, []).append({
            "city": dest,
            "country": _get_country(dest),
            "n": n,
        })

    by_date = []
    for ds in sorted(by_date_map.keys()):
        items = sorted(by_date_map[ds], key=lambda x: (-x["n"], x["city"]))
        by_date.append({"date": ds, "top": items[:top_n]})

    rows = _query(
        """SELECT destinazione_finale, COUNT(*) AS n
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND is_scheduled = TRUE
             AND destinazione_finale IS NOT NULL
             AND destinazione_finale != ''
             AND destinazione_finale != 'N/D'
             AND (tipo_movimento = 'Passeggeri'
                  OR tipo_movimento LIKE 'Cargo%%'
                  OR tipo_movimento LIKE 'Charter%%')
           GROUP BY destinazione_finale
           ORDER BY n DESC""",
        (date_from, date_to))

    totals = []
    for r in rows:
        dest = r[0]
        n = int(r[1] or 0)
        del_rows = _query(
            """SELECT COUNT(*) FROM nightly_reports
               WHERE data_riferimento BETWEEN %s AND %s
                 AND destinazione_finale = %s
                 AND notte_categoria IN ('sconfinamento','sconfinamento_grave')""",
            (date_from, date_to, dest))
        delayed = int(del_rows[0][0] or 0) if del_rows else 0
        totals.append({
            "city": dest,
            "country": _get_country(dest),
            "n": n,
            "delayed": delayed,
        })

    return {"by_date": by_date, "totals": totals}


def build_block_destinations_pax(date_from, date_to, top_cities=15, top_countries=10):
    """
    Destinazioni dei soli voli PASSEGGERI a tabellone, split per direzione.
    Ritorna {D: {by_city, by_country}, A: {by_city, by_country}, note}.
    """
    dir_case = """
        CASE
          WHEN direzione_sacbo IN ('D', 'A') THEN direzione_sacbo
          WHEN fase_volo = 'Decollo' THEN 'D'
          WHEN fase_volo IN ('Atterraggio', 'Avvicinamento') THEN 'A'
          ELSE '?'
        END
    """

    rows = _query(
        f"""SELECT destinazione_finale, stato_destinazione,
                   ({dir_case}) AS dir,
                   COUNT(*) AS n
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND is_scheduled = TRUE
             AND tipo_movimento = 'Passeggeri'
             AND destinazione_finale IS NOT NULL
             AND destinazione_finale != ''
             AND destinazione_finale != 'N/D'
           GROUP BY destinazione_finale, stato_destinazione, dir
           ORDER BY n DESC""",
        (date_from, date_to))

    acc = {
        "D": {"by_city": [], "by_country_acc": {}},
        "A": {"by_city": [], "by_country_acc": {}},
    }

    for r in rows:
        city = r[0]
        country = r[1] or "N/D"
        direction = r[2] if r[2] in ("D", "A") else None
        n = int(r[3] or 0)
        if direction is None:
            continue
        acc[direction]["by_city"].append({
            "city": city,
            "country": country,
            "n": n,
        })
        acc[direction]["by_country_acc"][country] = (
            acc[direction]["by_country_acc"].get(country, 0) + n
        )

    result = {}
    for dir_key in ("D", "A"):
        by_city = acc[dir_key]["by_city"]
        by_city.sort(key=lambda x: (-x["n"], x["city"]))
        by_country = [
            {"country": k, "n": v}
            for k, v in acc[dir_key]["by_country_acc"].items()
        ]
        by_country.sort(key=lambda x: -x["n"])
        result[dir_key] = {
            "by_city": by_city[:top_cities],
            "by_country": by_country[:top_countries],
        }

    result["note"] = (
        "Il grafico mostra le destinazioni dei soli voli passeggeri "
        "dichiarati dal tabellone SACBO nel periodo selezionato. "
        "Partenze e arrivi sono separati. Cargo e charter sono esclusi."
    )
    return result


def build_block_night_airlines(date_from, date_to, top_n):
    dir_case = """
        CASE
          WHEN direzione_sacbo IN ('D', 'A') THEN direzione_sacbo
          WHEN fase_volo = 'Decollo' THEN 'D'
          WHEN fase_volo IN ('Atterraggio', 'Avvicinamento') THEN 'A'
          ELSE '?'
        END
    """

    rows = _query(
        f"""SELECT data_riferimento, compagnia_aerea,
                  COUNT(*) FILTER (WHERE ({dir_case}) = 'D') AS n_d,
                  COUNT(*) FILTER (WHERE ({dir_case}) = 'A') AS n_a,
                  COUNT(*) AS n
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND is_scheduled = TRUE
             AND compagnia_aerea IS NOT NULL
             AND compagnia_aerea != ''
             AND compagnia_aerea != 'N/D'
             AND compagnia_aerea NOT LIKE 'Compagnia %%'
             AND (tipo_movimento = 'Passeggeri'
                  OR tipo_movimento LIKE 'Cargo%%'
                  OR tipo_movimento LIKE 'Charter%%')
           GROUP BY data_riferimento, compagnia_aerea
           ORDER BY data_riferimento, n DESC""",
        (date_from, date_to))

    by_date_map = {}
    for r in rows:
        ds = _date_str(r[0])
        airline = r[1]
        n_d = int(r[2] or 0)
        n_a = int(r[3] or 0)
        n = int(r[4] or 0)
        by_date_map.setdefault(ds, []).append({
            "airline": airline,
            "n": n,
            "D": n_d,
            "A": n_a,
        })

    by_date = []
    for ds in sorted(by_date_map.keys()):
        items = sorted(by_date_map[ds], key=lambda x: (-x["n"], x["airline"]))
        by_date.append({"date": ds, "top": items[:top_n]})

    rows = _query(
        f"""SELECT compagnia_aerea,
                  COUNT(*) FILTER (WHERE ({dir_case}) = 'D') AS n_d,
                  COUNT(*) FILTER (WHERE ({dir_case}) = 'A') AS n_a,
                  COUNT(*) AS n
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND is_scheduled = TRUE
             AND compagnia_aerea IS NOT NULL
             AND compagnia_aerea != ''
             AND compagnia_aerea != 'N/D'
             AND compagnia_aerea NOT LIKE 'Compagnia %%'
             AND (tipo_movimento = 'Passeggeri'
                  OR tipo_movimento LIKE 'Cargo%%'
                  OR tipo_movimento LIKE 'Charter%%')
           GROUP BY compagnia_aerea
           ORDER BY n DESC""",
        (date_from, date_to))

    totals = []
    for r in rows:
        airline = r[0]
        n_d = int(r[1] or 0)
        n_a = int(r[2] or 0)
        n = int(r[3] or 0)
        del_rows = _query(
            """SELECT COUNT(*) FROM nightly_reports
               WHERE data_riferimento BETWEEN %s AND %s
                 AND compagnia_aerea = %s
                 AND notte_categoria IN ('sconfinamento','sconfinamento_grave')""",
            (date_from, date_to, airline))
        delayed = int(del_rows[0][0] or 0) if del_rows else 0
        totals.append({
            "airline": airline,
            "n": n,
            "D": n_d,
            "A": n_a,
            "delayed": delayed,
        })

    return {"by_date": by_date, "totals": totals}


def _load_weather(date_from, date_to):
    rows = _query(
        """SELECT data_riferimento, orario, temperatura_c, precipitazioni_mm,
                  vento_kmh, vento_direzione_deg, condizioni
           FROM weather_hourly
           WHERE data_riferimento BETWEEN %s AND %s
           ORDER BY data_riferimento, orario""",
        (date_from, date_to))
    w = {}
    for r in rows:
        ds = _date_str(r[0])
        ora = r[1]
        hour = ora.hour if hasattr(ora, "hour") else int(str(ora).split(":")[0])
        w[(ds, hour)] = {
            "temp_c": float(r[2]) if r[2] is not None else None,
            "rain_mm": float(r[3]) if r[3] is not None else None,
            "wind_kmh": float(r[4]) if r[4] is not None else None,
            "wind_dir_deg": int(r[5]) if r[5] is not None else None,
            "conditions": r[6] or "",
        }
    return w


def build_block_night_weather(date_from, date_to):
    weather = _load_weather(date_from, date_to)

    rows = _query(
        """SELECT data_riferimento, temperatura_c, precipitazioni_mm,
                  vento_kmh, vento_direzione_deg, condizioni
           FROM weather_hourly
           WHERE data_riferimento BETWEEN %s AND %s
             AND EXTRACT(HOUR FROM orario) = 20
           ORDER BY data_riferimento""",
        (date_from, date_to))

    at_20 = []
    for r in rows:
        ds = _date_str(r[0])
        wd = int(r[4]) if r[4] is not None else None

        runway_rows = _query(
            """SELECT pista, COUNT(*) FROM radar_detections
               WHERE data_riferimento = %s
                 AND sessione_notturna IS NOT NULL
                 AND pista IN ('RWY 28', 'RWY 10')
               GROUP BY pista
               ORDER BY COUNT(*) DESC
               LIMIT 1""",
            (ds,))
        runway = runway_rows[0][0] if runway_rows else None
        side = _side_from_runway(runway)

        at_20.append({
            "date": ds,
            "temp_c": float(r[1]) if r[1] is not None else None,
            "rain_mm": float(r[2]) if r[2] is not None else None,
            "wind_kmh": float(r[3]) if r[3] is not None else None,
            "wind_dir_deg": wd,
            "wind_dir_cardinal": _wind_cardinal(wd),
            "conditions": r[5] or "",
            "runway_used": runway,
            "side_used": side,
        })

    rows = _query(
        """SELECT data_riferimento, callsign, compagnia_aerea,
                  direzione_sacbo, orario_schedulato, timestamp,
                  fase_volo, pista
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND is_scheduled = TRUE
             AND (tipo_movimento = 'Passeggeri'
                  OR tipo_movimento LIKE 'Cargo%%'
                  OR tipo_movimento LIKE 'Charter%%')
           ORDER BY data_riferimento, orario_schedulato""",
        (date_from, date_to))

    per_flight = []
    summary_acc = {}

    for r in rows:
        ds = _date_str(r[0])
        callsign = r[1]
        airline = r[2]
        dir_sacbo = r[3]
        sched = r[4]
        ts = r[5]
        fase = r[6]
        pista = r[7]

        hour = None
        session_date = ds
        if ts is not None:
            session_date = _session_date_for_ts(ts, ds)
            try:
                if isinstance(ts, str):
                    hour = int(ts.split()[1].split(":")[0])
                else:
                    hour = ts.hour
            except Exception:
                hour = None
        if hour is None and sched is not None:
            try:
                if hasattr(sched, "hour"):
                    hour = sched.hour
                else:
                    hour = int(str(sched).split(":")[0])
            except Exception:
                hour = None

        if hour is None:
            continue

        w = weather.get((session_date, hour))
        if not w:
            continue

        direction = _normalize_direction(dir_sacbo, fase)
        side = _side_from_runway(pista)

        sched_str = None
        if sched is not None:
            if hasattr(sched, "strftime"):
                sched_str = sched.strftime("%H:%M")
            else:
                sched_str = str(sched)[:5]

        per_flight.append({
            "date": ds,
            "callsign": callsign,
            "airline": airline,
            "direction": direction,
            "scheduled": sched_str,
            "runway": pista or None,
            "side": side,
            "temp_c": w["temp_c"],
            "wind_kmh": w["wind_kmh"],
            "wind_dir_deg": w["wind_dir_deg"],
            "wind_dir_cardinal": _wind_cardinal(w["wind_dir_deg"]),
            "rain_mm": w["rain_mm"],
            "conditions": w["conditions"],
        })

        acc = summary_acc.setdefault(ds, {
            "temp_sum": 0.0, "wind_sum": 0.0, "n": 0,
            "rain_ops": 0, "clear_ops": 0,
        })
        if w["temp_c"] is not None:
            acc["temp_sum"] += w["temp_c"]
        if w["wind_kmh"] is not None:
            acc["wind_sum"] += w["wind_kmh"]
        acc["n"] += 1
        if w["rain_mm"] is not None and w["rain_mm"] > 0:
            acc["rain_ops"] += 1
        else:
            acc["clear_ops"] += 1

    summary_by_date = []
    for ds in sorted(summary_acc.keys()):
        acc = summary_acc[ds]
        n = acc["n"] or 1
        summary_by_date.append({
            "date": ds,
            "temp_avg": round(acc["temp_sum"] / n, 1),
            "wind_avg_kmh": round(acc["wind_sum"] / n, 1),
            "ops_in_rain": acc["rain_ops"],
            "ops_in_clear": acc["clear_ops"],
        })

    return {
        "at_20": at_20,
        "per_flight": per_flight,
        "summary_by_date": summary_by_date,
    }


def build_block_runway_diagnostics(date_from, date_to):
    rows = _query(
        """SELECT data_riferimento, pista, COUNT(*)
           FROM radar_detections
           WHERE data_riferimento BETWEEN %s AND %s
             AND sessione_notturna IS NOT NULL
           GROUP BY data_riferimento, pista
           ORDER BY data_riferimento""",
        (date_from, date_to))

    by_date_map = {}
    totals = {rwy: 0 for rwy in RUNWAYS_TO_MONITOR}
    totals["N/D"] = 0
    totals["altro"] = 0

    for r in rows:
        ds = _date_str(r[0])
        pista = r[1]
        n = int(r[2] or 0)

        key = pista if pista in RUNWAYS_TO_MONITOR else (
            "N/D" if not pista or pista == "" else "altro"
        )

        item = by_date_map.setdefault(ds, {rwy: 0 for rwy in RUNWAYS_TO_MONITOR})
        item.setdefault("N/D", 0)
        item.setdefault("altro", 0)
        item["date"] = ds
        item[key] = item.get(key, 0) + n

        totals[key] = totals.get(key, 0) + n

    by_date = []
    for ds in sorted(by_date_map.keys()):
        item = by_date_map[ds]
        row = {"date": ds}
        for rwy in RUNWAYS_TO_MONITOR:
            row[rwy] = item.get(rwy, 0)
        row["N/D"] = item.get("N/D", 0)
        row["altro"] = item.get("altro", 0)
        by_date.append(row)

    return {"by_date": by_date, "totals": totals}


def build_web_json(days=90):
    today = datetime.now().date()
    date_to = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    date_from_calc = (today - timedelta(days=days)).strftime("%Y-%m-%d")

    web_cfg = _get_web_config()
    min_date = web_cfg["min_date"]
    top_n = web_cfg["top_n_per_date"]
    date_from = max(date_from_calc, min_date)

    logger.info(f"Costruzione JSON web: {date_from} -> {date_to} "
                f"(max {days} giorni, min_date={min_date}, top_n={top_n})")

    disclaimer = build_disclaimer(min_date)
    summary = build_summary(date_from, date_to)
    movements = build_block_night_movements(date_from, date_to)
    anomalies = build_block_night_anomalies(date_from, date_to)
    destinations = build_block_night_destinations(date_from, date_to, top_n)
    destinations_pax = build_block_destinations_pax(date_from, date_to)
    airlines = build_block_night_airlines(date_from, date_to, top_n)
    weather = build_block_night_weather(date_from, date_to)
    runway_diag = build_block_runway_diagnostics(date_from, date_to)

    n_dest_pax_D = len(destinations_pax.get("D", {}).get("by_city", []))
    n_dest_pax_A = len(destinations_pax.get("A", {}).get("by_city", []))

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "period": {"from": date_from, "to": date_to},
        "min_date_active": min_date,
        "disclaimer": disclaimer,
        "summary": summary,
        "block_night_movements": movements,
        "block_night_anomalies": anomalies,
        "block_night_destinations": destinations,
        "block_destinations_pax": destinations_pax,
        "block_night_airlines": airlines,
        "block_night_weather": weather,
        "block_runway_diagnostics": runway_diag,
    }

    logger.info(
        f"JSON web: {len(movements['by_date'])} giorni, "
        f"{anomalies['totals']} anomalie, "
        f"{len(destinations['totals'])} destinazioni (mix), "
        f"{n_dest_pax_D} dest. pax D, "
        f"{n_dest_pax_A} dest. pax A, "
        f"{len(airlines['totals'])} compagnie, "
        f"{len(weather['per_flight'])} voli con meteo"
    )
    return payload


def save_web_json(payload):
    os.makedirs(WEB_OUTPUT_DIR, exist_ok=True)
    try:
        with open(WEB_OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(WEB_PREFIX)
            json.dump(payload, f, ensure_ascii=False, indent=2)
        size_kb = round(os.path.getsize(WEB_OUTPUT_FILE) / 1024, 1)
        logger.info(f"JSON salvato: {WEB_OUTPUT_FILE} ({size_kb} KB)")
        return WEB_OUTPUT_FILE
    except Exception as e:
        logger.error(f"Errore salvataggio JSON: {e}")
        return None


def export_and_publish(days=90):
    from bgy_core import bgy_wordpress

    payload = build_web_json(days=days)
    if not payload:
        return False, "JSON vuoto"

    local_path = save_web_json(payload)
    if not local_path:
        return False, "Errore salvataggio JSON locale"

    if not bgy_wordpress.is_enabled():
        logger.info("WordPress disabilitato, salto pubblicazione")
        return True, f"JSON locale salvato ({local_path}), WordPress disabilitato"

    ok, msg, url = bgy_wordpress.publish_json(local_path)
    if ok:
        return True, f"Pubblicato: {url}"
    return False, f"Errore pubblicazione: {msg}"


def main():
    parser = argparse.ArgumentParser(
        description="Esportazione dati aggregati per il web (F17)")
    parser.add_argument("--days", type=int, default=90,
                        help="Giorni da includere (default: 90)")
    parser.add_argument("--publish", action="store_true",
                        help="Pubblica anche su WordPress")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo build locale, senza pubblicare")
    args = parser.parse_args()

    if not bgy_db.is_enabled():
        print("DB non abilitato")
        sys.exit(1)

    if args.dry_run or not args.publish:
        payload = build_web_json(days=args.days)
        path = save_web_json(payload)
        if path:
            print(f"JSON salvato: {path}")
            print(f"   Dimensione: {round(os.path.getsize(path)/1024, 1)} KB")
        else:
            print("Errore salvataggio JSON")
            sys.exit(1)
        sys.exit(0)

    ok, msg = export_and_publish(days=args.days)
    print(f"{'OK' if ok else 'ERRORE'}: {msg}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()