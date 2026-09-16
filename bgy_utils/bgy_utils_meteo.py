"""
bgy_utils/bgy_utils_meteo.py - Integrazione meteo Open-Meteo.
Versione 2.5.0

- Finestra notturna: 20:00 -> 06:00 del giorno successivo (configurabile).
- Coordinate, orari, timezone e timeout: da config_data.json (weather).
- Salva un CSV dedicato per ogni sessione notturna.
"""
import os
import sys

# Bootstrap: assicura che la root del progetto sia nel sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import pandas as pd
from datetime import datetime, timedelta

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_config_manager import config_manager
from bgy_core.bgy_dates import normalize_date
from bgy_core.bgy_paths import OUTPUT_CSV_DIR

logger = get_logger("Meteo")

# Mapping dei codici meteo WMO (standard internazionale, non configurabile)
WMO_CODES = {
    0: "Cielo Sereno",
    1: "Prevalentemente Sereno", 2: "Parzialmente Nuvoloso", 3: "Coperto",
    45: "Nebbia", 48: "Nebbia con brina",
    51: "Pioggerella Leggera", 53: "Pioggerella Moderata", 55: "Pioggerella Densa",
    61: "Pioggia Leggera", 63: "Pioggia Moderata", 65: "Pioggia Forte",
    71: "Neve Leggera", 73: "Neve Moderata", 75: "Neve Forte",
    80: "Rovescio Leggero", 81: "Rovescio Moderato", 82: "Rovescio Violento",
    95: "Temporale", 96: "Temporale con Grandine Leggera",
    99: "Temporale con Grandine Forte",
}


def _weather_cfg():
    """Legge la config weather con default."""
    return config_manager.get_weather_config()


def fetch_night_weather_df(date_str):
    """
    Recupera i dati meteo orari per BGY nella finestra notturna.
    Finestra: ore start_hour del giorno date_str -> ore end_hour del giorno dopo.
    Ritorna un DataFrame vuoto in caso di errore.
    """
    cfg = _weather_cfg()
    lat = cfg["latitude"]
    lon = cfg["longitude"]
    tz = cfg["timezone"]
    timeout = cfg["http_timeout"]

    date_norm = normalize_date(date_str)
    if not date_norm:
        logger.warning(f"Data meteo non valida: {date_str}")
        return pd.DataFrame()

    try:
        dt_start = datetime.strptime(date_norm, "%Y-%m-%d")
        dt_end = dt_start + timedelta(days=1)
        start_date = dt_start.strftime("%Y-%m-%d")
        end_date = dt_end.strftime("%Y-%m-%d")

        tz_encoded = tz.replace("/", "%2F")
        base_params = (
            f"latitude={lat}&longitude={lon}"
            f"&start_date={start_date}&end_date={end_date}"
            f"&hourly=temperature_2m,precipitation,rain,wind_speed_10m,"
            f"wind_direction_10m,weather_code"
            f"&timezone={tz_encoded}"
        )

        url = f"https://archive-api.open-meteo.com/v1/archive?{base_params}"
        resp = requests.get(url, timeout=timeout)

        if resp.status_code != 200:
            # Fallback alla API forecast
            url = f"https://api.open-meteo.com/v1/forecast?{base_params}"
            resp = requests.get(url, timeout=timeout)

        if resp.status_code != 200:
            logger.warning(f"Open-Meteo HTTP {resp.status_code}")
            return pd.DataFrame()

        data = resp.json()
        if "hourly" not in data:
            logger.warning("Open-Meteo: risposta senza 'hourly'")
            return pd.DataFrame()

        df = pd.DataFrame(data["hourly"])
        df["time"] = pd.to_datetime(df["time"])

        # Finestra: [date_norm start_hour] -> [date_norm+1 end_hour]
        night_start = pd.to_datetime(f"{start_date} {cfg['start_hour']:02d}:00")
        night_end = pd.to_datetime(f"{end_date} {cfg['end_hour']:02d}:00")

        df_night = df[(df["time"] >= night_start) & (df["time"] < night_end)].copy()
        df_night["orario"] = df_night["time"].dt.strftime("%H:%M")
        df_night["condizioni"] = df_night["weather_code"].map(
            lambda c: WMO_CODES.get(c, "N/D")
        )

        rename_map = {
            "temperature_2m": "temperatura_c",
            "precipitation": "precipitazioni_mm",
            "wind_speed_10m": "vento_kmh",
            "wind_direction_10m": "vento_direzione_deg",
        }
        cols = ["orario", "temperature_2m", "precipitation",
                "wind_speed_10m", "wind_direction_10m", "condizioni"]
        df_result = df_night[cols].rename(columns=rename_map)

        logger.info(
            f"🌤️ Meteo {date_norm} ({cfg['start_hour']:02d}:00-"
            f"{cfg['end_hour']:02d}:00): {len(df_result)} ore"
        )
        return df_result

    except Exception as e:
        logger.error(f"Errore recupero meteo: {e}")
        return pd.DataFrame()


def get_night_weather_summary(date_str):
    """Ritorna una sintesi testuale delle condizioni meteo notturne."""
    cfg = _weather_cfg()
    df = fetch_night_weather_df(date_str)
    if df.empty:
        return "Condizioni meteo non disponibili per la fascia notturna."

    header = (f"=== Condizioni Meteo Notturne "
              f"({date_str} {cfg['start_hour']:02d}:00 - "
              f"{cfg['end_hour']:02d}:00) ===")
    lines = [header]
    for _, row in df.iterrows():
        vento = row.get("vento_kmh", "N/D")
        direzione = row.get("vento_direzione_deg", "N/D")
        lines.append(
            f"  • {row['orario']} -> {row['condizioni']} | "
            f"Temp: {row['temperatura_c']}°C | "
            f"Vento: {vento} km/h ({direzione}°) | "
            f"Pioggia: {row['precipitazioni_mm']} mm"
        )
    return "\n".join(lines)


def save_night_weather(date_str):
    """
    Salva il CSV meteo della sessione notturna.
    Nome file: meteo_YYYY-MM-DD.csv (data di inizio sessione).
    Ritorna il path del file salvato, o None se non ci sono dati.
    """
    date_norm = normalize_date(date_str)
    if not date_norm:
        logger.warning(f"Data meteo non valida per salvataggio: {date_str}")
        return None

    df = fetch_night_weather_df(date_norm)
    if df.empty:
        logger.warning(f"Nessun dato meteo da salvare per {date_norm}")
        return None

    os.makedirs(OUTPUT_CSV_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_CSV_DIR, f"meteo_{date_norm}.csv")
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info(f"💾 Meteo salvato: {out_path}")
    return out_path


def get_meteo_filename(session_date_str):
    """Ritorna il nome file meteo per una sessione (data inizio)."""
    n = normalize_date(session_date_str)
    if not n:
        return None
    return f"meteo_{n}.csv"


if __name__ == "__main__":
    print("🧪 Test meteo...")
    oggi = datetime.now().strftime("%Y-%m-%d")
    print(get_night_weather_summary(oggi))
    p = save_night_weather(oggi)
    if p:
        print(f"📁 File: {p}")