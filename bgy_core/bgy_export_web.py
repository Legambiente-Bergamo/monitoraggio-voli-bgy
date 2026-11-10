"""
bgy_core/bgy_export_web.py - Esportazione dati aggregati per il web (F17).
Versione 2.4.9
"""
__version__ = "2.5.0"
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
DELAYS_OUTPUT_FILE = os.path.join(WEB_OUTPUT_DIR, "bgy-delays.csv")

WEB_PREFIX = "# BGY Monitoring Suite - dati JSON sotto questa riga\n"
DELAYS_PREFIX = "# BGY Monitoring Suite - RITARDI H24 - dati JSON sotto questa riga\n"

MIN_DATE_DEFAULT = "2026-09-30"
TOP_N_PER_DATE_DEFAULT = 10
TAXI_TIME_MIN_DEFAULT = 15

DELAYS_DEFAULTS = {
    "enabled": True,
    "top_company": 20,
    "top_destination": 30,
    "soglia_puntuale_min": 15,
    "soglia_grave_min": 60,
    "taxi_time_min": 15
}

GATE_DEFAULTS = {
    "enabled": True,
    "min_days_with_nightly": 1,
    "min_nightly_rows": 5,
    "min_daily_rows": 30,
    "min_radar_recent": 50,
    "radar_lookback_days": 2,
    "min_h24_recent": 20,
    "h24_lookback_days": 2
}

RUNWAY_SIDE_MAP = {"RWY 28": "Bergamo", "RWY 10": "Seriate"}
RUNWAYS_TO_MONITOR = ["RWY 28", "RWY 10", "RWY 16", "RWY 34"]

CATEGORY_FILTERS = [
    ("passeggeri", "tipo_movimento = 'Passeggeri'"),
    ("cargo", "tipo_movimento LIKE 'Cargo%%'"),
    ("charter", "tipo_movimento LIKE 'Charter%%'"),
    ("non_classificato", "tipo_movimento = 'Non classificato'"),
]

CATS_KEYS = ["passeggeri", "cargo", "charter", "non_classificato"]
RADAR_ONLY_KPI_CATS = ("cargo", "charter", "non_classificato")
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
        "days_default": int(cfg.get("days_default", 90))
    }


def _get_delays_config():
    from bgy_core.bgy_config_manager import config_manager
    try:
        cfg = config_manager.get_data_config().get("web_export", {}) or {}
        d = cfg.get("delays", {}) or {}
    except Exception:
        d = {}
    return {
        "enabled": bool(d.get("enabled", DELAYS_DEFAULTS["enabled"])),
        "top_company": int(d.get("top_company", DELAYS_DEFAULTS["top_company"])),
        "top_destination": int(d.get("top_destination", DELAYS_DEFAULTS["top_destination"])),
        "soglia_puntuale_min": int(d.get("soglia_puntuale_min", DELAYS_DEFAULTS["soglia_puntuale_min"])),
        "soglia_grave_min": int(d.get("soglia_grave_min", DELAYS_DEFAULTS["soglia_grave_min"])),
        "taxi_time_min": int(d.get("taxi_time_min", TAXI_TIME_MIN_DEFAULT))
    }


def _get_gate_config():
    from bgy_core.bgy_config_manager import config_manager
    try:
        cfg = config_manager.get_data_config().get("web_export", {}) or {}
        g = cfg.get("gate", {}) or {}
    except Exception:
        g = {}
    return {
        "enabled": bool(g.get("enabled", GATE_DEFAULTS["enabled"])),
        "min_days_with_nightly": int(g.get("min_days_with_nightly", GATE_DEFAULTS["min_days_with_nightly"])),
        "min_nightly_rows": int(g.get("min_nightly_rows", GATE_DEFAULTS["min_nightly_rows"])),
        "min_daily_rows": int(g.get("min_daily_rows", GATE_DEFAULTS["min_daily_rows"])),
        "min_radar_recent": int(g.get("min_radar_recent", GATE_DEFAULTS["min_radar_recent"])),
        "radar_lookback_days": int(g.get("radar_lookback_days", GATE_DEFAULTS["radar_lookback_days"])),
        "min_h24_recent": int(g.get("min_h24_recent", GATE_DEFAULTS["min_h24_recent"])),
        "h24_lookback_days": int(g.get("h24_lookback_days", GATE_DEFAULTS["h24_lookback_days"]))
    }


def _gate_check_pre_publish():
    cfg = _get_gate_config()
    if not cfg["enabled"]:
        logger.info("⏭️  Gate pre-publish disabilitato in config")
        return True, "Gate disabilitato"

    errors = []

    rows = _query("SELECT COUNT(DISTINCT data_riferimento) FROM nightly_reports")
    n_days = int(rows[0][0]) if rows and rows[0] and rows[0][0] is not None else 0
    if n_days < cfg["min_days_with_nightly"]:
        errors.append(f"notti con dati in DB: {n_days} (soglia {cfg['min_days_with_nightly']})")

    rows = _query(
        "SELECT COUNT(*) FROM nightly_reports "
        "WHERE data_riferimento = (SELECT MAX(data_riferimento) FROM nightly_reports)"
    )
    n_nightly = int(rows[0][0]) if rows and rows[0] and rows[0][0] is not None else 0
    if n_nightly < cfg["min_nightly_rows"]:
        errors.append(f"voli nell'ultima notte: {n_nightly} (soglia {cfg['min_nightly_rows']})")

    rows = _query(
        "SELECT COUNT(*) FROM v_daily_report "
        "WHERE data_riferimento = (SELECT MAX(data_riferimento) FROM v_daily_report)"
    )
    n_daily = int(rows[0][0]) if rows and rows[0] and rows[0][0] is not None else 0
    if n_daily < cfg["min_daily_rows"]:
        errors.append(f"voli diurni nell'ultimo giorno: {n_daily} (soglia {cfg['min_daily_rows']})")

    lookback = cfg["radar_lookback_days"]
    rows = _query(
        "SELECT COUNT(*) FROM radar_detections "
        f"WHERE data_riferimento >= (CURRENT_DATE - INTERVAL '{lookback} days')"
    )
    n_radar = int(rows[0][0]) if rows and rows[0] and rows[0][0] is not None else 0
    if n_radar < cfg["min_radar_recent"]:
        errors.append(f"rilevamenti radar ultimi {lookback}g: {n_radar} (soglia {cfg['min_radar_recent']})")

    h24_lookback = cfg["h24_lookback_days"]
    rows = _query(
        "SELECT data_calendario, COUNT(*) FROM h24_reports "
        f"WHERE data_calendario >= (CURRENT_DATE - INTERVAL '{h24_lookback} days') "
        "GROUP BY data_calendario ORDER BY data_calendario DESC LIMIT 1"
    )
    if not rows:
        errors.append(f"h24_reports: nessuna riga negli ultimi {h24_lookback}g")
    else:
        max_d, n_h24 = rows[0]
        max_d_str = _date_str(max_d)
        expected_d = (datetime.now().date() - timedelta(days=1)).strftime("%Y-%m-%d")
        if max_d_str < expected_d:
            errors.append(f"h24_reports: manca il giorno {expected_d} (ultimo: {max_d_str})")
        if int(n_h24) < cfg["min_h24_recent"]:
            errors.append(f"h24_reports: ultimo giorno ({max_d_str}) ha solo {n_h24} righe (soglia {cfg['min_h24_recent']})")

    if errors:
        return False, " | ".join(errors)
    return True, "OK"


def _wind_cardinal(deg):
    if deg is None: return None
    try: d = float(deg) % 360
    except: return None
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return dirs[int((d + 22.5) // 45) % 8]


def _get_country(destination):
    try:
        from bgy_core.bgy_update_rules import get_country
        return get_country(destination) or "N/D"
    except Exception:
        return "N/D"


def _get_airline_safe(callsign):
    if not callsign:
        return 'N/D'
    try:
        from bgy_core import bgy_update_rules as ur
        cs = str(callsign).strip().upper().replace(' ', '')
        if len(cs) < 3:
            return 'N/D'

        airlines = getattr(ur, '_AIRLINES', {}) or {}
        cargo = getattr(ur, '_CARGO_AIRLINES', {}) or {}
        charter = getattr(ur, '_CHARTER_AIRLINES', {}) or {}

        def _lookup(d):
            if not isinstance(d, dict):
                return None
            for n in (3, 2):
                if len(cs) > n:
                    p = cs[:n]
                    if p in d:
                        return d[p]
            return None

        third_char = cs[2] if len(cs) >= 3 else ''
        if third_char.isalpha():
            v = _lookup(cargo) or _lookup(charter)
            if v:
                return v
        v = _lookup(airlines)
        if v:
            return v
        v = _lookup(cargo) or _lookup(charter)
        return v or 'N/D'
    except Exception:
        return 'N/D'


def _side_from_runway(runway):
    if not runway: return "N/D"
    return RUNWAY_SIDE_MAP.get(str(runway).strip(), "N/D")


def _side_key(side):
    if side == "Bergamo": return "bergamo"
    if side == "Seriate": return "seriate"
    return "nd"


def _normalize_direction(dir_sacbo, fase_volo):
    d = (dir_sacbo or "").strip().upper()
    if d in ("D", "A"): return d
    f = (fase_volo or "").strip()
    if f == "Decollo": return "D"
    if f in ("Atterraggio", "Avvicinamento"): return "A"
    return "?"


def _category_from_tipo(tipo_movimento):
    t = str(tipo_movimento or "").strip()
    if t == "Passeggeri": return "passeggeri"
    if t.startswith("Cargo"): return "cargo"
    if t.startswith("Charter"): return "charter"
    if t == "Non classificato": return "non_classificato"
    return None


def _session_date_for_ts(ts, fallback_date):
    if ts is None: return fallback_date
    try: dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S") if isinstance(ts, str) else ts
    except Exception: return fallback_date
    if dt.hour >= 12: return dt.strftime("%Y-%m-%d")
    return (dt - timedelta(days=1)).strftime("%Y-%m-%d")


def _date_str(v):
    if v is None: return None
    if hasattr(v, "strftime"): return v.strftime("%Y-%m-%d")
    return str(v)


def _time_to_minutes(h, m):
    return h * 60 + m


def _parse_slot(s):
    h, m = map(int, s.split(":"))
    return h, m, h * 60 + m


# =============================================================================
# WEB-40: QUALITY WARNINGS
# =============================================================================
DEFAULT_DAY_SLOTS = ["02:00", "06:00", "10:00", "14:00", "18:00", "22:00"]
REQUIRED_NIGHT_SLOTS = ["23:00", "05:00"]
OPTIONAL_NIGHT_SLOTS = ["00:01", "02:00"]
SLOT_TOLERANCE_MIN = 15
RADAR_GAP_THRESHOLD_MIN = 90


def _get_expected_slots():
    from bgy_core.bgy_config_manager import config_manager
    try:
        cfg = config_manager.get_data_config() or {}
    except Exception:
        cfg = {}
    day_raw = cfg.get("scan_schedules") or DEFAULT_DAY_SLOTS

    def _parse_many(items):
        out = []
        for s in items:
            try:
                h, m, minutes = _parse_slot(s)
                out.append(minutes)
            except Exception:
                logger.warning(f"Slot orario non valido: {s}")
        return out

    required = set(_parse_many(day_raw))
    required |= set(_parse_many(REQUIRED_NIGHT_SLOTS))
    optional = set(_parse_many(OPTIONAL_NIGHT_SLOTS)) - required
    return sorted(required), sorted(optional)


def build_data_quality_warnings(date_from, date_to):
    required_slots, optional_slots = _get_expected_slots()
    logger.info(
        f"Slot SACBO obbligatori: "
        f"{[f'{m//60:02d}:{m%60:02d}' for m in required_slots]}"
    )
    if optional_slots:
        logger.info(
            f"Slot SACBO opzionali: "
            f"{[f'{m//60:02d}:{m%60:02d}' for m in optional_slots]}"
        )

    # 1. Scansioni SACBO
    rows = _query(
        """SELECT scan_timestamp::date AS d,
                  EXTRACT(HOUR FROM scan_timestamp)::int AS h,
                  EXTRACT(MINUTE FROM scan_timestamp)::int AS m
           FROM scans
           WHERE scan_timestamp::date BETWEEN %s AND %s""",
        (date_from, date_to))
    scans_by_day = {}
    for r in rows:
        ds = _date_str(r[0])
        scans_by_day.setdefault(ds, []).append(int(r[1]) * 60 + int(r[2]))

    # 2. Radar
    rows = _query(
        """SELECT timestamp::date AS d, timestamp
           FROM radar_detections
           WHERE timestamp::date BETWEEN %s AND %s
           ORDER BY timestamp""",
        (date_from, date_to))
    radar_by_day = {}
    for r in rows:
        ds = _date_str(r[0])
        radar_by_day.setdefault(ds, []).append(r[1])

    # 3. Report notturno
    rows = _query(
        """SELECT data_riferimento, COUNT(*)
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
           GROUP BY data_riferimento""",
        (date_from, date_to))
    nightly_by_day = {_date_str(r[0]): int(r[1]) for r in rows}

    # 4. Report H24
    rows = _query(
        """SELECT data_calendario, COUNT(*)
           FROM h24_reports
           WHERE data_calendario BETWEEN %s AND %s
           GROUP BY data_calendario""",
        (date_from, date_to))
    h24_by_day = {_date_str(r[0]): int(r[1]) for r in rows}

    # 5. Avionio
    rows = _query(
        """SELECT COALESCE(scan_timestamp, imported_at)::date AS d, COUNT(*)
           FROM flights_avionio
           WHERE COALESCE(scan_timestamp, imported_at)::date BETWEEN %s AND %s
           GROUP BY d""",
        (date_from, date_to))
    avionio_by_day = {_date_str(r[0]): int(r[1]) for r in rows}
    avionio_min_date = min(avionio_by_day.keys()) if avionio_by_day else None
    if avionio_min_date:
        logger.info(f"Avionio: prima data con dati = {avionio_min_date}")
    else:
        logger.info("Avionio: nessun dato nel periodo (check saltato)")

    warnings = []
    current = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date()
    first_day = current
    last_day = end

    while current <= end:
        ds = current.strftime("%Y-%m-%d")
        issues = []

        # 5a. SACBO
        day_scans = scans_by_day.get(ds, [])
        if not day_scans:
            issues.append({
                "type": "sacbo_missing",
                "msg": "Non è stato possibile leggere il tabellone ufficiale dei voli in questa giornata: i dati potrebbero essere incompleti."
            })
        else:
            first_scan_min = min(day_scans)
            if first_scan_min > SLOT_TOLERANCE_MIN:
                first_h, first_m = first_scan_min // 60, first_scan_min % 60
                logger.info(
                    f"[{ds}] prima scansione SACBO alle {first_h:02d}:{first_m:02d} — "
                    f"slot precedenti ignorati"
                )
            for slot_min in required_slots:
                if slot_min < first_scan_min - SLOT_TOLERANCE_MIN:
                    continue
                if not any(abs(sm - slot_min) <= SLOT_TOLERANCE_MIN for sm in day_scans):
                    h, m = slot_min // 60, slot_min % 60
                    issues.append({
                        "type": "sacbo_missing_slot",
                        "slot": f"{h:02d}:{m:02d}",
                        "msg": f"Non è stato possibile leggere il tabellone ufficiale alle {h:02d}:{m:02d}: i dati di quel momento potrebbero mancare."
                    })

        # 5b. Radar
        day_radar = radar_by_day.get(ds, [])
        if not day_radar:
            issues.append({"type": "radar_missing", "msg": "Nessun rilevamento radar"})
        else:
            timestamps = []
            for ts in day_radar:
                if isinstance(ts, str):
                    ts = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                timestamps.append(ts)
            day_start = datetime.strptime(ds + " 00:00:00", "%Y-%m-%d %H:%M:%S")
            day_end = datetime.strptime(ds + " 23:59:59", "%Y-%m-%d %H:%M:%S")
            max_gap = 0
            gap_start = gap_end = None

            if current != first_day:
                g0 = (timestamps[0] - day_start).total_seconds() / 60
                if g0 > max_gap:
                    max_gap = g0
                    gap_start, gap_end = day_start, timestamps[0]

            for i in range(1, len(timestamps)):
                g = (timestamps[i] - timestamps[i - 1]).total_seconds() / 60
                if g > max_gap:
                    max_gap = g
                    gap_start, gap_end = timestamps[i - 1], timestamps[i]

            if current != last_day:
                g_end = (day_end - timestamps[-1]).total_seconds() / 60
                if g_end > max_gap:
                    max_gap = g_end
                    gap_start, gap_end = timestamps[-1], day_end

            if max_gap > RADAR_GAP_THRESHOLD_MIN:
                issues.append({
                    "type": "radar_gap",
                    "gap_min": round(max_gap),
                    "msg": (
                        f"Non abbiamo rilevamenti radar tra le {gap_start.strftime('%H:%M')} "
                        f"e le {gap_end.strftime('%H:%M')} ({round(max_gap)} minuti): "
                        f"non è stato possibile verificare i movimenti in quella fascia."
                    ),
                })

        # 5c. Report notturno
        if ds not in nightly_by_day or nightly_by_day[ds] == 0:
            issues.append({
                "type": "nightly_missing",
                "msg": "Non è stato elaborato il riepilogo della notte: i dati di quella notte potrebbero essere incompleti."
            })

        # 5d. Report H24
        if ds not in h24_by_day or h24_by_day[ds] == 0:
            issues.append({
                "type": "h24_missing",
                "msg": "Non è stato elaborato il riepilogo giornaliero: i dati di quel giorno potrebbero essere incompleti."
            })

        # 5e. Avionio
        if avionio_min_date and ds >= avionio_min_date:
            if ds not in avionio_by_day or avionio_by_day[ds] == 0:
                issues.append({
                    "type": "avionio_missing",
                    "msg": "Non sono stati raccolti i dati di integrazione (fonte Avionio): potrebbero mancare voli non presenti nel tabellone ufficiale."
                })

        if issues:
            warnings.append({
                "date": ds,
                "severity": "high",
                "issues": issues,
                "message": "; ".join(i["msg"] for i in issues),
            })

        current += timedelta(days=1)

    logger.info(f"Data quality warnings: {len(warnings)} giorni con problemi")
    return warnings


# =============================================================================
# BLOCCO HOME SUMMARY
# =============================================================================
def build_home_summary(date_from, date_to):
    def _query_breakdown(table, date_col):
        sql = f"""
            SELECT
                SUM(CASE WHEN tipo_movimento = 'Passeggeri'      THEN 1 ELSE 0 END) AS pax,
                SUM(CASE WHEN tipo_movimento LIKE 'Cargo%%'      THEN 1 ELSE 0 END) AS cargo,
                SUM(CASE WHEN tipo_movimento LIKE 'Charter%%'    THEN 1 ELSE 0 END) AS charter,
                SUM(CASE WHEN tipo_movimento = 'Non classificato' THEN 1 ELSE 0 END) AS altro,
                SUM(CASE WHEN tipo_movimento = 'Passeggeri'      AND direzione_sacbo = 'D' THEN 1 ELSE 0 END) AS pax_D,
                SUM(CASE WHEN tipo_movimento = 'Passeggeri'      AND direzione_sacbo = 'A' THEN 1 ELSE 0 END) AS pax_A,
                SUM(CASE WHEN tipo_movimento LIKE 'Cargo%%'      AND direzione_sacbo = 'D' THEN 1 ELSE 0 END) AS cargo_D,
                SUM(CASE WHEN tipo_movimento LIKE 'Cargo%%'      AND direzione_sacbo = 'A' THEN 1 ELSE 0 END) AS cargo_A,
                SUM(CASE WHEN tipo_movimento LIKE 'Charter%%'    AND direzione_sacbo = 'D' THEN 1 ELSE 0 END) AS charter_D,
                SUM(CASE WHEN tipo_movimento LIKE 'Charter%%'    AND direzione_sacbo = 'A' THEN 1 ELSE 0 END) AS charter_A,
                SUM(CASE WHEN tipo_movimento = 'Non classificato' AND direzione_sacbo = 'D' THEN 1 ELSE 0 END) AS altro_D,
                SUM(CASE WHEN tipo_movimento = 'Non classificato' AND direzione_sacbo = 'A' THEN 1 ELSE 0 END) AS altro_A,
                SUM(CASE WHEN direzione_sacbo = 'D' THEN 1 ELSE 0 END) AS tot_D,
                SUM(CASE WHEN direzione_sacbo = 'A' THEN 1 ELSE 0 END) AS tot_A
            FROM {table}
            WHERE {date_col} BETWEEN %s AND %s
              AND is_scheduled = TRUE
        """
        rows = _query(sql, (date_from, date_to))
        result = {
            "pax": 0, "cargo": 0, "charter": 0, "altro": 0,
            "pax_D": 0, "pax_A": 0,
            "cargo_D": 0, "cargo_A": 0,
            "charter_D": 0, "charter_A": 0,
            "altro_D": 0, "altro_A": 0,
            "D": 0, "A": 0, "total": 0
        }
        if rows and rows[0]:
            cols = ["pax", "cargo", "charter", "altro",
                    "pax_D", "pax_A", "cargo_D", "cargo_A",
                    "charter_D", "charter_A", "altro_D", "altro_A",
                    "D", "A"]
            for i, key in enumerate(cols):
                result[key] = int(rows[0][i] or 0)
            result["total"] = (result["pax"] + result["cargo"]
                               + result["charter"] + result["altro"])
        return result

    h24 = _query_breakdown("h24_reports", "data_calendario")
    nightly = _query_breakdown("nightly_reports", "data_riferimento")
    return {"h24": h24, "nightly": nightly}


# =============================================================================
# BLOCCHI NOTTURNI
# =============================================================================

def _empty_by_date_item(date_str):
    item = {
        "date": date_str,
        "totale": 0, "a_tabellone": 0, "solo_radar": 0,
        "schedulato": 0, "schedulato_D": 0, "schedulato_A": 0,
        "sconfinamenti": 0, "sconfinamenti_D": 0, "sconfinamenti_A": 0,
        "sconfinamenti_gravi": 0, "sconfinamenti_gravi_D": 0, "sconfinamenti_gravi_A": 0,
        "anomalie": 0, "D": 0, "A": 0, "D_radar": 0, "A_radar": 0,
        "side_bergamo": 0, "side_bergamo_D": 0, "side_bergamo_A": 0,
        "side_seriate": 0, "side_seriate_D": 0, "side_seriate_A": 0,
        "side_nd": 0, "side_nd_D": 0, "side_nd_A": 0,
        "totale_movimenti_rilevati": 0, "D_totali_rilevati": 0, "A_totali_rilevati": 0,
        "radar_only_total": 0, "radar_only_D": 0, "radar_only_A": 0
    }
    for cat in CATS_KEYS:
        item["D_" + cat] = 0
        item["A_" + cat] = 0
    for cat in RADAR_ONLY_KPI_CATS:
        item["D_" + cat + "_ro"] = 0
        item["A_" + cat + "_ro"] = 0
    return item


def _fill_tab_derived(container):
    for cat in RADAR_ONLY_KPI_CATS:
        d_ro = container.get("D_" + cat + "_ro", 0)
        a_ro = container.get("A_" + cat + "_ro", 0)
        container["D_" + cat + "_tab"] = max(0, container.get("D_" + cat, 0) - d_ro)
        container["A_" + cat + "_tab"] = max(0, container.get("A_" + cat, 0) - a_ro)
    container["D_passeggeri_tab"] = container.get("D_passeggeri", 0)
    container["A_passeggeri_tab"] = container.get("A_passeggeri", 0)


def _fill_radar_only_derived(container):
    ro_D = sum(container.get("D_" + c + "_ro", 0) for c in RADAR_ONLY_KPI_CATS)
    ro_A = sum(container.get("A_" + c + "_ro", 0) for c in RADAR_ONLY_KPI_CATS)
    ro_tot = ro_D + ro_A
    container["radar_only_D"] = ro_D
    container["radar_only_A"] = ro_A
    container["radar_only_total"] = ro_tot
    container["D_totali_rilevati"] = container.get("D", 0) + ro_D
    container["A_totali_rilevati"] = container.get("A", 0) + ro_A
    container["totale_movimenti_rilevati"] = container.get("a_tabellone", 0) + ro_tot


def build_disclaimer(min_date):
    from bgy_core.bgy_config_manager import config_manager
    disclaimers = config_manager.get_data_config().get("disclaimers", {})
    global_d = disclaimers.get("global", {})
    title = global_d.get("title", "DATI IN FASE DI VERIFICA")
    body = global_d.get("body", "").replace("{min_date}", min_date)
    return {"test_phase": True, "min_date": min_date, "title": title, "message": body}


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
        "rumore_max_db": rumore_max
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
        "totale_movimenti_rilevati": 0, "D_totali_rilevati": 0, "A_totali_rilevati": 0,
        "radar_only_total": 0, "radar_only_D": 0, "radar_only_A": 0
    }
    for cat in CATS_KEYS:
        totals["D_" + cat] = 0
        totals["A_" + cat] = 0
    for cat in RADAR_ONLY_KPI_CATS:
        totals["D_" + cat + "_ro"] = 0
        totals["A_" + cat + "_ro"] = 0

    by_side_acc = {
        "bergamo": {"totale": 0, "D": 0, "A": 0},
        "seriate": {"totale": 0, "D": 0, "A": 0},
        "nd": {"totale": 0, "D": 0, "A": 0}
    }

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
            item["a_tabellone"] += n; totals["a_tabellone"] += n
            if d == "D": item["D"] += n; totals["D"] += n
            elif d == "A": item["A"] += n; totals["A"] += n
            item["side_" + sk] += n
            if d == "D": item["side_" + sk + "_D"] += n
            elif d == "A": item["side_" + sk + "_A"] += n
            by_side_acc[sk]["totale"] += n
            if d == "D": by_side_acc[sk]["D"] += n
            elif d == "A": by_side_acc[sk]["A"] += n
            if notte_cat == "regolare":
                item["schedulato"] += n; totals["schedulato"] += n
                if d == "D": item["schedulato_D"] += n; totals["schedulato_D"] += n
                elif d == "A": item["schedulato_A"] += n; totals["schedulato_A"] += n
            elif notte_cat == "sconfinamento":
                item["sconfinamenti"] += n; totals["sconfinamenti"] += n
                if d == "D": item["sconfinamenti_D"] += n; totals["sconfinamenti_D"] += n
                elif d == "A": item["sconfinamenti_A"] += n; totals["sconfinamenti_A"] += n
            elif notte_cat == "sconfinamento_grave":
                item["sconfinamenti_gravi"] += n; totals["sconfinamenti_gravi"] += n
                if d == "D": item["sconfinamenti_gravi_D"] += n; totals["sconfinamenti_gravi_D"] += n
                elif d == "A": item["sconfinamenti_gravi_A"] += n; totals["sconfinamenti_gravi_A"] += n
            elif notte_cat == "anomalia":
                item["anomalie"] += n; totals["anomalie"] += n
            if cat and d in ("D", "A"):
                item[d + "_" + cat] += n; totals[d + "_" + cat] += n
        else:
            item["solo_radar"] += n; totals["solo_radar"] += n
            if d == "D": item["D_radar"] += n; totals["D_radar"] += n
            elif d == "A": item["A_radar"] += n; totals["A_radar"] += n
            if cat in RADAR_ONLY_KPI_CATS and d in ("D", "A"):
                item[d + "_" + cat] += n; totals[d + "_" + cat] += n
                item[d + "_" + cat + "_ro"] += n; totals[d + "_" + cat + "_ro"] += n

    _fill_radar_only_derived(totals)
    _fill_tab_derived(totals)
    for ds in by_date_acc:
        _fill_radar_only_derived(by_date_acc[ds])
        _fill_tab_derived(by_date_acc[ds])

    by_date = [by_date_acc[ds] for ds in sorted(by_date_acc.keys())]
    return {"by_date": by_date, "totals": totals, "by_side": by_side_acc, "by_hour": _build_by_hour(date_from, date_to)}


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
            "date": ds, "callsign": r[1] or "N/D", "airline": r[2] or "N/D",
            "direction": _normalize_direction(r[3], r[4]), "scheduled": sched_str
        })
    return {"totals": len(items), "items": items}


def _empty_hour_slot(hour):
    return {
        "hour": hour,
        "D": {"passeggeri": 0, "cargo": 0, "charter": 0, "non_classificato": 0, "total": 0},
        "A": {"passeggeri": 0, "cargo": 0, "charter": 0, "non_classificato": 0, "total": 0}
    }


def _build_by_hour(date_from, date_to):
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
          AND is_scheduled = TRUE
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
        if h is None or h not in NIGHT_HOURS: continue
        d = r[2] or '?'
        if d not in ('D', 'A'): continue
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

    return {"by_date": by_date, "totals": [totals[h] for h in NIGHT_HOURS]}


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
        if direction is None: continue
        day = by_date_acc.setdefault(ds, {
            "D": {"by_city": [], "by_country_acc": {}},
            "A": {"by_city": [], "by_country_acc": {}}
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
                "by_country": by_country[:top_countries]
            }
        by_date.append(item)
    return {
        "by_date": by_date,
        "note": ("Il grafico mostra le destinazioni dei soli voli passeggeri "
                 "dichiarati dal tabellone SACBO nel periodo selezionato. "
                 "Partenze e arrivi sono separati. Cargo e charter sono esclusi.")
    }


def build_block_geo_breakdown(date_from, date_to):
    dir_case = """
        CASE
          WHEN direzione_sacbo IN ('D', 'A') THEN direzione_sacbo
          WHEN fase_volo = 'Decollo' THEN 'D'
          WHEN fase_volo IN ('Atterraggio', 'Avvicinamento') THEN 'A'
          ELSE '?'
        END
    """
    rows = _query(
        f"""SELECT data_riferimento, ({dir_case}) AS dir,
                   tipo_movimento, stato_destinazione, destinazione_finale,
                   COUNT(*) AS n
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND is_scheduled = TRUE
             AND (tipo_movimento = 'Passeggeri'
                  OR tipo_movimento LIKE 'Cargo%%'
                  OR tipo_movimento LIKE 'Charter%%'
                  OR tipo_movimento = 'Non classificato')
           GROUP BY data_riferimento, dir, tipo_movimento,
                    stato_destinazione, destinazione_finale""",
        (date_from, date_to))

    def _empty():
        return {"passeggeri": 0, "cargo": 0, "charter": 0, "non_classificato": 0, "total": 0}

    def _add(container, cat, n):
        container[cat] = container.get(cat, 0) + n
        container["total"] = container.get("total", 0) + n

    by_date_acc = {}
    for r in rows:
        ds = _date_str(r[0])
        d = r[1] if r[1] in ("D", "A") else None
        if d is None: continue
        cat = _category_from_tipo(r[2])
        if cat is None: continue
        country = r[3] or "DA CLASSIFICARE"
        city = r[4] or "N/D"
        n = int(r[5] or 0)

        day = by_date_acc.setdefault(ds, {
            "D": {"by_country_acc": {}, "by_city_acc": {}},
            "A": {"by_country_acc": {}, "by_city_acc": {}}
        })
        d_side = day[d]

        ck = country
        if ck not in d_side["by_country_acc"]:
            d_side["by_country_acc"][ck] = _empty()
        _add(d_side["by_country_acc"][ck], cat, n)

        city_key = city + "|" + country
        if city_key not in d_side["by_city_acc"]:
            d_side["by_city_acc"][city_key] = {
                "city": city, "country": country,
                "passeggeri": 0, "cargo": 0, "charter": 0,
                "non_classificato": 0, "total": 0
            }
        _add(d_side["by_city_acc"][city_key], cat, n)

    by_date = []
    for ds in sorted(by_date_acc.keys()):
        day = by_date_acc[ds]
        item = {"date": ds}
        for dir_key in ("D", "A"):
            d_side = day[dir_key]
            by_country = []
            for country, acc in d_side["by_country_acc"].items():
                entry = {"country": country}
                entry.update(acc)
                by_country.append(entry)
            by_country.sort(key=lambda x: (-x["total"], x["country"]))
            by_city = list(d_side["by_city_acc"].values())
            by_city.sort(key=lambda x: (-x["total"], x["city"]))
            item[dir_key] = {"by_country": by_country, "by_city": by_city}
        by_date.append(item)

    return {"by_date": by_date}


def build_block_night_airlines(date_from, date_to, top_n):
    dir_case = """
        CASE
          WHEN direzione_sacbo IN ('D', 'A') THEN direzione_sacbo
          WHEN fase_volo = 'Decollo' THEN 'D'
          WHEN fase_volo IN ('Atterraggio', 'Avvicinamento') THEN 'A'
          ELSE '?'
        END
    """
    cat_case = """
        CASE
          WHEN tipo_movimento LIKE 'Cargo%%' THEN 'cargo'
          WHEN tipo_movimento LIKE 'Charter%%' THEN 'charter'
          WHEN tipo_movimento = 'Non classificato' THEN 'non_classificato'
          ELSE 'passeggeri'
        END
    """
    rows = _query(
        f"""SELECT data_riferimento, compagnia_aerea, ({cat_case}) AS cat,
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
                  OR tipo_movimento LIKE 'Charter%%'
                  OR tipo_movimento = 'Non classificato')
           GROUP BY data_riferimento, compagnia_aerea, cat
           ORDER BY data_riferimento, n DESC""",
        (date_from, date_to))

    by_date_acc = {}
    for r in rows:
        ds = _date_str(r[0])
        airline = r[1]
        cat = r[2]
        n_d = int(r[3] or 0)
        n_a = int(r[4] or 0)
        n = int(r[5] or 0)

        key = (ds, airline)
        if key not in by_date_acc:
            by_date_acc[key] = {
                "airline": airline, "cat": cat,
                "n": 0, "D": 0, "A": 0, "_cat_counts": {}
            }
        entry = by_date_acc[key]
        entry["n"] += n
        entry["D"] += n_d
        entry["A"] += n_a
        entry["_cat_counts"][cat] = entry["_cat_counts"].get(cat, 0) + n

    for entry in by_date_acc.values():
        cc = entry.pop("_cat_counts", {})
        if cc:
            entry["cat"] = max(cc.items(), key=lambda kv: kv[1])[0]

    by_date_map = {}
    for (ds, airline), entry in by_date_acc.items():
        by_date_map.setdefault(ds, []).append(entry)

    by_date = []
    for ds in sorted(by_date_map.keys()):
        items = sorted(by_date_map[ds], key=lambda x: (-x["n"], x["airline"]))
        by_date.append({"date": ds, "top": items[:top_n]})

    rows = _query(
        f"""SELECT compagnia_aerea, ({cat_case}) AS cat,
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
                  OR tipo_movimento LIKE 'Charter%%'
                  OR tipo_movimento = 'Non classificato')
           GROUP BY compagnia_aerea, cat
           ORDER BY n DESC""",
        (date_from, date_to))

    totals_acc = {}
    for r in rows:
        airline = r[0]
        cat = r[1]
        n_d = int(r[2] or 0)
        n_a = int(r[3] or 0)
        n = int(r[4] or 0)
        if airline not in totals_acc:
            totals_acc[airline] = {
                "airline": airline, "cat": cat,
                "n": 0, "D": 0, "A": 0, "_cat_counts": {}
            }
        entry = totals_acc[airline]
        entry["n"] += n
        entry["D"] += n_d
        entry["A"] += n_a
        entry["_cat_counts"][cat] = entry["_cat_counts"].get(cat, 0) + n

    totals = []
    for entry in totals_acc.values():
        cc = entry.pop("_cat_counts", {})
        if cc:
            entry["cat"] = max(cc.items(), key=lambda kv: kv[1])[0]
        totals.append(entry)
    totals.sort(key=lambda x: -x["n"])

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
            "conditions": r[6] or ""
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
            "side_used": _side_from_runway(runway)
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
            "rain_mm": w["rain_mm"], "conditions": w["conditions"]
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
            "ops_in_clear": acc["clear_ops"]
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


def build_block_pista_fonte(date_from, date_to):
    rows = _query(
        """SELECT direzione_sacbo, COALESCE(pista_fonte, 'N/D') as fonte, COUNT(*)
           FROM nightly_reports
           WHERE data_riferimento BETWEEN %s AND %s
             AND is_scheduled = TRUE
           GROUP BY direzione_sacbo, fonte""",
        (date_from, date_to))

    result = {
        "D": {"radar_diretto": 0, "propagato": 0, "geometrico": 0, "N/D": 0},
        "A": {"radar_diretto": 0, "propagato": 0, "geometrico": 0, "N/D": 0}
    }

    for r in rows:
        d = (r[0] or "").strip().upper()
        if d not in ("D", "A"):
            continue
        fonte = (r[1] or "N/D").strip()
        if fonte not in result[d]:
            fonte = "N/D"
        result[d][fonte] += int(r[2] or 0)

    return result


# =============================================================================
# BLOCCO RITARDI H24
# =============================================================================

def _delta_sql_expr():
    return """
        CASE
            WHEN v.timestamp IS NULL OR v.orario_schedulato IS NULL THEN NULL
            WHEN v.timestamp::time = v.orario_schedulato THEN 0
            WHEN v.timestamp::time > v.orario_schedulato THEN
                CASE
                    WHEN EXTRACT(EPOCH FROM (v.timestamp::time - v.orario_schedulato)) <= 720 * 60 THEN
                        EXTRACT(EPOCH FROM (v.timestamp::time - v.orario_schedulato)) / 60
                    ELSE
                        (EXTRACT(EPOCH FROM (v.timestamp::time - v.orario_schedulato)) / 60) - 1440
                END
            ELSE
                CASE
                    WHEN EXTRACT(EPOCH FROM (v.orario_schedulato - v.timestamp::time)) <= 720 * 60 THEN
                        -(EXTRACT(EPOCH FROM (v.orario_schedulato - v.timestamp::time)) / 60)
                    ELSE
                        1440 - (EXTRACT(EPOCH FROM (v.orario_schedulato - v.timestamp::time)) / 60)
                END
        END
    """


def _empty_delay_agg():
    return {
        "n_total": 0, "n_puntuali": 0, "n_ritardo": 0, "n_grave": 0,
        "n_anticipo": 0,
        "sum_delta": 0.0,
        "sum_delta_ritardi": 0.0,
        "deltas_ritardi": [],
        "ritardi_min": None,
        "ritardi_max": None
    }


def _finalize_delay_agg(agg):
    n = agg["n_total"]
    n_rit = agg["n_ritardo"]

    agg["ritardo_medio"] = round(agg["sum_delta"] / n, 1) if n > 0 else 0.0

    if n_rit > 0:
        agg["ritardo_medio_ritardati"] = round(
            agg["sum_delta_ritardi"] / n_rit, 1)
    else:
        agg["ritardo_medio_ritardati"] = 0.0

    deltas = agg.pop("deltas_ritardi", [])

    if deltas:
        deltas_sorted = sorted(deltas)
        n_d = len(deltas_sorted)
        if n_d % 2 == 1:
            agg["mediana_ritardi"] = float(deltas_sorted[n_d // 2])
        else:
            agg["mediana_ritardi"] = round(
                (deltas_sorted[n_d // 2 - 1] + deltas_sorted[n_d // 2]) / 2, 1)
    else:
        agg["mediana_ritardi"] = 0.0

    fasce = {
        "15-30": 0,
        "30-45": 0,
        "45-60": 0,
        "60-120": 0,
        ">120": 0
    }
    for d in deltas:
        if d <= 30: fasce["15-30"] += 1
        elif d <= 45: fasce["30-45"] += 1
        elif d <= 60: fasce["45-60"] += 1
        elif d <= 120: fasce["60-120"] += 1
        else: fasce[">120"] += 1
    agg["ritardi_fasce"] = fasce

    return agg


def _add_delta_to_agg(agg, delta, soglia_punt, soglia_grave):
    agg["sum_delta"] += delta
    if abs(delta) <= soglia_punt:
        agg["n_puntuali"] += 1
    if delta >= soglia_punt:
        agg["n_ritardo"] += 1
        agg["sum_delta_ritardi"] += delta
        agg["deltas_ritardi"].append(delta)
        if agg["ritardi_min"] is None or delta < agg["ritardi_min"]:
            agg["ritardi_min"] = delta
        if agg["ritardi_max"] is None or delta > agg["ritardi_max"]:
            agg["ritardi_max"] = delta
    if delta > soglia_grave:
        agg["n_grave"] += 1
    if delta <= -soglia_punt:
        agg["n_anticipo"] += 1


def build_block_delays_h24(date_from, date_to):
    cfg = _get_delays_config()
    if not cfg["enabled"]:
        logger.info("Blocco delays disabilitato in config_data.json")
        return None

    soglia_punt = cfg["soglia_puntuale_min"]
    soglia_grave = cfg["soglia_grave_min"]
    top_company = cfg["top_company"]
    top_dest = cfg["top_destination"]

    try:
        from bgy_core.bgy_update_rules import load_rules
        load_rules()
    except Exception as e:
        logger.warning(f"load_rules() fallito: {e}")

    delta_expr = _delta_sql_expr()

    sql_totali = """
        SELECT data_calendario, direzione_sacbo, COUNT(*) 
        FROM h24_reports
        WHERE data_calendario BETWEEN %s AND %s
          AND is_scheduled = TRUE
        GROUP BY data_calendario, direzione_sacbo
    """
    rows_totali = _query(sql_totali, (date_from, date_to))

    totali_generali = {}
    for r in rows_totali:
        ds = _date_str(r[0])
        d = (r[1] or "").strip().upper()
        n = int(r[2] or 0)
        if ds not in totali_generali:
            totali_generali[ds] = {"D": 0, "A": 0}
        if d in ("D", "A"):
            totali_generali[ds][d] += n

    sql_ritardi = f"""
        SELECT
            v.data,
            v.callsign,
            v.tipo_movimento,
            v.destinazione_finale,
            v.orario_schedulato,
            v.ora_effettiva,
            v.compagnia_aerea,
            v.direzione_sacbo,
            {delta_expr} AS delta_min
        FROM v_h24_report v
        WHERE v.data BETWEEN %s AND %s
          AND v.is_scheduled = TRUE
          AND v.orario_schedulato IS NOT NULL
          AND v.timestamp IS NOT NULL
          AND v.fase_volo NOT IN ('Non rilevato', 'N/D', '')
          AND (v.tipo_movimento = 'Passeggeri'
               OR v.tipo_movimento LIKE 'Cargo%%'
               OR v.tipo_movimento LIKE 'Charter%%'
               OR v.tipo_movimento = 'Non classificato')
    """
    rows_ritardi = _query(sql_ritardi, (date_from, date_to))

    logger.info(f"   Ritardi (H24): {len(rows_ritardi)} voli validi per i ritardi.")

    by_date_acc = {}
    raw_delays = []

    for ds, tot in totali_generali.items():
        by_date_acc[ds] = {
            "D": {"agg": _empty_delay_agg(), "hours": {}, "companies": {}, "dests": {}, "by_category": {}},
            "A": {"agg": _empty_delay_agg(), "hours": {}, "companies": {}, "dests": {}, "by_category": {}}
        }
        by_date_acc[ds]["D"]["agg"]["n_total"] = tot["D"]
        by_date_acc[ds]["A"]["agg"]["n_total"] = tot["A"]

    for r in rows_ritardi:
        ds = _date_str(r[0])
        callsign = r[1]
        tipo = (r[2] or "").strip()
        dest = r[3] or ""
        sched = r[4]
        hh = r[5]
        comp_db = r[6]
        d = (r[7] or "").strip().upper()
        delta = r[8]

        if delta is None: continue
        try: delta = int(round(float(delta)))
        except (ValueError, TypeError): continue
        if d not in ('D', 'A'): continue

        comp = comp_db if comp_db and comp_db != 'N/D' else _get_airline_safe(callsign)

        day = by_date_acc.setdefault(ds, {
            "D": {"agg": _empty_delay_agg(), "hours": {}, "companies": {}, "dests": {}, "by_category": {}},
            "A": {"agg": _empty_delay_agg(), "hours": {}, "companies": {}, "dests": {}, "by_category": {}}
        })

        dir_block = day[d]

        _add_delta_to_agg(dir_block["agg"], delta, soglia_punt, soglia_grave)

        cat = _category_from_tipo(tipo)
        if cat:
            if cat not in dir_block["by_category"]:
                dir_block["by_category"][cat] = _empty_delay_agg()
            cat_agg = dir_block["by_category"][cat]
            cat_agg["n_total"] += 1
            _add_delta_to_agg(cat_agg, delta, soglia_punt, soglia_grave)

        if hh is not None:
            if hh not in dir_block["hours"]:
                dir_block["hours"][hh] = _empty_delay_agg()
            hr_agg = dir_block["hours"][hh]
            hr_agg["n_total"] += 1
            _add_delta_to_agg(hr_agg, delta, soglia_punt, soglia_grave)

        if comp and comp != 'N/D':
            if comp not in dir_block["companies"]:
                dir_block["companies"][comp] = _empty_delay_agg()
            c_agg = dir_block["companies"][comp]
            c_agg["n_total"] += 1
            _add_delta_to_agg(c_agg, delta, soglia_punt, soglia_grave)

        if dest and dest.strip():
            dk = dest.strip()
            if dk not in dir_block["dests"]:
                dir_block["dests"][dk] = _empty_delay_agg()
            d_agg = dir_block["dests"][dk]
            d_agg["n_total"] += 1
            _add_delta_to_agg(d_agg, delta, soglia_punt, soglia_grave)

        if delta >= soglia_punt or delta <= -15:
            sched_str = sched.strftime("%H:%M") if hasattr(sched, "strftime") else str(sched)[:5]
            raw_delays.append({
                "date": ds, "callsign": callsign, "company": comp, "dest": dest,
                "sched": sched_str, "delta": delta, "dir": d
            })

    by_date = []
    for ds in sorted(by_date_acc.keys()):
        day_in = by_date_acc[ds]
        day_out = {"date": ds}

        for d in ('D', 'A'):
            din = day_in[d]
            dout = _finalize_delay_agg(din["agg"])

            hours_list = []
            for h in sorted(din["hours"].keys()):
                hout = _finalize_delay_agg(din["hours"][h])
                hout["h"] = h
                hours_list.append(hout)
            dout["by_hour"] = hours_list

            companies_list = []
            for name, agg in din["companies"].items():
                cout = _finalize_delay_agg(agg)
                cout["compagnia"] = name
                companies_list.append(cout)
            companies_list.sort(key=lambda x: -x["n_total"])
            dout["by_company"] = companies_list[:top_company]

            dests_list = []
            for name, agg in din["dests"].items():
                dout_dest = _finalize_delay_agg(agg)
                dout_dest["dest"] = name
                dests_list.append(dout_dest)
            dests_list.sort(key=lambda x: -x["n_total"])
            dout["by_destination"] = dests_list[:top_dest]

            cat_aggs = {}
            for cat_name, cat_agg in din["by_category"].items():
                cat_aggs[cat_name] = _finalize_delay_agg(cat_agg)
            dout["by_category"] = cat_aggs

            day_out[d] = dout

        by_date.append(day_out)

    logger.info(f"   Ritardi (H24): {len(by_date)} giorni aggregati.")

    return {
        "soglie": {"puntuale_min": soglia_punt, "grave_min": soglia_grave},
        "by_date": by_date,
        "raw_delays": raw_delays
    }


def build_block_delays_hourly_weather(date_from, date_to):
    cfg = _get_delays_config()
    if not cfg["enabled"]:
        return None

    soglia_punt = cfg["soglia_puntuale_min"]
    delta_expr = _delta_sql_expr()

    sql = f"""
        SELECT
            v.data,
            v.ora_effettiva,
            v.direzione_sacbo,
            {delta_expr} AS delta_min
        FROM v_h24_report v
        WHERE v.data BETWEEN %s AND %s
          AND v.is_scheduled = TRUE
          AND v.orario_schedulato IS NOT NULL
          AND v.timestamp IS NOT NULL
          AND v.fase_volo NOT IN ('Non rilevato', 'N/D', '')
          AND (v.tipo_movimento = 'Passeggeri'
               OR v.tipo_movimento LIKE 'Cargo%%'
               OR v.tipo_movimento LIKE 'Charter%%'
               OR v.tipo_movimento = 'Non classificato')
    """
    rows = _query(sql, (date_from, date_to))

    weather_data = _load_weather(date_from, date_to)

    agg = {}

    for r in rows:
        ds = _date_str(r[0])
        hh = r[1]
        d = (r[2] or "").strip().upper()
        delta = r[3]

        if hh is None or d not in ('D', 'A') or delta is None:
            continue

        try:
            delta = int(round(float(delta)))
        except (ValueError, TypeError):
            continue

        key = (ds, hh)
        if key not in agg:
            agg[key] = {
                "D": {"n_total": 0, "n_ritardo": 0},
                "A": {"n_total": 0, "n_ritardo": 0}
            }

        agg[key][d]["n_total"] += 1
        if delta >= soglia_punt or delta <= -15:
            agg[key][d]["n_ritardo"] += 1

    result = []
    for (ds, hh) in sorted(agg.keys()):
        w = weather_data.get((ds, hh))

        entry = {
            "date": ds,
            "hour": hh,
            "D": agg[(ds, hh)]["D"],
            "A": agg[(ds, hh)]["A"],
            "weather": {
                "temp_c": w["temp_c"] if w else None,
                "rain_mm": w["rain_mm"] if w else None,
                "wind_kmh": w["wind_kmh"] if w else None,
                "wind_dir_deg": w["wind_dir_deg"] if w else None,
                "conditions": w["conditions"] if w else ""
            }
        }
        result.append(entry)

    return result


# =============================================================================
# BUILDERS PRINCIPALI (FLOTTA)
# =============================================================================

def build_block_fleet(date_from, date_to):
    """
    Costruisce i dati per la pagina La Flotta (WEB-37).
    Restituisce: { passeggeri: { voli: [...] }, cargo: { voli: [...] }, charter: { voli: [...] } }
    La categoria 'charter' include anche i voli privati e militari (altri movimenti).
    Ogni volo ha: compagnia, parent_company (se disponibile), modello, motore, max_passeggeri, data.
    La classificazione usa le colonne is_cargo, is_charter, is_private, is_military da airlines.
    """
    from bgy_core.bgy_update_rules import get_parent_company
    from bgy_core import bgy_db

    # Carica i motori e i posti massimi da aircraft_models
    motori = {}
    max_pax = {}
    try:
        ok, rows = bgy_db.execute_query("SELECT model, motore, max_passeggeri FROM aircraft_models WHERE motore IS NOT NULL OR max_passeggeri IS NOT NULL")
        if ok and rows:
            for r in rows:
                motori[r[0]] = r[1]
                max_pax[r[0]] = r[2]
    except Exception as e:
        logger.warning(f"Impossibile caricare i motori: {e}")

    # Carica la classificazione delle compagnie da airlines
    airlines_class = {}
    try:
        ok, rows = bgy_db.execute_query("SELECT code, is_cargo, is_charter, is_private, is_military FROM airlines")
        if ok and rows:
            for r in rows:
                airlines_class[r[0]] = {
                    "is_cargo": bool(r[1]),
                    "is_charter": bool(r[2]),
                    "is_private": bool(r[3]),
                    "is_military": bool(r[4]),
                }
    except Exception as e:
        logger.warning(f"Impossibile caricare la classificazione delle compagnie: {e}")

    sql = """
        SELECT data_calendario, tipo_movimento, compagnia_aerea, modello_aereo, callsign, COUNT(*) as n
        FROM h24_reports
        WHERE data_calendario BETWEEN %s AND %s
          AND is_scheduled = TRUE
          AND modello_aereo IS NOT NULL
          AND modello_aereo NOT IN ('N/D', '')
        GROUP BY data_calendario, tipo_movimento, compagnia_aerea, modello_aereo, callsign
    """
    rows = _query(sql, (date_from, date_to))

    result = {
        "passeggeri": {"voli": []},
        "cargo": {"voli": []},
        "charter": {"voli": []}
    }

    def _cat_from_tipo(tipo):
        t = str(tipo or "").strip().lower()
        if t.startswith("passeggeri"): return "passeggeri"
        if t.startswith("cargo"): return "cargo"
        if t.startswith("charter") or t.startswith("privato") or t.startswith("militare"):
            return "charter"
        return None

    def _cat_from_airline(comp, callsign):
        # Cerca il prefisso del callsign nella mappa airlines_class
        if callsign:
            cs = callsign.strip().upper().replace(" ", "")
            for prefix_len in (3, 2):
                if len(cs) > prefix_len:
                    prefix = cs[:prefix_len]
                    if prefix in airlines_class:
                        cls = airlines_class[prefix]
                        if cls["is_military"]:
                            return "charter"  # militari -> altri movimenti
                        if cls["is_private"]:
                            return "charter"  # privati -> altri movimenti
                        if cls["is_cargo"]:
                            return "cargo"
                        if cls["is_charter"]:
                            return "charter"
        # Fallback: usa il tipo_movimento
        return None

    for r in rows:
        data_cal = _date_str(r[0])
        tipo = r[1]
        comp = r[2] or "N/D"
        model = r[3]
        callsign = r[4] or ""
        n = int(r[5])
        # Prova prima con la classificazione da airlines, poi con tipo_movimento
        cat = _cat_from_airline(comp, callsign)
        if cat is None:
            cat = _cat_from_tipo(tipo)
        if cat is None or cat not in result:
            continue
        parent = get_parent_company(callsign) if callsign else None
        motore = motori.get(model, "N/D")
        max_pax_val = max_pax.get(model, 0)
        for _ in range(n):
            result[cat]["voli"].append({
                "compagnia": comp,
                "parent_company": parent,
                "modello": model,
                "motore": motore,
                "max_passeggeri": max_pax_val,
                "data": data_cal
            })

    logger.info(f"Fleet: passeggeri={len(result['passeggeri']['voli'])}, "
                f"cargo={len(result['cargo']['voli'])}, "
                f"charter+altri={len(result['charter']['voli'])}")
    return result


def _build_home_summary_h24(date_from, date_to):
    rows = _query(
        """SELECT 
              COUNT(*) FILTER (WHERE tipo_movimento = 'Passeggeri' OR tipo_movimento LIKE 'Passeggeri (%') AS pax,
              COUNT(*) FILTER (WHERE tipo_movimento LIKE 'Cargo%%') AS cargo,
              COUNT(*) FILTER (WHERE tipo_movimento LIKE 'Charter%%') AS charter,
              COUNT(*) FILTER (WHERE tipo_movimento = 'Non classificato') AS nc
           FROM h24_reports
           WHERE data_calendario BETWEEN %s AND %s""",
        (date_from, date_to))
    if rows:
        return {
            "pax": int(rows[0][0] or 0),
            "cargo": int(rows[0][1] or 0),
            "charter": int(rows[0][2] or 0),
            "non_classificato": int(rows[0][3] or 0),
        }
    return {"pax": 0, "cargo": 0, "charter": 0, "non_classificato": 0}


def build_web_json(days=90):
    today = datetime.now().date()
    date_to = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    date_from_calc = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    web_cfg = _get_web_config()
    min_date = web_cfg["min_date"]
    top_n = web_cfg["top_n_per_date"]
    date_from = max(date_from_calc, min_date)

    if date_from > date_to:
        logger.warning(
            f"Range non valido: date_from={date_from} > date_to={date_to} "
            f"(min_date={min_date}, days={days}). Uso date_to come date_from."
        )
        date_from = date_to

    logger.info(f"Costruzione JSON web: {date_from} -> {date_to} "
                f"(max {days} giorni, min_date={min_date}, top_n={top_n})")

    warnings = build_data_quality_warnings(date_from, date_to)

    disclaimer = build_disclaimer(min_date)
    summary = build_summary(date_from, date_to)
    movements = build_block_night_movements(date_from, date_to)
    anomalies = build_block_night_anomalies(date_from, date_to)
    destinations = build_block_night_destinations(date_from, date_to, top_n)
    destinations_pax = build_block_destinations_pax(date_from, date_to)
    geo_breakdown = build_block_geo_breakdown(date_from, date_to)
    airlines = build_block_night_airlines(date_from, date_to, top_n)
    weather = build_block_night_weather(date_from, date_to)
    runway_diag = build_block_runway_diagnostics(date_from, date_to)
    pista_fonte = build_block_pista_fonte(date_from, date_to)
    fleet_data = build_block_fleet(date_from, date_to)
    home_summary = build_home_summary(date_from, date_to)

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "data_quality_warnings": warnings,
        "period": {"from": date_from, "to": date_to},
        "min_date_active": min_date,
        "disclaimer": disclaimer,
        "summary": summary,
        "block_night_movements": movements,
        "block_night_anomalies": anomalies,
        "block_night_destinations": destinations,
        "block_destinations_pax": destinations_pax,
        "block_geo_breakdown": geo_breakdown,
        "block_night_airlines": airlines,
        "block_night_weather": weather,
        "block_runway_diagnostics": runway_diag,
        "block_pista_fonte": pista_fonte,
        "block_fleet": fleet_data,
        "block_home_summary": home_summary,
    }

    n_pax = len(fleet_data.get('passeggeri', {}).get('voli', []))
    n_cargo = len(fleet_data.get('cargo', {}).get('voli', []))
    n_charter = len(fleet_data.get('charter', {}).get('voli', []))
    logger.info(
        f"JSON web: {len(movements['by_date'])} giorni, "
        f"{anomalies['totals']} anomalie, "
        f"{len(destinations_pax.get('by_date', []))} giorni pax, "
        f"{len(geo_breakdown.get('by_date', []))} giorni geo, "
        f"{len(airlines['totals'])} compagnie, "
        f"fleet: pax={n_pax}, cargo={n_cargo}, charter={n_charter}, "
        f"home_summary h24={home_summary['h24']['total']} "
        f"night={home_summary['nightly']['total']}, "
        f"by_hour su {len(movements['by_hour'].get('by_date', []))} date, "
        f"warnings={len(warnings)}"
    )
    return payload


def build_delays_json(days=90):
    cfg = _get_delays_config()
    if not cfg["enabled"]:
        logger.info("Blocco delays disabilitato in config_data.json")
        return None

    today = datetime.now().date()
    date_to = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    date_from_calc = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    web_cfg = _get_web_config()
    min_date = web_cfg["min_date"]
    date_from = max(date_from_calc, min_date)

    if date_from > date_to:
        logger.warning(
            f"Range non valido: date_from={date_from} > date_to={date_to} "
            f"(min_date={min_date}, days={days}). Uso date_to come date_from."
        )
        date_from = date_to

    logger.info(f"Costruzione JSON ritardi: {date_from} -> {date_to} "
                f"(max {days} giorni, min_date={min_date})")

    warnings = build_data_quality_warnings(date_from, date_to)

    delays = build_block_delays_h24(date_from, date_to)
    if delays is None:
        return None

    hourly_weather = build_block_delays_hourly_weather(date_from, date_to)

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "data_quality_warnings": warnings,
        "period": {"from": date_from, "to": date_to},
        "min_date_active": min_date,
        "soglie": delays["soglie"],
        "by_date": delays["by_date"],
        "raw_delays": delays["raw_delays"],
        "block_delays_hourly_weather": hourly_weather
    }

    logger.info(
        f"JSON ritardi: {len(delays['by_date'])} giorni, "
        f"{len(delays['raw_delays'])} ritardi grezzi, "
        f"{len(hourly_weather) if hourly_weather else 0} ore meteo/ritardi, "
        f"soglie puntuale={delays['soglie']['puntuale_min']}min "
        f"grave={delays['soglie']['grave_min']}min, "
        f"warnings={len(warnings)}"
    )
    return payload


# =============================================================================
# SALVATAGGIO E PUBBLICAZIONE
# =============================================================================

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


def save_delays_json(payload):
    os.makedirs(WEB_OUTPUT_DIR, exist_ok=True)
    try:
        with open(DELAYS_OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(DELAYS_PREFIX)
            json.dump(payload, f, ensure_ascii=False, indent=2)
        size_kb = round(os.path.getsize(DELAYS_OUTPUT_FILE) / 1024, 1)
        logger.info(f"JSON ritardi salvato: {DELAYS_OUTPUT_FILE} ({size_kb} KB)")
        return DELAYS_OUTPUT_FILE
    except Exception as e:
        logger.error(f"Errore salvataggio JSON ritardi: {e}")
        return None


def export_and_publish(days=90, skip_gate=False):
    from bgy_core import bgy_wordpress
    payload = build_web_json(days=days)
    if not payload:
        return False, "JSON vuoto"

    if not skip_gate:
        gate_ok, gate_msg = _gate_check_pre_publish()
        if not gate_ok:
            logger.error(f"❌ Gate pre-publish (notturno): {gate_msg}")
            return False, f"Gate pre-publish bloccato: {gate_msg}"
        logger.info(f"✅ Gate pre-publish (notturno): OK")

    local_path = save_web_json(payload)
    if not local_path:
        return False, "Errore salvataggio JSON locale"
    if not bgy_wordpress.is_enabled():
        return True, f"JSON locale salvato ({local_path}), WordPress disabilitato"
    ok, msg, url = bgy_wordpress.publish_json(local_path)
    return (True, f"Pubblicato: {url}") if ok else (False, f"Errore: {msg}")


def export_delays_and_publish(days=90, skip_gate=False):
    from bgy_core import bgy_wordpress
    payload = build_delays_json(days=days)
    if not payload:
        return False, "JSON ritardi vuoto (config disabilitata?)"

    if not skip_gate:
        gate_ok, gate_msg = _gate_check_pre_publish()
        if not gate_ok:
            logger.error(f"❌ Gate pre-publish (ritardi): {gate_msg}")
            return False, f"Gate pre-publish bloccato: {gate_msg}"
        logger.info(f"✅ Gate pre-publish (ritardi): OK")

    local_path = save_delays_json(payload)
    if not local_path:
        return False, "Errore salvataggio JSON ritardi locale"
    if not bgy_wordpress.is_enabled():
        return True, f"JSON ritardi locale salvato ({local_path}), WordPress disabilitato"
    ok, msg, url = bgy_wordpress.publish_json(local_path)
    return (True, f"Ritardi pubblicati: {url}") if ok else (False, f"Errore: {msg}")


# =============================================================================
# MAIN CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--publish", action="store_true",
                        help="Pubblica bgy-data.csv su WordPress")
    parser.add_argument("--publish-delays", action="store_true",
                        help="Pubblica bgy-delays.csv su WordPress")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-gate", action="store_true",
                        help="QA-02: salta il gate pre-publish (per test)")
    args = parser.parse_args()

    if not bgy_db.is_enabled():
        print("DB non abilitato")
        sys.exit(1)

    if args.publish_delays:
        ok, msg = export_delays_and_publish(
            days=args.days, skip_gate=args.skip_gate)
        print(f"{'OK' if ok else 'ERRORE'}: {msg}")
        sys.exit(0 if ok else 1)

    if args.dry_run or not args.publish:
        payload = build_web_json(days=args.days)
        path = save_web_json(payload)
        if path:
            print(f"JSON salvato: {path}")
        delays_payload = build_delays_json(days=args.days)
        if delays_payload:
            delays_path = save_delays_json(delays_payload)
            if delays_path:
                print(f"JSON ritardi salvato: {delays_path}")
        sys.exit(0)

    ok, msg = export_and_publish(days=args.days, skip_gate=args.skip_gate)
    print(f"{'OK' if ok else 'ERRORE'}: {msg}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()