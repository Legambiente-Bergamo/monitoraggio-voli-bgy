"""
bgy_scanners/bgy_scanner_alt.py - Scanner alternativo (Avionio).
Versione 0.1.1

Scopo:
  - Fornire una fonte alternativa di confronto per i dati SACBO.
  - NON sostituisce lo scanner principale (bgy_scanner_day.py).
  - I dati sono salvati in bgy_data/bgy_avionio/ (rotazione 7 giorni).

Fonte: https://www.avionio.com/en/airport/bgy/{arrivals,departures}

Struttura tabella HTML:
    Time | Date | IATA | Origin/Destination | Flight | Airline | Status

Novità v0.1.1:
- Fix _normalize_callsign: 'FR3403' → 'FR 3403' (era 'FR3 403').
  Regex ora distingue IATA (2 char) da ICAO (3 lettere).

Uso:
    py -3.12 -m bgy_scanners.bgy_scanner_alt
    py -3.12 -m bgy_scanners.bgy_scanner_alt --movement arrivals
    py -3.12 -m bgy_scanners.bgy_scanner_alt --movement departures
    py -3.12 -m bgy_scanners.bgy_scanner_alt --cleanup
"""
import os
import re
import sys
import csv
import argparse
from datetime import datetime

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_logger import get_logger

logger = get_logger("ScannerAlt")

AVIONIO_BASE = "https://www.avionio.com/en/airport/bgy"
AVIONIO_ARRIVALS = f"{AVIONIO_BASE}/arrivals"
AVIONIO_DEPARTURES = f"{AVIONIO_BASE}/departures"

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AVIONIO_DIR = os.path.join(_PROJECT_ROOT, "bgy_data", "bgy_avionio")

RETENTION_DAYS = 7

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


# -----------------------------------------------------------------------------
# UTILITY
# -----------------------------------------------------------------------------

def _normalize_callsign(flight):
    """
    Normalizza il numero di volo: 'FR3403' → 'FR 3403'.
    Gestisce prefissi IATA (2 char) e ICAO (3 lettere).
    Lascia invariati i casi già normalizzati ('FR 3403').
    """
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


# -----------------------------------------------------------------------------
# FETCH E PARSING
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
    """Salva i voli in un file CSV."""
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
# FUNZIONI PUBBLICHE
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
    args = parser.parse_args()

    if args.cleanup:
        n = cleanup_old_files()
        print(f"🧹 Rimossi {n} file vecchi")
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