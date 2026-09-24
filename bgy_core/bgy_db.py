"""
bgy_core/bgy_db.py - Modulo di accesso al database PostgreSQL.
Versione 2.5.2
- Fix: execute_query() gestisce correttamente INSERT ... RETURNING
- Fix: execute_query() usa cur.description per capire se la query ritorna righe
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_config_manager import config_manager

logger = get_logger("DB")

SCHEMA_VERSION = 1


SCHEMA_SQL = """
-- Tabella di versioning dello schema
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT NOW(),
    note TEXT
);

-- Metadati delle scansioni SACBO
CREATE TABLE IF NOT EXISTS scans (
    id BIGSERIAL PRIMARY KEY,
    scan_timestamp TIMESTAMP NOT NULL,
    file_name TEXT NOT NULL,
    data_riferimento DATE NOT NULL,
    tipo VARCHAR(10) NOT NULL CHECK (tipo IN ('diurno', 'notturno')),
    righe_importate INTEGER DEFAULT 0,
    imported_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (file_name)
);
CREATE INDEX IF NOT EXISTS idx_scans_data ON scans (data_riferimento);
CREATE INDEX IF NOT EXISTS idx_scans_timestamp ON scans (scan_timestamp);

-- Voli dal tabellone SACBO (raw, tutte le scansioni)
CREATE TABLE IF NOT EXISTS flights_sacbo (
    id BIGSERIAL PRIMARY KEY,
    scan_id BIGINT REFERENCES scans(id) ON DELETE CASCADE,
    callsign_volo TEXT NOT NULL,
    tipo_movimento VARCHAR(2),
    destinazione_origine TEXT,
    orario_schedulato TIME,
    orario_effettivo TIME,
    stato_volo TEXT,
    scan_timestamp TIMESTAMP NOT NULL,
    data_riferimento DATE NOT NULL,
    imported_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_flights_data ON flights_sacbo (data_riferimento);
CREATE INDEX IF NOT EXISTS idx_flights_callsign ON flights_sacbo (callsign_volo);
CREATE INDEX IF NOT EXISTS idx_flights_scan ON flights_sacbo (scan_id);
CREATE INDEX IF NOT EXISTS idx_flights_ts ON flights_sacbo (scan_timestamp);

-- Rilevamenti radar
CREATE TABLE IF NOT EXISTS radar_detections (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    callsign TEXT,
    icao24 TEXT,
    pista TEXT,
    fase_volo TEXT,
    direzione TEXT,
    quota_ft INTEGER,
    rotta_deg REAL,
    distanza_km REAL,
    paese TEXT,
    sessione_notturna DATE NOT NULL,
    imported_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_radar_sessione ON radar_detections (sessione_notturna);
CREATE INDEX IF NOT EXISTS idx_radar_icao ON radar_detections (icao24);
CREATE INDEX IF NOT EXISTS idx_radar_ts ON radar_detections (timestamp);

-- Meteo orario notturno
CREATE TABLE IF NOT EXISTS weather_hourly (
    id BIGSERIAL PRIMARY KEY,
    data_riferimento DATE NOT NULL,
    orario TIME NOT NULL,
    temperatura_c REAL,
    precipitazioni_mm REAL,
    vento_kmh REAL,
    vento_direzione_deg INTEGER,
    condizioni TEXT,
    imported_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (data_riferimento, orario)
);
CREATE INDEX IF NOT EXISTS idx_weather_data ON weather_hourly (data_riferimento);

-- Report notturni (con arricchimento)
CREATE TABLE IF NOT EXISTS nightly_reports (
    id BIGSERIAL PRIMARY KEY,
    data_riferimento DATE NOT NULL,
    callsign TEXT,
    tipo_movimento TEXT,
    is_scheduled BOOLEAN,
    destinazione_finale TEXT,
    stato_destinazione TEXT,
    compagnia_aerea TEXT,
    modello_aereo TEXT,
    orario_schedulato TIME,
    timestamp TIMESTAMP,
    pista TEXT,
    fase_volo TEXT,
    direzione TEXT,
    quota_ft INTEGER,
    rotta_deg REAL,
    distanza_km REAL,
    paese TEXT,
    matched_score INTEGER,
    stima_passeggeri INTEGER,
    stima_rumore_db INTEGER,
    imported_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_nightly_data ON nightly_reports (data_riferimento);
CREATE INDEX IF NOT EXISTS idx_nightly_callsign ON nightly_reports (callsign);
CREATE INDEX IF NOT EXISTS idx_nightly_compagnia ON nightly_reports (compagnia_aerea);

-- Vista: report giornaliero deduplicato
CREATE OR REPLACE VIEW v_daily_report AS
WITH ranked AS (
    SELECT
        f.*,
        ROW_NUMBER() OVER (
            PARTITION BY f.data_riferimento, f.callsign_volo, f.orario_schedulato
            ORDER BY f.scan_timestamp DESC
        ) AS rn
    FROM flights_sacbo f
)
SELECT
    id,
    data_riferimento,
    callsign_volo,
    tipo_movimento,
    destinazione_origine,
    orario_schedulato,
    orario_effettivo,
    stato_volo,
    scan_timestamp
FROM ranked
WHERE rn = 1;
"""


def _db_cfg():
    return config_manager.get_database_config()


def is_enabled():
    cfg = _db_cfg()
    return bool(cfg.get("enabled", False))


def get_connection():
    if not is_enabled():
        return None
    cfg = _db_cfg()
    try:
        import psycopg
        conn = psycopg.connect(
            host=cfg.get("host", "localhost"),
            port=int(cfg.get("port", 5432)),
            dbname=cfg.get("dbname", "bgy_monitoring"),
            user=cfg.get("user", "bgy_user"),
            password=cfg.get("password", ""),
            connect_timeout=int(cfg.get("connect_timeout", 10)),
            application_name=cfg.get("application_name", "BGY Monitoring Suite"),
        )
        return conn
    except Exception as e:
        logger.error(f"Errore connessione DB: {e}")
        return None


def test_connection():
    if not is_enabled():
        return False, "Database disabilitato in configurazione"
    try:
        conn = get_connection()
        if conn is None:
            return False, "Impossibile connettersi al database"
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            row = cur.fetchone()
            pg_version = row[0] if row else "unknown"
        conn.close()
        return True, pg_version
    except Exception as e:
        return False, f"Errore: {e}"


def get_schema_version():
    conn = get_connection()
    if conn is None:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'schema_version'
                )
            """)
            exists = cur.fetchone()[0]
            if not exists:
                return 0
            cur.execute("SELECT MAX(version) FROM schema_version")
            row = cur.fetchone()
            return row[0] if row and row[0] is not None else 0
    except Exception as e:
        logger.error(f"Errore lettura schema_version: {e}")
        return 0
    finally:
        conn.close()


def apply_schema():
    conn = get_connection()
    if conn is None:
        return False, "Impossibile connettersi al database"
    try:
        current = get_schema_version()
        if current >= SCHEMA_VERSION:
            return True, f"Schema già alla versione {current} (corrente: {SCHEMA_VERSION})"

        logger.info(f"Applicazione schema v{SCHEMA_VERSION} (attuale: {current})...")
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
            cur.execute(
                "INSERT INTO schema_version (version, note) VALUES (%s, %s) "
                "ON CONFLICT (version) DO NOTHING",
                (SCHEMA_VERSION, "Schema iniziale BGY Monitoring Suite 2.5")
            )
        conn.commit()
        logger.info(f"✅ Schema v{SCHEMA_VERSION} applicato")
        return True, f"Schema v{SCHEMA_VERSION} applicato"
    except Exception as e:
        conn.rollback()
        logger.error(f"Errore applicazione schema: {e}")
        return False, f"Errore: {e}"
    finally:
        conn.close()


def execute_query(sql, params=None, fetch=True):
    """
    Esegue una query SQL.

    - Se la query ritorna righe (SELECT, INSERT/UPDATE/DELETE ... RETURNING),
      ritorna (True, rows).
    - Altrimenti ritorna (True, rowcount).

    Il commit viene fatto sempre, sia per SELECT che per DML.
    """
    conn = get_connection()
    if conn is None:
        return False, "DB non disponibile"
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())

            has_results = cur.description is not None

            if fetch and has_results:
                rows = cur.fetchall()
                conn.commit()  # commit per chiudere transazione
                return True, rows
            else:
                conn.commit()
                return True, cur.rowcount
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"Errore query: {e}")
        return False, str(e)
    finally:
        conn.close()


def execute_many(sql, params_list):
    conn = get_connection()
    if conn is None:
        return False, "DB non disponibile"
    try:
        with conn.cursor() as cur:
            cur.executemany(sql, params_list)
        conn.commit()
        return True, len(params_list)
    except Exception as e:
        conn.rollback()
        logger.error(f"Errore executemany: {e}")
        return False, str(e)
    finally:
        conn.close()


def get_table_counts():
    tables = [
        "scans", "flights_sacbo", "radar_detections",
        "weather_hourly", "nightly_reports",
    ]
    result = {}
    conn = get_connection()
    if conn is None:
        return result
    try:
        with conn.cursor() as cur:
            for t in tables:
                try:
                    cur.execute(f"SELECT COUNT(1) FROM {t}")
                    result[t] = cur.fetchone()[0]
                except Exception:
                    result[t] = None
        conn.rollback()
        return result
    finally:
        conn.close()


def get_db_size():
    conn = get_connection()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_database_size(current_database())")
            size_bytes = cur.fetchone()[0]
        conn.rollback()
        return round(size_bytes / 1024 / 1024, 2)
    except Exception:
        return None
    finally:
        conn.close()


if __name__ == "__main__":
    print("=== Test bgy_db ===")
    print(f"Abilitato: {is_enabled()}")
    ok, msg = test_connection()
    print(f"Connessione: {'✅' if ok else '❌'} {msg}")
    if ok:
        print(f"Versione schema: {get_schema_version()}")
        print(f"Dimensione DB: {get_db_size()} MB")
        print(f"Tabelle: {get_table_counts()}")