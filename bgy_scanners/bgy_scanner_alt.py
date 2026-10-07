"""
bgy_scanners/bgy_scanner_alt.py - Scanner alternativo (Avionio).
Versione 0.3.0

Scopo:
  - Fonte alternativa di confronto per i dati SACBO.
  - Fallback quando SACBO è irraggiungibile (Cloudflare, sito giù).
  - INFRA-01: fonte scheduled integrativa per il cargo.
  - I dati sono salvati in bgy_data/bgy_avionio/ (rotazione 7 giorni).

Fonte: https://www.avionio.com/en/airport/bgy/{arrivals,departures}

Struttura tabella HTML:
    Time | Date | IATA | Origin/Destination | Flight | Airline | Status

Novità v0.3.0 (INFRA-01, 07/10/2026):
- Aggiunta fetch_as_scheduled_rows(date_norm): ritorna i voli Avionio
  della sessione notturna nel formato di load_scheduled_flights()
  (callsign_volo, tipo_movimento, destinazione_origine, orario_schedulato,
  orario_effettivo, stato_volo, fonte_scheduled='avionio').
  Usata da bgy_report_night.py v2.9.19 in load_avionio_scheduled().
- Aggiunta read_scheduled_from_files(date_norm): legge i file già salvati
  della sessione (flat YYYY-MM-DD_HH-MM) e li deduplica per
  (callsign, orario_schedulato, tipo_movimento), tenendo il record più
  recente (post-operativo > pre-operativo).
- La struttura di salvataggio resta FLAT (retrocompatibile con i file
  esistenti). Niente cartelle per data.

Novità v0.2.0 (failover SACBO):
- Aggiunta fetch_as_scan_rows(): formato compatibile con scan_*.csv
  di SACBO per il fallback di bgy_scanner_day.py.
- Aggiunta STATUS_MAP: traduzione stati Avionio in italiano.
- Aggiunta _avionio_effective_time().

Novità v0.1.1:
- Fix _normalize_callsign: 'FR3403' → 'FR 3403'.

Uso:
    py -3.12 -m bgy_scanners.bgy_scanner_alt
    py -3.12 -m bgy_scanners.bgy_scanner_alt --movement arrivals
    py -3.12 -m bgy_scanners.bgy_scanner_alt --cleanup
    py -3.12 -m bgy_scanners.bgy_scanner_alt --list-session 2026-10-01
    py -3.12 -m bgy_scanners.bgy_scanner_alt --debug-scheduled 2026-10-01
"""
import os
import re
import sys
import csv
import argparse
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_dates import normalize_date

logger = get_logger("ScannerAlt")

AVIONIO_BASE = "https://www.avionio.com/en/airport/bgy"
AVIONIO_ARRIVALS = f"{AVIONIO_BASE}/arrivals"
AVIONIO_DEPARTURES = f"{AVIONIO_BASE}/departures"

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AVIONIO_DIR = os.path.join(_PROJECT_ROOT, "bgy_data", "bgy_avionio")

RETENTION_DAYS = 7

# Finestra oraria schedulata ammessa per il report notturno (filtro STRETTO)
NIGHT_START_MIN = 23 * 60   # 23:00
NIGHT_END_MIN = 6 * 60      # 06:00 (escluso)

# Fascia dei FILE da leggere per la sessione notturna:
# dal file "22-00" del giorno X al file "06-30" del giorno X+1.
SESSION_FILE_HOURS_START = 22   # X hh>=22
SESSION_FILE_HOURS_END = 7      # X+1 hh<7

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

FIELDNAMES = [
    "callsign_volo", "tipo_movimento", "destinazione_origine",
    "orario_schedulato", "orario_effettivo", "stato_volo",
    "compagnia_aerea", "codice_iata", "data", "fonte",
]

STATUS_MAP = {
    # Stati "a terra"
    "boarding": "Imbarco in corso",
    "boarding closed": "Imbarco chiuso",
    "gate closed": "Imbarco chiuso",
    "gate open": "Operativo",
    "last call": "Imbarco ultima chiamata",
    "check-in": "Operativo",
    "check in": "Operativo",
    "checkin": "Operativo",
    "delayed": "In ritardo",
    "estimated": "Operativo",
    "scheduled": "Operativo",
    "on time": "Operativo",
    "on-time": "Operativo",
    # Stati "operati"
    "departed": "Decollato",
    "took off": "Decollato",
    "tookoff": "Decollato",
    "airborne": "In volo",
    "en route": "In volo",
    "landed": "Atterrato",
    "arrived": "Atterrato",
    "arrival": "Atterrato",
    # Stati terminali
    "cancelled": "Cancellato",
    "canceled": "Cancellato",
    "diverted": "Dirottato",
    "unknown": "Operativo",
    "": "Operativo",
}

STATI_PRE_OPERATIVI = (
    "operativo", "imbarco", "check-in", "stimato", "scheduled",
)

STATI_POST_OPERATIVI = (
    "decollato", "atterrato", "arrivato", "in volo", "partito",
)

# File name regex: avionio_{arrivals|departures}_{YYYY-MM-DD}_{HH-MM}.csv
_FILENAME_RE = re.compile(
    r"^avionio_(arrivals|departures)_(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})\.csv$"
)


# -----------------------------------------------------------------------------
# UTILITY
# -----------------------------------------------------------------------------

def _normalize_callsign(flight):
    """Normalizza il numero di volo: 'FR3403' → 'FR 3403'."""
    if not flight:
        return ""
    flight = str(flight).strip()
    if " " in flight:
        return flight
    m = re.match(r'^([A-Z][A-Z0-9]|[A-Z]{3})(\d+)$', flight.upper())
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return flight


def _is_valid_time(hhmm):
    if not hhmm:
        return False
    return bool(re.match(r'^\d{1,2}:\d{2}$', str(hhmm).strip()))


def _translate_status(status):
    """Traduce lo stato Avionio in italiano SACBO-compatibile."""
    if not status:
        return "Operativo"
    s = str(status).strip().lower()
    if s in STATUS_MAP:
        return STATUS_MAP[s]
    for key, value in STATUS_MAP.items():
        if key and key in s:
            return value
    return str(status).strip()


def _avionio_effective_time(status_translated, orario_schedulato):
    """
    Stima l'orario effettivo da uno stato Avionio.

    Avionio non fornisce un campo separato di orario effettivo. La logica:
      - post-operativo → vuoto (orario effettivo non disponibile)
      - cancellato/dirottato → vuoto
      - in ritardo → vuoto
      - pre-operativo → uguale allo schedulato (assunzione "in orario")
    """
    s = str(status_translated).strip().lower()

    if any(k in s for k in ("cancellat", "cancelled", "canceled",
                             "dirottat", "diverted")):
        return ""
    if any(k in s for k in ("in ritardo", "delayed")):
        return ""
    if any(k in s for k in ("decollato", "atterrato", "arrivato",
                             "in volo", "partito")):
        return ""
    return orario_schedulato if _is_valid_time(orario_schedulato) else ""


def _time_to_minutes(hhmm):
    if not hhmm:
        return None
    try:
        parts = str(hhmm).strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError, AttributeError):
        return None


def _is_in_night_schedule(hhmm):
    """True se l'orario schedulato è tra 23:00 e 05:59 (inclusi)."""
    mins = _time_to_minutes(hhmm)
    if mins is None:
        return False
    return mins >= NIGHT_START_MIN or mins < NIGHT_END_MIN


def _is_in_night_schedule_extended(hhmm):
    """
    Finestra estesa per il match scheduled Avionio:
    22:30-06:30. Serve a catturare voli con sched leggermente fuori fascia
    (es. 22:55, 06:05) che però possono essere operati in fascia.
    Il filtro stretto avviene poi nel report notturno.
    """
    mins = _time_to_minutes(hhmm)
    if mins is None:
        return False
    return (mins >= 22 * 60 + 30) or (mins < 6 * 60 + 30)


# -----------------------------------------------------------------------------
# FETCH E PARSING (invariati da v0.2.0)
# -----------------------------------------------------------------------------

def fetch_avionio(url, movement_type):
    """Scarica e parsa una pagina Avionio."""
    try:
        logger.info(f"🌐 Fetch Avionio: {movement_type}")
        r = requests.get(url, headers=HEADERS, timeout=20)

        if r.status_code != 200:
            logger.warning(f"⚠️ Avionio status {r.status_code}")
            return []

        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table")
        if not table:
            logger.warning("⚠️ Nessuna tabella trovata in Avionio")
            return []

        rows = table.find_all("tr")
        flights = []
        skipped_header = 0
        skipped_invalid = 0

        for row in rows:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            cell_texts = [c.get_text(strip=True) for c in cells]

            first = cell_texts[0] if cell_texts else ""
            if first in ("Time", "") or first.startswith("Previous"):
                skipped_header += 1
                continue

            if len(cell_texts) < 7:
                skipped_invalid += 1
                continue

            time_str = cell_texts[0].strip()
            date_str = cell_texts[1].strip()
            iata = cell_texts[2].strip()
            city = cell_texts[3].strip()
            flight = cell_texts[4].strip()
            airline = cell_texts[5].strip()
            status = cell_texts[6].strip()

            if not _is_valid_time(time_str):
                skipped_invalid += 1
                continue

            flight_norm = _normalize_callsign(flight)
            if not flight_norm:
                skipped_invalid += 1
                continue

            mov = "A" if movement_type == "arrivals" else "D"

            flights.append({
                "callsign_volo": flight_norm,
                "tipo_movimento": mov,
                "destinazione_origine": city,
                "orario_schedulato": time_str,
                "orario_effettivo": "",
                "stato_volo": status,
                "compagnia_aerea": airline,
                "codice_iata": iata,
                "data": date_str,
                "fonte": "avionio",
            })

        logger.info(
            f"✅ Avionio {movement_type}: {len(flights)} voli "
            f"(scartate {skipped_header} righe header, "
            f"{skipped_invalid} righe invalide)"
        )
        return flights

    except requests.Timeout:
        logger.error(f"❌ Timeout Avionio ({movement_type})")
        return []
    except requests.RequestException as e:
        logger.error(f"❌ Errore rete Avionio: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ Errore Avionio: {e}")
        return []


# -----------------------------------------------------------------------------
# SALVATAGGIO E PULIZIA
# -----------------------------------------------------------------------------

def save_to_csv(flights, movement_type):
    """Salva i voli in un file CSV (flat, retrocompatibile)."""
    if not flights:
        logger.info(f"⏭️ Nessun volo da salvare ({movement_type})")
        return None

    try:
        os.makedirs(AVIONIO_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"avionio_{movement_type}_{ts}.csv"
        filepath = os.path.join(AVIONIO_DIR, filename)

        with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            for fl in flights:
                writer.writerow(fl)

        logger.info(f"💾 Salvato: {filename} ({len(flights)} voli)")
        return filepath

    except Exception as e:
        logger.error(f"❌ Errore salvataggio {movement_type}: {e}")
        return None


def cleanup_old_files(days=RETENTION_DAYS):
    """Rimuove i file Avionio più vecchi di N giorni."""
    if not os.path.isdir(AVIONIO_DIR):
        return 0

    cutoff = datetime.now().timestamp() - (days * 86400)
    removed = 0

    try:
        for f in os.listdir(AVIONIO_DIR):
            if not f.endswith(".csv"):
                continue
            full = os.path.join(AVIONIO_DIR, f)
            try:
                if os.path.getmtime(full) < cutoff:
                    os.remove(full)
                    removed += 1
            except Exception as e:
                logger.warning(f"Errore rimozione {f}: {e}")
    except Exception as e:
        logger.error(f"❌ Errore cleanup Avionio: {e}")

    return removed


# -----------------------------------------------------------------------------
# FUNZIONI PUBBLICHE (v0.2.0)
# -----------------------------------------------------------------------------

def run_scan_alt(movement_type="both"):
    """Esegue lo scan Avionio."""
    results = {}

    if movement_type in ("arrivals", "both"):
        arr = fetch_avionio(AVIONIO_ARRIVALS, "arrivals")
        path = save_to_csv(arr, "arrivals")
        results["arrivals"] = {"count": len(arr), "path": path}

    if movement_type in ("departures", "both"):
        dep = fetch_avionio(AVIONIO_DEPARTURES, "departures")
        path = save_to_csv(dep, "departures")
        results["departures"] = {"count": len(dep), "path": path}

    return results


def fetch_all():
    """Ritorna (arrivals, departures) senza salvare su file."""
    arr = fetch_avionio(AVIONIO_ARRIVALS, "arrivals")
    dep = fetch_avionio(AVIONIO_DEPARTURES, "departures")
    return arr, dep


def fetch_as_scan_rows():
    """
    Ritorna i voli Avionio nel formato compatibile con scan_*.csv di SACBO.

    Usata da bgy_scanner_day.py come fallback quando SACBO è irraggiungibile.
    """
    arr, dep = fetch_all()
    rows = []

    for fl in (arr or []):
        stato_tradotto = _translate_status(fl.get("stato_volo", ""))
        orario_eff = _avionio_effective_time(
            stato_tradotto, fl.get("orario_schedulato", "")
        )
        rows.append({
            "callsign_volo": fl.get("callsign_volo", ""),
            "tipo_movimento": fl.get("tipo_movimento", "A"),
            "destinazione_origine": fl.get("destinazione_origine", ""),
            "orario_schedulato": fl.get("orario_schedulato", ""),
            "orario_effettivo": orario_eff,
            "stato_volo": stato_tradotto,
            "fonte_scan": "avionio",
        })

    for fl in (dep or []):
        stato_tradotto = _translate_status(fl.get("stato_volo", ""))
        orario_eff = _avionio_effective_time(
            stato_tradotto, fl.get("orario_schedulato", "")
        )
        rows.append({
            "callsign_volo": fl.get("callsign_volo", ""),
            "tipo_movimento": fl.get("tipo_movimento", "D"),
            "destinazione_origine": fl.get("destinazione_origine", ""),
            "orario_schedulato": fl.get("orario_schedulato", ""),
            "orario_effettivo": orario_eff,
            "stato_volo": stato_tradotto,
            "fonte_scan": "avionio",
        })

    logger.info(
        f"📦 Avionio → scan rows: {len(rows)} voli "
        f"({len(arr or [])} arrivi + {len(dep or [])} partenze)"
    )
    return rows


# -----------------------------------------------------------------------------
# v0.3.0 — LETTURA FILE SALVATI PER IL REPORT NOTTURNO
# -----------------------------------------------------------------------------

def _list_session_files(date_norm):
    """
    Ritorna i file Avionio che coprono la sessione notturna:
      - giorno X: file con ora >= 22:00
      - giorno X+1: file con ora < 07:00

    La sessione notturna è definita come 'notte del giorno X'.
    """
    if not os.path.isdir(AVIONIO_DIR):
        return []

    date_dt = datetime.strptime(date_norm, "%Y-%m-%d")
    next_date_norm = (date_dt + timedelta(days=1)).strftime("%Y-%m-%d")

    files = []
    for fname in os.listdir(AVIONIO_DIR):
        m = _FILENAME_RE.match(fname)
        if not m:
            continue
        movement = m.group(1)
        fdate = m.group(2)
        fhour = int(m.group(3))

        if fdate == date_norm and fhour >= SESSION_FILE_HOURS_START:
            files.append(os.path.join(AVIONIO_DIR, fname))
        elif fdate == next_date_norm and fhour < SESSION_FILE_HOURS_END:
            files.append(os.path.join(AVIONIO_DIR, fname))

    files.sort()
    return files


def _read_avionio_file(filepath):
    """Legge un file Avionio e ritorna una lista di dict."""
    rows = []
    try:
        with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(r)
    except Exception as e:
        logger.warning(f"Errore lettura {filepath}: {e}")
    return rows


def read_scheduled_from_files(date_norm):
    """
    v0.3.0: legge tutti i file Avionio della sessione notturna (dal file
    '22-00' del giorno X al file '06-30' del giorno X+1), li deduplica
    per (callsign, orario_schedulato, tipo_movimento), tenendo il record
    con lo stato più avanzato (post-operativo > pre-operativo).

    Ritorna una lista di dict pronti per il merge con SACBO, nel formato:
        {
            callsign_volo: 'DJ 6498',
            tipo_movimento: 'A'|'D',
            destinazione_origine: 'Cologne/Bonn',
            orario_schedulato: '05:15',
            orario_effettivo: '',
            stato_volo: 'Operativo',
            fonte_scheduled: 'avionio',
            codice_iata: 'CGN',
            compagnia_aerea: 'Air Djibouti',
        }

    Filtra gli orari fuori dalla finestra ESTESA 22:30-06:30.
    Il filtro STRETTO 23:00-05:59 avviene poi nel report notturno.
    """
    date_norm = normalize_date(date_norm)
    if not date_norm:
        logger.warning(f"read_scheduled_from_files: data non valida")
        return []

    files = _list_session_files(date_norm)
    if not files:
        logger.info(f"📁 Nessun file Avionio per la sessione {date_norm}")
        return []

    logger.info(f"📁 File Avionio sessione {date_norm}: {len(files)}")

    # Chiave: (callsign_normalizzato, orario_schedulato, tipo_movimento)
    dedup = {}

    for fp in files:
        rows = _read_avionio_file(fp)
        for r in rows:
            cs = _normalize_callsign(r.get("callsign_volo", ""))
            sched = (r.get("orario_schedulato") or "").strip()
            mov = (r.get("tipo_movimento") or "").strip().upper()

            if not cs or not sched or mov not in ("A", "D"):
                continue
            if not _is_in_night_schedule_extended(sched):
                continue

            stato_tradotto = _translate_status(r.get("stato_volo", ""))
            is_post = any(k in stato_tradotto.lower()
                          for k in ("decollato", "atterrato", "arrivato",
                                    "in volo", "partito"))
            priority = 1 if is_post else 0

            key = (cs, sched, mov)
            existing = dedup.get(key)
            if existing is None or priority > existing["_priority"]:
                dedup[key] = {
                    "callsign_volo": cs,
                    "tipo_movimento": mov,
                    "destinazione_origine": r.get("destinazione_origine", ""),
                    "orario_schedulato": sched,
                    "orario_effettivo": _avionio_effective_time(
                        stato_tradotto, sched
                    ),
                    "stato_volo": stato_tradotto,
                    "fonte_scheduled": "avionio",
                    "codice_iata": r.get("codice_iata", ""),
                    "compagnia_aerea": r.get("compagnia_aerea", ""),
                    "_priority": priority,
                }

    result = []
    for v in dedup.values():
        v.pop("_priority", None)
        result.append(v)

    logger.info(
        f"📋 Avionio scheduled sessione {date_norm}: {len(result)} voli "
        f"(su {len(files)} file, finestra estesa 22:30-06:30)"
    )
    return result


def fetch_as_scheduled_rows(date_norm):
    """
    v0.3.0: come read_scheduled_from_files(), ma se i file della sessione
    non esistono tenta un fetch live da Avionio.

    Usata da bgy_report_night.py v2.9.19. In produzione i file ci sono
    sempre (raccolti dallo scheduler), quindi il fetch live è un fallback.
    """
    rows = read_scheduled_from_files(date_norm)
    if rows:
        return rows

    logger.info(f"📡 Nessun file Avionio per {date_norm}, tenta fetch live")
    arr, dep = fetch_all()
    out = []
    for fl in (arr or []):
        sched = fl.get("orario_schedulato", "")
        if not _is_in_night_schedule_extended(sched):
            continue
        stato_tradotto = _translate_status(fl.get("stato_volo", ""))
        out.append({
            "callsign_volo": fl.get("callsign_volo", ""),
            "tipo_movimento": fl.get("tipo_movimento", "A"),
            "destinazione_origine": fl.get("destinazione_origine", ""),
            "orario_schedulato": sched,
            "orario_effettivo": _avionio_effective_time(stato_tradotto, sched),
            "stato_volo": stato_tradotto,
            "fonte_scheduled": "avionio",
            "codice_iata": fl.get("codice_iata", ""),
            "compagnia_aerea": fl.get("compagnia_aerea", ""),
        })
    for fl in (dep or []):
        sched = fl.get("orario_schedulato", "")
        if not _is_in_night_schedule_extended(sched):
            continue
        stato_tradotto = _translate_status(fl.get("stato_volo", ""))
        out.append({
            "callsign_volo": fl.get("callsign_volo", ""),
            "tipo_movimento": fl.get("tipo_movimento", "D"),
            "destinazione_origine": fl.get("destinazione_origine", ""),
            "orario_schedulato": sched,
            "orario_effettivo": _avionio_effective_time(stato_tradotto, sched),
            "stato_volo": stato_tradotto,
            "fonte_scheduled": "avionio",
            "codice_iata": fl.get("codice_iata", ""),
            "compagnia_aerea": fl.get("compagnia_aerea", ""),
        })
    return out


# -----------------------------------------------------------------------------
# MAIN (CLI)
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scanner Avionio (fonte alternativa)")
    parser.add_argument(
        "--movement",
        choices=["arrivals", "departures", "both"],
        default="both",
        help="Cosa scaricare (default: both)"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Esegue solo la pulizia dei file vecchi"
    )
    parser.add_argument(
        "--list-session",
        type=str,
        metavar="YYYY-MM-DD",
        help="Elenca i file della sessione notturna"
    )
    parser.add_argument(
        "--debug-scheduled",
        type=str,
        metavar="YYYY-MM-DD",
        help="Stampa i voli scheduled letti da Avionio per la sessione"
    )
    args = parser.parse_args()

    if args.cleanup:
        n = cleanup_old_files()
        print(f"🧹 Rimossi {n} file vecchi")
        return

    if args.list_session:
        files = _list_session_files(normalize_date(args.list_session))
        print(f"📁 File sessione {args.list_session}: {len(files)}")
        for f in files:
            print(f"  · {os.path.basename(f)}")
        return

    if args.debug_scheduled:
        rows = read_scheduled_from_files(normalize_date(args.debug_scheduled))
        print(f"📋 Voli scheduled Avionio: {len(rows)}")
        for r in rows:
            print(f"  · {r['callsign_volo']:12s} {r['tipo_movimento']} "
                  f"sched {r['orario_schedulato']:5s} → {r['destinazione_origine']}"
                  f" ({r['stato_volo']})")
        return

    results = run_scan_alt(args.movement)

    print()
    print("=" * 60)
    print("SCANNER AVIONIO — RISULTATO")
    print("=" * 60)
    for k, v in results.items():
        path = v["path"] if v["path"] else "n/d"
        print(f"  {k:12s}: {v['count']:3d} voli  →  {path}")

    n = cleanup_old_files()
    if n > 0:
        print(f"\n🧹 Rimossi {n} file Avionio più vecchi di {RETENTION_DAYS} giorni")


if __name__ == "__main__":
    main()