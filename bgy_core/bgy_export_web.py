"""
bgy_core/bgy_export_web.py - Esportazione dati aggregati per il web (F17).
Versione 1.2.12

Novità v1.2.12 (05/10/2026):
- Cargo, charter e non classificati radar-only (is_scheduled=FALSE) ora
  contribuiscono alle KPI di dettaglio D_cargo/A_cargo, D_charter/A_charter,
  D_non_classificato/A_non_classificato. Necessario perché SACBO non pubblica
  cargo: tutti i cargo sono radar-only.
- _build_by_hour: rimossa la condizione is_scheduled = TRUE. Anche cargo,
  charter e non classificati radar-only entrano nel grafico orario.
  I "Passeggeri (radar)" (duplicati del matching) restano esclusi perché
  la WHERE usa tipo_movimento = 'Passeggeri' (esatto).
- build_block_night_airlines: rimossa la condizione is_scheduled = TRUE.
  Le compagnie cargo (Maersk, DHL, ecc.) ora appaiono nel grafico compagnie.

Novità v1.2.11:
- _build_by_hour() ritorna {by_date: [...], totals: [...]}. Il filtro JS
  ritaglia la distribuzione oraria sul periodo selezionato.

Novità v1.2.10:
- build_block_night_movements: aggiunti sconfinamenti_D/A,
  sconfinamenti_gravi_D/A in totals e by_date.

Novità v1.2.9:
- build_block_destinations_pax: struttura by_date per filtro JS.

Novità v1.2.8:
- Aggiunti totals.schedulato_D/A, block_night_anomalies.

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

RUNWAY_SIDE_MAP = {"RWY 28": "Bergamo", "RWY 10": "Seriate"}
RUNWAYS_TO_MONITOR = ["RWY 28", "RWY 10", "RWY 16", "RWY 34"]

CATEGORY_FILTERS = [
    ("passeggeri", "tipo_movimento = 'Passeggeri'"),
    ("cargo", "tipo_movimento LIKE 'Cargo%%'"),
    ("charter", "tipo_movimento LIKE 'Charter%%'"),
    ("non_classificato", "tipo_movimento = 'Non classificato'"),
]

CATS_KEYS = ["passeggeri", "cargo", "charter", "non_classificato"]

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
    return dirs[int((d + 22.5) // 45) % 8]


def _get_country(destination):
    try:
        from bgy_core.bgy_update_rules import get_country
        return get_country(destination) or "N/D"
    except Exception:
        return "N/D"


def _side_from_runway(runway):
    if not runway:
        return "N/D"
    return RUNWAY_SIDE_MAP.get(str(runway).strip(), "N/D")


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
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S") if isinstance(ts, str) else ts
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
        "totale": 0, "a_tabellone": 0, "solo_radar": 0,
        "schedulato": 0, "schedulato_D": 0, "schedulato_A": 0,
        "sconfinamenti": 0, "sconfinamenti_D": 0, "sconfinamenti_A": 0,
        "sconfinamenti_gravi": 0, "sconfinamenti_gravi_D": 0, "sconfinamenti_gravi_A": 0,
        "anomalie": 0,
        "D": 0, "A": 0, "D_radar": 0, "A_radar": 0,
        "side_bergamo": 0, "side_bergamo_D": 0, "side_bergamo_A": 0,
        "side_seriate": 0, "side_seriate_D": 0, "side_seriate_A": 0,
        "side_nd": 0, "side_nd_D": 0, "side_nd_A": 0,
    }
    for cat in ("passeggeri", "cargo", "charter", "non_classificato"):
        item["D_" + cat] = 0
        item["A_" + cat] = 0
    return item


def build_disclaimer(min_date):
    return {"test_phase": True, "min_date": min_date, "message": DISCLAIMER_MESSAGE}


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
    sched = sconf = gravi = rumore_max = 0
    if rows:
        sched = int(rows[0][0] or 0)
        sconf = int(rows[0][1] or 0)
        gravi = int(rows[0][2] or 0)
        rumore_max = int(rows[0][3] or 0)
    return {
        "giorni": (datetime.strptime(date_to, "%Y-%m-%d") - datetime.strptime(date_from, "%Y-%m-%d")).days + 1,
        "schedulato": sched,
        "sconfinamenti": sconf,
        "sconfinamenti_gravi": gravi,
        "sconfinamenti_totali": sconf + gravi,
        "rumore_max_db": rumore_max,
    }


def build_block_night_movements(date_from, date_to):
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
        "sconfinamenti": 0, "sconfinamenti_D": 0, "sconfinamenti_A": 0,
        "sconfinamenti_gravi": 0, "sconfinamenti_gravi_D": 0, "sconfinamenti_gravi_A": 0,
        "anomalie": 0, "D": 0, "A": 0, "D_radar": 0, "A_radar": 0,
    }
    by_side_acc = {
        "bergamo": {"totale": 0, "D": 0, "A": 0},
        "seriate": {"totale": 0, "D": 0, "A": 0},
        "nd": {"totale": 0, "D": 0, "A": 0},
    }

    # v1.2.12: categorie che contribuiscono alle KPI di dettaglio anche se
    # radar-only. I passeggeri radar-only sono duplicati del matching e
    # restano esclusi (tipo_movimento = 'Passeggeri (radar)' non è in questa
    # lista e non è catturato da _category_from_tipo).
    RADAR_ONLY_KPI_CATS = ("cargo", "charter", "non_classificato")

    for r in rows:
        ds = _date_str(r[0])
        pista, dir_sacbo, fase = r[1], r[2], r[3]
        notte_cat = r[4] or ""
        is_sched = r[5]
        tipo_mov = r[6] or ""
        n = int(r[7] or 0)

        d = _normalize_direction(dir_sacbo, fase)
        sk = _side_key(_side_from_runway(pista))
        item = by_date_acc.setdefault(ds, _empty_by_date_item(ds))
        item["totale"] += n
        totals["totale"] += n

        cat = _category_from_tipo(tipo_mov)

        if is_sched is True:
            item["a_tabellone"] += n
            totals["a_tabellone"] += n
            if d == "D":
                item["D"] += n; totals["D"] += n
            elif d == "A":
                item["A"] += n; totals["A"] += n

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
                item["schedulato"] += n; totals["schedulato"] += n
                if d == "D":
                    item["schedulato_D"] += n; totals["schedulato_D"] += n
                elif d == "A":
                    item["schedulato_A"] += n; totals["schedulato_A"] += n
            elif notte_cat == "sconfinamento":
                item["sconfinamenti"] += n; totals["sconfinamenti"] += n
                if d == "D":
                    item["sconfinamenti_D"] += n; totals["sconfinamenti_D"] += n
                elif d == "A":
                    item["sconfinamenti_A"] += n; totals["sconfinamenti_A"] += n
            elif notte_cat == "sconfinamento_grave":
                item["sconfinamenti_gravi"] += n; totals["sconfinamenti_gravi"] += n
                if d == "D":
                    item["sconfinamenti_gravi_D"] += n; totals["sconfinamenti_gravi_D"] += n
                elif d == "A":
                    item["sconfinamenti_gravi_A"] += n; totals["sconfinamenti_gravi_A"] += n
            elif notte_cat == "anomalia":
                item["anomalie"] += n; totals["anomalie"] += n

            if cat and d in ("D", "A"):
                item[d + "_" + cat] += n
        else:
            item["solo_radar"] += n; totals["solo_radar"] += n
            if d == "D":
                item["D_radar"] += n; totals["D_radar"] += n
            elif d == "A":
                item["A_radar"] += n; totals["A_radar"] += n

            # v1.2.12: cargo/charter/non_classificato radar-only contribuiscono
            # alle KPI di dettaglio (passeggeri radar esclusi: duplicati).
            if cat in RADAR_ONLY_KPI_CATS and d in ("D", "A"):
                item[d + "_" + cat] += n

    by_date = [by_date_acc[ds] for ds in sorted(by_date_acc.keys())]
    return {
        "by_date": by_date,
        "totals": totals,
        "by_side": by_side_acc,
        "by_hour": _build_by_hour(date_from, date_to),
    }


def build_block_night_anomalies(date_from, date_to):
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
        sched = r[5]
        sched_str = None
        if sched is not None:
            sched_str = sched.strftime("%H:%M") if hasattr(sched, "strftime") else str(sched)[:5]
        items.append({
            "date": ds,
            "callsign": r[1] or "N/D",
            "airline": r[2] or "N/D",
            "direction": _normalize_direction(r[3], r[4]),
            "scheduled": sched_str,
        })
    return {"totals": len(items), "items": items}


def _empty_hour_slot(hour):
    """Slot vuoto per una singola ora notturna."""
    return {
        "hour": hour,
        "D": {"passeggeri": 0, "cargo": 0, "charter": 0, "non_classificato": 0, "total": 0},
        "A": {"passeggeri": 0, "cargo": 0, "charter": 0, "non_classificato": 0, "total": 0},
    }


def _build_by_hour(date_from, date_to):
    """
    v1.2.12: rimossa la condizione is_scheduled = TRUE. Anche i movimenti
    radar-only (cargo, charter, non classificato) entrano nel grafico orario.
    I passeggeri radar-only restano esclusi perché la WHERE usa
    tipo_movimento = 'Passeggeri' (esatto, esclude 'Passeggeri (radar)').

    v1.2.11: ritorna {by_date: [{date, hours: [7 slot]}], totals: [7 slot]}.
    """
    cat_selects = []
    for cat_key, cat_filter in CATEGORY_FILTERS:
        cat_selects.append(f"COUNT(*) FILTER (WHERE {cat_filter}) AS {cat_key}_n")

    sql = f"""
        SELECT
          data_riferimento,
          CASE
            WHEN timestamp IS NOT NULL THEN EXTRACT(HOUR FROM timestamp)
            WHEN orario_schedulato IS NOT NULL THEN EXTRACT(HOUR FROM orario_schedulato)
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
          AND (tipo_movimento = 'Passeggeri'
               OR tipo_movimento LIKE 'Cargo%%'
               OR tipo_movimento LIKE 'Charter%%'
               OR tipo_movimento = 'Non classificato')
        GROUP BY data_riferimento, h, dir
        ORDER BY data_riferimento, h, dir
    """
    rows = _query(sql, (date_from, date_to))

    by_date_acc = {}
    for r in rows or []:
        ds = _date_str(r[0])
        h = int(r[1]) if r[1] is not None else None
        if h is None or h not in NIGHT_HOURS:
            continue
        d = r[2] or '?'
        if d not in ('D', 'A'):
            continue
        day = by_date_acc.get(ds)
        if day is None:
            day = {"date": ds, "hours": {hh: _empty_hour_slot(hh) for hh in NIGHT_HOURS}}
            by_date_acc[ds] = day
        for i, cat in enumerate(CATS_KEYS):
            day["hours"][h][d][cat] += int(r[3 + i] or 0)
        day["hours"][h][d]["total"] += int(r[7] or 0)

    by_date = []
    for ds in sorted(by_date_acc.keys()):
        entry = by_date_acc[ds]
        hours_list = [entry["hours"][h] for h in NIGHT_HOURS]
        by_date.append({"date": ds, "hours": hours_list})

    totals = {h: _empty_hour_slot(h) for h in NIGHT_HOURS}
    for ds in by_date_acc:
        for h in NIGHT_HOURS:
            for dir_k in ("D", "A"):
                src = by_date_acc[ds]["hours"][h][dir_k]
                dst = totals[h][dir_k]
                for cat in ("passeggeri", "cargo", "charter", "non_classificato", "total"):
                    dst[cat] += src[cat]

    return {
        "by_date": by_date,
        "totals": [totals[h] for h in NIGHT_HOURS],
    }


def build_block_night_destinations(date_from, date_to, top_n):
    rows = _query(
        """SELECT data_riferimento, destinazione_finale, COUNT(*) AS n
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND is_scheduled = TRUE
             AND destinazione_finale IS NOT NULL
             AND destinazione_finale != ''
             AND destinazione_finale != 'N/D'
             AND (tipo_movimento = 'Passeggeri' OR tipo_movimento LIKE 'Cargo%%' OR tipo_movimento LIKE 'Charter%%')
           GROUP BY data_riferimento, destinazione_finale
           ORDER BY data_riferimento, n DESC""",
        (date_from, date_to))
    by_date_map = {}
    for r in rows:
        ds = _date_str(r[0])
        by_date_map.setdefault(ds, []).append({
            "city": r[1], "country": _get_country(r[1]), "n": int(r[2] or 0)})
    by_date = []
    for ds in sorted(by_date_map.keys()):
        items = sorted(by_date_map[ds], key=lambda x: (-x["n"], x["city"]))
        by_date.append({"date": ds, "top": items[:top_n]})
    return {"by_date": by_date}


def build_block_destinations_pax(date_from, date_to, top_cities=15, top_countries=10):
    dir_case = """
        CASE
          WHEN direzione_sacbo IN ('D', 'A') THEN direzione_sacbo
          WHEN fase_volo = 'Decollo' THEN 'D'
          WHEN fase_volo IN ('Atterraggio', 'Avvicinamento') THEN 'A'
          ELSE '?'
        END
    """
    rows = _query(
        f"""SELECT data_riferimento, destinazione_finale, stato_destinazione,
                   ({dir_case}) AS dir, COUNT(*) AS n
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND is_scheduled = TRUE
             AND tipo_movimento = 'Passeggeri'
             AND destinazione_finale IS NOT NULL
             AND destinazione_finale != ''
             AND destinazione_finale != 'N/D'
           GROUP BY data_riferimento, destinazione_finale, stato_destinazione, dir
           ORDER BY data_riferimento, n DESC""",
        (date_from, date_to))
    by_date_acc = {}
    for r in rows:
        ds = _date_str(r[0])
        direction = r[3] if r[3] in ("D", "A") else None
        if direction is None:
            continue
        day = by_date_acc.setdefault(ds, {
            "D": {"by_city": [], "by_country_acc": {}},
            "A": {"by_city": [], "by_country_acc": {}},
        })
        day[direction]["by_city"].append({
            "city": r[1], "country": r[2] or "N/D", "n": int(r[4] or 0)})
        day[direction]["by_country_acc"][r[2] or "N/D"] = (
            day[direction]["by_country_acc"].get(r[2] or "N/D", 0) + int(r[4] or 0))

    by_date = []
    for ds in sorted(by_date_acc.keys()):
        day = by_date_acc[ds]
        item = {"date": ds}
        for dir_key in ("D", "A"):
            by_city = sorted(day[dir_key]["by_city"], key=lambda x: (-x["n"], x["city"]))
            by_country = [{"country": k, "n": v} for k, v in day[dir_key]["by_country_acc"].items()]
            by_country.sort(key=lambda x: -x["n"])
            item[dir_key] = {
                "by_city": by_city[:top_cities],
                "by_country": by_country[:top_countries],
            }
        by_date.append(item)
    return {
        "by_date": by_date,
        "note": ("Il grafico mostra le destinazioni dei soli voli passeggeri "
                 "dichiarati dal tabellone SACBO nel periodo selezionato. "
                 "Partenze e arrivi sono separati. Cargo e charter sono esclusi."),
    }


def build_block_night_airlines(date_from, date_to, top_n):
    """
    v1.2.12: rimossa la condizione is_scheduled = TRUE. Le compagnie cargo
    (Maersk, DHL, ecc.) che operano radar-only ora compaiono nel grafico.
    I passeggeri radar-only restano esclusi perché la WHERE usa
    tipo_movimento = 'Passeggeri' (esatto).
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
        f"""SELECT data_riferimento, compagnia_aerea,
                  COUNT(*) FILTER (WHERE ({dir_case}) = 'D') AS n_d,
                  COUNT(*) FILTER (WHERE ({dir_case}) = 'A') AS n_a,
                  COUNT(*) AS n
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND compagnia_aerea IS NOT NULL
             AND compagnia_aerea != ''
             AND compagnia_aerea != 'N/D'
             AND compagnia_aerea NOT LIKE 'Compagnia %%'
             AND (tipo_movimento = 'Passeggeri'
                  OR tipo_movimento LIKE 'Cargo%%'
                  OR tipo_movimento LIKE 'Charter%%'
                  OR tipo_movimento = 'Non classificato')
           GROUP BY data_riferimento, compagnia_aerea
           ORDER BY data_riferimento, n DESC""",
        (date_from, date_to))
    by_date_map = {}
    for r in rows:
        ds = _date_str(r[0])
        by_date_map.setdefault(ds, []).append({
            "airline": r[1], "n": int(r[4] or 0),
            "D": int(r[2] or 0), "A": int(r[3] or 0)})
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
             AND compagnia_aerea IS NOT NULL
             AND compagnia_aerea != ''
             AND compagnia_aerea != 'N/D'
             AND compagnia_aerea NOT LIKE 'Compagnia %%'
             AND (tipo_movimento = 'Passeggeri'
                  OR tipo_movimento LIKE 'Cargo%%'
                  OR tipo_movimento LIKE 'Charter%%'
                  OR tipo_movimento = 'Non classificato')
           GROUP BY compagnia_aerea
           ORDER BY n DESC""",
        (date_from, date_to))
    totals = [{"airline": r[0], "n": int(r[3] or 0),
               "D": int(r[1] or 0), "A": int(r[2] or 0)} for r in rows]
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
               WHERE data_riferimento = %s AND sessione_notturna IS NOT NULL
                 AND pista IN ('RWY 28', 'RWY 10')
               GROUP BY pista ORDER BY COUNT(*) DESC LIMIT 1""",
            (ds,))
        runway = runway_rows[0][0] if runway_rows else None
        at_20.append({
            "date": ds,
            "temp_c": float(r[1]) if r[1] is not None else None,
            "rain_mm": float(r[2]) if r[2] is not None else None,
            "wind_kmh": float(r[3]) if r[3] is not None else None,
            "wind_dir_deg": wd,
            "wind_dir_cardinal": _wind_cardinal(wd),
            "conditions": r[5] or "",
            "runway_used": runway,
            "side_used": _side_from_runway(runway),
        })

    rows = _query(
        """SELECT data_riferimento, callsign, compagnia_aerea,
                  direzione_sacbo, orario_schedulato, timestamp, fase_volo, pista
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND is_scheduled = TRUE
             AND (tipo_movimento = 'Passeggeri' OR tipo_movimento LIKE 'Cargo%%' OR tipo_movimento LIKE 'Charter%%')
           ORDER BY data_riferimento, orario_schedulato""",
        (date_from, date_to))

    per_flight = []
    summary_acc = {}
    for r in rows:
        ds = _date_str(r[0])
        sched, ts, fase, pista = r[4], r[5], r[6], r[7]
        hour = None
        session_date = ds
        if ts is not None:
            session_date = _session_date_for_ts(ts, ds)
            try:
                hour = int(ts.split()[1].split(":")[0]) if isinstance(ts, str) else ts.hour
            except Exception:
                hour = None
        if hour is None and sched is not None:
            try:
                hour = sched.hour if hasattr(sched, "hour") else int(str(sched).split(":")[0])
            except Exception:
                hour = None
        if hour is None:
            continue
        w = weather.get((session_date, hour))
        if not w:
            continue
        sched_str = None
        if sched is not None:
            sched_str = sched.strftime("%H:%M") if hasattr(sched, "strftime") else str(sched)[:5]
        per_flight.append({
            "date": ds, "callsign": r[1], "airline": r[2],
            "direction": _normalize_direction(r[3], fase),
            "scheduled": sched_str,
            "runway": pista or None,
            "side": _side_from_runway(pista),
            "temp_c": w["temp_c"], "wind_kmh": w["wind_kmh"],
            "wind_dir_deg": w["wind_dir_deg"],
            "wind_dir_cardinal": _wind_cardinal(w["wind_dir_deg"]),
            "rain_mm": w["rain_mm"], "conditions": w["conditions"],
        })
        acc = summary_acc.setdefault(ds, {"temp_sum": 0.0, "wind_sum": 0.0, "n": 0,
                                          "rain_ops": 0, "clear_ops": 0})
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
    return {"at_20": at_20, "per_flight": per_flight, "summary_by_date": summary_by_date}


def build_block_runway_diagnostics(date_from, date_to):
    rows = _query(
        """SELECT data_riferimento, pista, COUNT(*)
           FROM radar_detections
           WHERE data_riferimento BETWEEN %s AND %s AND sessione_notturna IS NOT NULL
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
        key = pista if pista in RUNWAYS_TO_MONITOR else ("N/D" if not pista else "altro")
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
        f"{len(destinations_pax.get('by_date', []))} giorni pax, "
        f"{len(airlines['totals'])} compagnie, "
        f"by_hour su {len(movements['by_hour'].get('by_date', []))} date"
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
        return True, f"JSON locale salvato ({local_path}), WordPress disabilitato"
    ok, msg, url = bgy_wordpress.publish_json(local_path)
    return (True, f"Pubblicato: {url}") if ok else (False, f"Errore: {msg}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not bgy_db.is_enabled():
        print("DB non abilitato"); sys.exit(1)
    if args.dry_run or not args.publish:
        payload = build_web_json(days=args.days)
        path = save_web_json(payload)
        if path:
            print(f"JSON salvato: {path}")
        sys.exit(0)
    ok, msg = export_and_publish(days=args.days)
    print(f"{'OK' if ok else 'ERRORE'}: {msg}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()