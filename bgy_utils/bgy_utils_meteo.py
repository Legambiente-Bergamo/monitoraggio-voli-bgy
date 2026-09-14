"""
bgy_utils_meteo.py - Integrazione meteo Open-Meteo.
"""
import requests
import pandas as pd
from datetime import datetime, timedelta

from core.bgy_logger import get_logger

logger = get_logger("Meteo")

LATITUDE = 45.6739
LONGITUDE = 9.7042

# Mappatura dei codici meteo WMO in descrizioni leggibili
WMO_CODES = {
    0: "Cielo Sereno",
    1: "Prevalentemente Sereno", 2: "Parzialmente Nuvoloso", 3: "Coperto",
    45: "Nebbia", 48: "Nebbia con brina",
    51: "Pioggerella Leggera", 53: "Pioggerella Moderata", 55: "Pioggerella Densa",
    61: "Pioggia Leggera", 63: "Pioggia Moderata", 65: "Pioggia Forte",
    71: "Neve Leggera", 73: "Neve Moderata", 75: "Neve Forte",
    80: "Rovescio Leggero", 81: "Rovescio Moderato", 82: "Rovescio Violento",
    95: "Temporale", 96: "Temporale con Grandine Leggera", 99: "Temporale con Grandine Forte"
}


def fetch_night_weather_df(date_str):
    """
    Recupera i dati meteo orari per BGY nella fascia notturna (23:00 del giorno date_str -> 06:00 del giorno dopo).
    """
    try:
        dt_start = datetime.strptime(date_str, "%Y-%m-%d")
        dt_end = dt_start + timedelta(days=1)

        start_date = dt_start.strftime("%Y-%m-%d")
        end_date = dt_end.strftime("%Y-%m-%d")

        url = (
            f"https://archive-api.open-meteo.com/v1/archive?"
            f"latitude={LATITUDE}&longitude={LONGITUDE}"
            f"&start_date={start_date}&end_date={end_date}"
            f"&hourly=temperature_2m,precipitation,rain,wind_speed_10m,weather_code"
            f"&timezone=Europe%2FRome"
        )

        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            # Fallback all'API forecast
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={LATITUDE}&longitude={LONGITUDE}"
                f"&start_date={start_date}&end_date={end_date}"
                f"&hourly=temperature_2m,precipitation,rain,wind_speed_10m,weather_code"
                f"&timezone=Europe%2FRome"
            )
            resp = requests.get(url, timeout=10)

        data = resp.json()
        if "hourly" not in data:
            return pd.DataFrame()

        df = pd.DataFrame(data["hourly"])
        df['time'] = pd.to_datetime(df['time'])

        night_start = pd.to_datetime(f"{start_date} 23:00")
        night_end = pd.to_datetime(f"{end_date} 06:00")

        df_night = df[(df['time'] >= night_start) & (df['time'] <= night_end)].copy()
        df_night['orario'] = df_night['time'].dt.strftime("%H:%M")
        df_night['condizioni'] = df_night['weather_code'].map(lambda c: WMO_CODES.get(c, "N/D"))

        df_result = df_night[['orario', 'temperature_2m', 'precipitation', 'wind_speed_10m', 'condizioni']].rename(
            columns={
                'temperature_2m': 'temperatura_c',
                'precipitation': 'precipitazioni_mm',
                'wind_speed_10m': 'vento_kmh'
            }
        )
        return df_result

    except Exception as e:
        logger.error(f"Errore recupero meteo: {e}")
        return pd.DataFrame()


def get_night_weather_summary(date_str):
    """Restituisce una sintesi testuale formattata delle condizioni meteo notturne."""
    df = fetch_night_weather_df(date_str)
    if df.empty:
        return "Condizioni meteo non disponibili per la fascia notturna."

    lines = [f"=== Condizioni Meteo Notturne ({date_str} 23:00 - 06:00) ==="]
    for _, row in df.iterrows():
        lines.append(
            f"  • {row['orario']} -> {row['condizioni']} | Temp: {row['temperatura_c']}°C | "
            f"Vento: {row['vento_kmh']} km/h | Pioggia: {row['precipitazioni_mm']} mm"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    print("🧪 Test meteo...")
    summary = get_night_weather_summary(datetime.now().strftime("%Y-%m-%d"))
    print(summary)