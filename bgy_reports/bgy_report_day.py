"""
bgy_reports/bgy_report_day.py - Generazione report giornaliero dei voli BGY.
Versione 2.5.0
- soglie ritardo/anticipo da config_data.json (report_day)
"""
import os
import pandas as pd
from datetime import datetime

from bgy_core import get_airline, get_country, load_rules, get_logger
from bgy_core.bgy_paths import RAW_DIR, OUTPUT_CSV_DIR
from bgy_core.bgy_dates import normalize_date, report_daily_filename
from bgy_core.bgy_config_manager import config_manager

logger = get_logger("ReportDay")


def calculate_delay_status(sched, eff):
    cfg = config_manager.get_report_day_config()
    delay_th = cfg.get("delay_threshold_min", 15)
    early_th = cfg.get("early_threshold_min", -5)
    wrap = cfg.get("midnight_wrap_min", 1200)

    if pd.isnull(sched) or pd.isnull(eff) or str(sched).strip() in ["", "N/D", "nan"]:
        return 0, "N/D"
    try:
        s_h, s_m = map(int, str(sched).strip().split(":")[:2])
        e_h, e_m = map(int, str(eff).strip().split(":")[:2])
        diff = (e_h * 60 + e_m) - (s_h * 60 + s_m)
        if diff < -wrap:
            diff += 1440
        elif diff > wrap:
            diff -= 1440
        if diff > delay_th:
            return diff, f"Ritardo (+{diff} min)"
        elif diff < early_th:
            return diff, f"In Anticipo ({diff} min)"
        else:
            return diff, "In Orario"
    except (ValueError, AttributeError, TypeError):
        return 0, "N/D"


def find_column(df, possible_names):
    for name in possible_names:
        if name in df.columns:
            return name
    return None


def load_sacbo_files(date_str):
    if not os.path.exists(RAW_DIR):
        return []
    date_norm = normalize_date(date_str) or date_str
    date_clean = date_norm.replace("-", "")

    all_files = []
    for f in os.listdir(RAW_DIR):
        if not f.endswith(".csv"):
            continue
        if f.startswith("report_") or f.startswith("bgy_night_") or f.startswith("radar_"):
            continue
        if f.startswith(f"scan_{date_norm}_") or f.startswith(f"scan_{date_clean}_"):
            all_files.append(os.path.join(RAW_DIR, f))

    if not all_files:
        candidates = [
            os.path.join(RAW_DIR, f) for f in os.listdir(RAW_DIR)
            if f.endswith(".csv") and f.startswith("scan_")
        ]
        candidates.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        all_files = candidates[:3]
        if all_files:
            logger.info(f"📂 Nessun file per {date_norm}, uso gli ultimi {len(all_files)} file")

    return all_files


def generate_daily_report(date_str=None):
    load_rules()

    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    date_norm = normalize_date(date_str)
    if not date_norm:
        logger.error(f"Data non valida: {date_str}")
        return None, f"Data non valida: {date_str}"

    logger.info(f"📊 Avvio generazione report giornaliero per {date_norm}")

    files = load_sacbo_files(date_norm)
    if not files:
        return None, f"Nessun file CSV trovato per {date_norm}"

    try:
        dfs = []
        for f in files:
            if os.path.getsize(f) > 0:
                try:
                    df = pd.read_csv(f)
                    if not df.empty:
                        dfs.append(df)
                        logger.info(f"📄 Caricato: {os.path.basename(f)} - {len(df)} righe")
                except Exception as e:
                    logger.warning(f"Errore lettura {f}: {e}")

        if not dfs:
            return None, "File CSV vuoti"

        combined_df = pd.concat(dfs, ignore_index=True)
        logger.info(f"📊 Combinati {len(dfs)} file, totale {len(combined_df)} righe")

        flight_col = find_column(combined_df, ['volo', 'callsign_volo', 'callsign'])
        sched_col = find_column(combined_df, ['orario_schedulato', 'scheduled_time', 'scheduled'])
        eff_col = find_column(combined_df, ['orario_effettivo', 'actual_time', 'estimated_time'])
        dest_col = find_column(combined_df, ['destinazione_origine', 'destination', 'airport'])
        type_col = find_column(combined_df, ['tipo_movimento', 'tipo', 'type'])

        combined_df['volo'] = combined_df[flight_col] if flight_col else 'N/D'
        combined_df['orario_schedulato'] = combined_df[sched_col] if sched_col else 'N/D'
        combined_df['orario_effettivo'] = combined_df[eff_col] if eff_col else 'N/D'
        combined_df['destinazione_origine'] = combined_df[dest_col] if dest_col else 'N/D'

        if type_col:
            combined_df['tipo_movimento'] = combined_df[type_col].apply(
                lambda x: 'Atterraggio (A)' if str(x).upper() in ['A', 'ATTERRAGGIO', 'ARRIVAL', 'ARR']
                else 'Decollo (D)' if str(x).upper() in ['D', 'DECOLLO', 'DEPARTURE', 'DEP']
                else str(x)
            )
        else:
            combined_df['tipo_movimento'] = 'N/D'

        before = len(combined_df)
        combined_df.drop_duplicates(subset=['volo', 'orario_schedulato'], keep='last', inplace=True)
        if len(combined_df) < before:
            logger.info(f"🗑️ Rimossi {before - len(combined_df)} duplicati")

        combined_df.reset_index(drop=True, inplace=True)

        logger.info("🔍 Arricchimento dati...")
        combined_df['compagnia_aerea'] = combined_df['volo'].apply(get_airline)
        combined_df['stato_destinazione'] = combined_df['destinazione_origine'].apply(get_country)

        delay_info = combined_df.apply(
            lambda r: calculate_delay_status(
                r.get('orario_schedulato'), r.get('orario_effettivo')),
            axis=1
        )
        combined_df['minuti_ritardo'] = [d[0] for d in delay_info]
        combined_df['stato_ritardo'] = [d[1] for d in delay_info]

        os.makedirs(OUTPUT_CSV_DIR, exist_ok=True)
        out_filename = report_daily_filename(date_norm)
        out_path = os.path.join(OUTPUT_CSV_DIR, out_filename)
        combined_df.to_csv(out_path, index=False, encoding="utf-8-sig")

        total = len(combined_df)
        ritardi = len(combined_df[combined_df['minuti_ritardo'] > 15])
        in_orario = len(combined_df[combined_df['stato_ritardo'] == 'In Orario'])

        msg = f"✅ Report generato: {total} voli (Ritardi: {ritardi}, In Orario: {in_orario})"
        logger.info(msg)
        return out_path, msg

    except Exception as e:
        error_msg = f"❌ Errore: {e}"
        logger.error(error_msg)
        return None, error_msg


if __name__ == "__main__":
    path, msg = generate_daily_report()
    print(msg)
    if path:
        print(f"📁 File: {path}")