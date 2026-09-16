"""
bgy_core/bgy_dates.py - Gestione unificata date, orari e nomi file.
Versione 2.5

REGOLE DI NAMING (unico punto di verità):
  - Rilevazioni raw:              YYYY-MM-DD_HH-MM   (scan_*, radar_*)
  - Report elaborati giornalieri: YYYY-MM-DD         (report_daily_*, report_nightly_*)
  - Report mensili:               YYYY-MM            (report_monthly_*_YYYY-MM.csv)
  - Report annuali:               YYYY               (report_yearly_*_YYYY.csv)
  - GUI (input/output):           DD/MM/YYYY, MM/YYYY, YYYY

SEMANTICA DI GIORNO E NOTTE:
  - Giorno: 00:00 - 23:59 dello stesso giorno
  - Notte:  23:00 del giorno X  ->  05:59 del giorno X+1
  - La "data di sessione notturna" è quella del giorno di INIZIO (X).
"""
import re
from datetime import datetime, date, timedelta

# --- Soglie notturne ---
NIGHT_START_HOUR = 23
NIGHT_END_HOUR = 6

# --- Formati interni ---
FMT_RAW = "%Y-%m-%d_%H-%M"      # scan_2026-09-15_06-00
FMT_DATE = "%Y-%m-%d"           # 2026-09-15
FMT_MONTH = "%Y-%m"             # 2026-09
FMT_YEAR = "%Y"                 # 2026

# --- Formati GUI ---
FMT_GUI_DATE = "%d/%m/%Y"       # 15/09/2026
FMT_GUI_MONTH = "%m/%Y"         # 09/2026
FMT_GUI_YEAR = "%Y"             # 2026


# =============================================================================
# NORMALIZZAZIONE INPUT (accetta vari formati, ritorna sempre 'YYYY-MM-DD')
# =============================================================================

def normalize_date(date_str):
    """
    Normalizza una data da formato vario a 'YYYY-MM-DD'.
    Accetta: YYYY-MM-DD, YYYYMMDD, DD/MM/YYYY, DD-MM-YYYY.
    Ritorna None se non riconosce il formato.
    """
    if date_str is None:
        return None
    s = str(date_str).strip()
    if not s:
        return None

    # Già YYYY-MM-DD
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    # YYYYMMDD
    if re.fullmatch(r"\d{8}", s):
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    # DD/MM/YYYY o DD-MM-YYYY
    m = re.fullmatch(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", s)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
    return None


def to_compact(date_str):
    """'YYYY-MM-DD' -> 'YYYYMMDD'. Ritorna None se input non valido."""
    n = normalize_date(date_str)
    if not n:
        return None
    return n.replace("-", "")


def from_compact(compact):
    """'YYYYMMDD' -> 'YYYY-MM-DD'. Ritorna None se input non valido."""
    if compact is None:
        return None
    s = str(compact).strip()
    if not re.fullmatch(r"\d{8}", s):
        return None
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def to_year_month(date_str):
    """'YYYY-MM-DD' -> 'YYYY-MM'. Ritorna None se non valido."""
    n = normalize_date(date_str)
    if not n:
        return None
    return n[:7]


def to_year(date_str):
    """'YYYY-MM-DD' -> 'YYYY'. Ritorna None se non valido."""
    n = normalize_date(date_str)
    if not n:
        return None
    return n[:4]


# =============================================================================
# CONVERSIONE VERSO GUI (input/output utente)
# =============================================================================

def format_gui_date(d):
    """date/datetime -> 'DD/MM/YYYY'."""
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime(FMT_GUI_DATE)


def format_gui_month(d):
    """date/datetime -> 'MM/YYYY'."""
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime(FMT_GUI_MONTH)


def format_gui_year(d):
    """date/datetime/int -> 'YYYY'."""
    if isinstance(d, int):
        return f"{d:04d}"
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime(FMT_GUI_YEAR)


def parse_gui_date(s):
    """'DD/MM/YYYY' -> date. Ritorna None se non valido."""
    if not s:
        return None
    try:
        return datetime.strptime(str(s).strip(), FMT_GUI_DATE).date()
    except ValueError:
        return None


def parse_gui_month(s):
    """'MM/YYYY' -> (year, month). Ritorna None se non valido."""
    if not s:
        return None
    try:
        dt = datetime.strptime(str(s).strip(), FMT_GUI_MONTH)
        return (dt.year, dt.month)
    except ValueError:
        return None


def parse_gui_year(s):
    """'YYYY' -> int. Ritorna None se non valido."""
    if not s:
        return None
    s = str(s).strip()
    if re.fullmatch(r"\d{4}", s):
        return int(s)
    return None


# =============================================================================
# SEMANTICA GIORNO / NOTTE
# =============================================================================

def is_night_time(dt=None):
    """True se dt è nella fascia notturna (23:00-05:59)."""
    if dt is None:
        dt = datetime.now()
    return dt.hour >= NIGHT_START_HOUR or dt.hour < NIGHT_END_HOUR


def night_session_date(dt=None):
    """
    Ritorna la data (stringa 'YYYY-MM-DD') della sessione notturna a cui
    appartiene dt.
      - Se dt è tra 23:00 e 23:59: sessione iniziata OGGI.
      - Se dt è tra 00:00 e 05:59: sessione iniziata IERI.
      - Altrimenti: ritorna la data di dt (fuori finestra notturna).
    """
    if dt is None:
        dt = datetime.now()
    if dt.hour >= NIGHT_START_HOUR:
        return dt.strftime(FMT_DATE)
    if dt.hour < NIGHT_END_HOUR:
        return (dt - timedelta(days=1)).strftime(FMT_DATE)
    return dt.strftime(FMT_DATE)


def night_window(session_date_str):
    """
    Data una data di sessione notturna 'YYYY-MM-DD', ritorna
    (datetime_inizio, datetime_fine) = (X 23:00, X+1 05:59).
    """
    n = normalize_date(session_date_str)
    if not n:
        return None, None
    start = datetime.strptime(n + " 23:00", "%Y-%m-%d %H:%M")
    end_date = (datetime.strptime(n, FMT_DATE) + timedelta(days=1)).strftime(FMT_DATE)
    end = datetime.strptime(end_date + " 05:59", "%Y-%m-%d %H:%M")
    return start, end


def belongs_to_night_session(hhmm_str, session_date_str):
    """
    Verifica se un orario 'HH:MM' appartiene alla sessione notturna
    identificata da session_date_str ('YYYY-MM-DD').
      - 23:00-23:59 appartiene alla sessione del giorno stesso
      - 00:00-05:59 appartiene alla sessione del giorno precedente
    """
    try:
        hh, mm = map(int, str(hhmm_str).strip().split(":")[:2])
    except (ValueError, AttributeError):
        return False
    n = normalize_date(session_date_str)
    if not n:
        return False
    session_day = datetime.strptime(n, FMT_DATE).date()
    # Se l'orario è nella fascia 23:00-23:59, deve appartenere al giorno stesso
    if hh >= NIGHT_START_HOUR:
        # verifichiamo che il giorno sia coerente: prendiamo il giorno
        # di session_date e confrontiamo l'orario
        return True
    if hh < NIGHT_END_HOUR:
        # l'orario è nel giorno successivo, appartiene alla sessione del giorno prima
        return True
    return False


# =============================================================================
# COSTRUZIONE NOMI FILE
# =============================================================================

def scan_filename(dt=None):
    """
    Nome file per una scansione SACBO.
    Formato: 'scan_YYYY-MM-DD_HH-MM.csv'
    """
    if dt is None:
        dt = datetime.now()
    return f"scan_{dt.strftime(FMT_RAW)}.csv"


def radar_filename(session_date_str):
    """
    Nome file per il file radar cumulativo di una sessione notturna.
    Formato: 'radar_YYYY-MM-DD.csv'
    La data è quella di INIZIO sessione.
    """
    n = normalize_date(session_date_str)
    if not n:
        return None
    return f"radar_{n}.csv"


def report_daily_filename(date_str):
    """'report_daily_YYYY-MM-DD.csv'"""
    n = normalize_date(date_str)
    if not n:
        return None
    return f"report_daily_{n}.csv"


def report_nightly_filename(session_date_str):
    """'report_nightly_YYYY-MM-DD.csv' (data di inizio sessione)."""
    n = normalize_date(session_date_str)
    if not n:
        return None
    return f"report_nightly_{n}.csv"


def report_monthly_filename(year_month, kind="daily"):
    """
    'report_monthly_daily_YYYY-MM.csv' o
    'report_monthly_nightly_YYYY-MM.csv'
    year_month: 'YYYY-MM' o (year, month).
    """
    if isinstance(year_month, tuple) and len(year_month) == 2:
        y, m = year_month
        ym = f"{y:04d}-{m:02d}"
    else:
        ym = str(year_month).strip()
        if not re.fullmatch(r"\d{4}-\d{2}", ym):
            # prova a normalizzare da 'YYYYMM'
            if re.fullmatch(r"\d{6}", ym):
                ym = f"{ym[:4]}-{ym[4:6]}"
            else:
                return None
    kind = kind if kind in ("daily", "nightly") else "daily"
    return f"report_monthly_{kind}_{ym}.csv"


def report_yearly_filename(year, kind="daily"):
    """'report_yearly_daily_YYYY.csv' o 'report_yearly_nightly_YYYY.csv'."""
    y = str(year).strip()
    if not re.fullmatch(r"\d{4}", y):
        return None
    kind = kind if kind in ("daily", "nightly") else "daily"
    return f"report_yearly_{kind}_{y}.csv"


# =============================================================================
# PARSING NOMI FILE (per migrazione e doppia lettura)
# =============================================================================

def parse_scan_filename(filename):
    """
    Estrae datetime da 'scan_YYYY-MM-DD_HH-MM.csv'.
    Accetta anche il vecchio formato 'scan_YYYYMMDD_HHMM.csv'.
    Ritorna datetime o None.
    """
    if not filename:
        return None
    base = filename.replace(".csv", "")
    # nuovo formato
    m = re.fullmatch(r"scan_(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2})", base)
    if m:
        try:
            return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H-%M")
        except ValueError:
            return None
    # vecchio formato
    m = re.fullmatch(r"scan_(\d{8})_(\d{4})", base)
    if m:
        try:
            return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y%m%d %H%M")
        except ValueError:
            return None
    return None


def parse_radar_filename(filename):
    """
    Estrae la data di sessione da 'radar_YYYY-MM-DD.csv' o dal vecchio
    'bgy_night_flights_YYYY-MM-DD.csv'.
    Ritorna 'YYYY-MM-DD' o None.
    """
    if not filename:
        return None
    base = filename.replace(".csv", "")
    m = re.fullmatch(r"radar_(\d{4}-\d{2}-\d{2})", base)
    if m:
        return m.group(1)
    m = re.fullmatch(r"bgy_night_flights_(\d{4}-\d{2}-\d{2})", base)
    if m:
        return m.group(1)
    return None


def parse_report_daily_filename(filename):
    """'report_daily_YYYY-MM-DD.csv' o vecchio 'report_daily_YYYYMMDD.csv'."""
    if not filename:
        return None
    base = filename.replace(".csv", "")
    m = re.fullmatch(r"report_daily_(\d{4}-\d{2}-\d{2})", base)
    if m:
        return m.group(1)
    m = re.fullmatch(r"report_daily_(\d{8})", base)
    if m:
        return from_compact(m.group(1))
    return None


def parse_report_nightly_filename(filename):
    """'report_nightly_YYYY-MM-DD.csv' o vecchio 'report_nightly_YYYYMMDD.csv'."""
    if not filename:
        return None
    base = filename.replace(".csv", "")
    m = re.fullmatch(r"report_nightly_(\d{4}-\d{2}-\d{2})", base)
    if m:
        return m.group(1)
    m = re.fullmatch(r"report_nightly_(\d{8})", base)
    if m:
        return from_compact(m.group(1))
    return None


# =============================================================================
# UTILITY
# =============================================================================

def today_str():
    """Data odierna in formato 'YYYY-MM-DD'."""
    return datetime.now().strftime(FMT_DATE)


def yesterday_str():
    """Data di ieri in formato 'YYYY-MM-DD'."""
    return (datetime.now() - timedelta(days=1)).strftime(FMT_DATE)


def now_str():
    """Data e ora attuali in formato 'YYYY-MM-DD HH:MM:SS'."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    # Test rapido
    print("=== Test bgy_dates ===")
    print(f"now:                {now_str()}")
    print(f"today:              {today_str()}")
    print(f"yesterday:          {yesterday_str()}")
    print()
    print(f"is_night_time(02:00): {is_night_time(datetime(2026, 9, 16, 2, 0))}")
    print(f"is_night_time(12:00): {is_night_time(datetime(2026, 9, 16, 12, 0))}")
    print()
    print(f"night_session_date(2026-09-15 23:30): "
          f"{night_session_date(datetime(2026, 9, 15, 23, 30))}")
    print(f"night_session_date(2026-09-16 02:00): "
          f"{night_session_date(datetime(2026, 9, 16, 2, 0))}")
    print()
    start, end = night_window("2026-09-15")
    print(f"night_window(2026-09-15): {start} -> {end}")
    print()
    print(f"scan_filename:              {scan_filename(datetime(2026, 9, 15, 6, 0))}")
    print(f"radar_filename:             {radar_filename('2026-09-15')}")
    print(f"report_daily_filename:      {report_daily_filename('2026-09-15')}")
    print(f"report_nightly_filename:    {report_nightly_filename('2026-09-15')}")
    print(f"report_monthly_filename:    {report_monthly_filename('2026-09')}")
    print(f"report_yearly_filename:     {report_yearly_filename('2026')}")
    print()
    print(f"normalize_date('2026-09-15'): {normalize_date('2026-09-15')}")
    print(f"normalize_date('20260915'):   {normalize_date('20260915')}")
    print(f"normalize_date('15/09/2026'): {normalize_date('15/09/2026')}")
    print(f"to_compact('2026-09-15'):     {to_compact('2026-09-15')}")
    print()
    print(f"format_gui_date:  {format_gui_date(date(2026, 9, 15))}")
    print(f"format_gui_month: {format_gui_month(date(2026, 9, 15))}")
    print(f"format_gui_year:  {format_gui_year(date(2026, 9, 15))}")
    print()
    print(f"parse_scan_filename('scan_2026-09-15_06-00.csv'): "
          f"{parse_scan_filename('scan_2026-09-15_06-00.csv')}")
    print(f"parse_scan_filename('scan_20260915_0600.csv'): "
          f"{parse_scan_filename('scan_20260915_0600.csv')}")
    print(f"parse_radar_filename('bgy_night_flights_2026-09-15.csv'): "
          f"{parse_radar_filename('bgy_night_flights_2026-09-15.csv')}")