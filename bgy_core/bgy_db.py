"""
bgy_core/bgy_db.py - Modulo di accesso al database PostgreSQL.
Versione 2.11.1

Novita v2.11.1 (INFRA-21, 19/10/2026):
- SCHEMA_SQL: aggiunta colonna data_calendario alla tabella flights_avionio.
  Allineamento a apply_schema_updates() (che la creava via ALTER).
  Su DB vergine: la colonna ora esiste già alla CREATE.
  Su DB esistente: invariato (già aggiunta da ALTER).
- SCHEMA_VERSION resta 7: la struttura risultante è identica.

Novita v2.11.0 (Cantiere B.2, 19/10/2026):
- SCHEMA_VERSION bumpata da 6 a 7.
- SCHEMA_SQL: aggiunta tabella h24_reports e vista v_h24_report.

Novita v2.10.0 (Cantiere B.1, 14/10/2026):
- SCHEMA_VERSION bumpata da 5 a 6.
- SCHEMA_SQL: aggiunta tabella flights_avionio.

Novita v2.9.0 (BUG-05 / INFRA-07, 13/10/2026):
- SCHEMA_VERSION bumpata da 4 a 5.
- SCHEMA_SQL: aggiunto indice univoco parziale uniq_nightly_flight
  su (data_riferimento, callsign, orario_schedulato) WHERE
  orario_schedulato IS NOT NULL.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_config_manager import config_manager

logger = get_logger("DB")

SCHEMA_VERSION = 7


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

-- Voli scheduled Avionio (Cantiere B.1)
CREATE TABLE IF NOT EXISTS flights_avionio (
    id BIGSERIAL PRIMARY KEY,
    scan_id BIGINT REFERENCES scans(id) ON DELETE CASCADE,
    callsign_volo TEXT NOT NULL,
    tipo_movimento VARCHAR(2),
    destinazione_origine TEXT,
    orario_schedulato TIME,
    orario_effettivo TIME,
    stato_volo TEXT,
    codice_iata VARCHAR(3),
    compagnia_aerea TEXT,
    scan_timestamp TIMESTAMP NOT NULL,
    data_riferimento DATE NOT NULL,
    data_calendario DATE,
    imported_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (data_riferimento, callsign_volo, orario_schedulato, tipo_movimento)
);
CREATE INDEX IF NOT EXISTS idx_avionio_data ON flights_avionio (data_riferimento);
CREATE INDEX IF NOT EXISTS idx_avionio_callsign ON flights_avionio (callsign_volo);
CREATE INDEX IF NOT EXISTS idx_avionio_scan ON flights_avionio (scan_id);
CREATE INDEX IF NOT EXISTS idx_avionio_ts ON flights_avionio (scan_timestamp);

-- Rilevamenti radar (h24 multi-fonte, v2.7.0)
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
    sessione_notturna DATE,
    data_riferimento DATE,
    fonte TEXT,
    timestamp_utc TIMESTAMPTZ,
    imported_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_radar_sessione ON radar_detections (sessione_notturna);
CREATE INDEX IF NOT EXISTS idx_radar_data ON radar_detections (data_riferimento);
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
    direzione_sacbo VARCHAR(2),
    notte_categoria VARCHAR(30),
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

-- v2.9.0 (BUG-05): vincolo univoco sui voli scheduled.
CREATE UNIQUE INDEX IF NOT EXISTS uniq_nightly_flight
ON nightly_reports (data_riferimento, callsign, orario_schedulato)
WHERE orario_schedulato IS NOT NULL;

-- Report H24 multi-fonte (Cantiere B.2)
CREATE TABLE IF NOT EXISTS h24_reports (
    id BIGSERIAL PRIMARY KEY,
    data_riferimento DATE NOT NULL,
    data_calendario DATE NOT NULL,
    callsign TEXT,
    tipo_movimento TEXT,
    direzione_sacbo VARCHAR(2),
    fascia VARCHAR(10),
    categoria VARCHAR(30),
    is_scheduled BOOLEAN,
    fonte_scheduled VARCHAR(10),
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
    icao24 VARCHAR(6),
    stima_passeggeri INTEGER,
    stima_rumore_db INTEGER,
    logic_version VARCHAR(20),
    imported_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_h24_calendario ON h24_reports (data_calendario);
CREATE INDEX IF NOT EXISTS idx_h24_riferimento ON h24_reports (data_riferimento);
CREATE INDEX IF NOT EXISTS idx_h24_callsign ON h24_reports (callsign);

-- Viste
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
    id, data_riferimento, callsign_volo, tipo_movimento, destinazione_origine,
    orario_schedulato, orario_effettivo, stato_volo, scan_timestamp
FROM ranked
WHERE rn = 1;

CREATE OR REPLACE VIEW v_h24_report AS
SELECT
    data_calendario AS data,
    callsign,
    tipo_movimento,
    direzione_sacbo,
    categoria AS notte_categoria,
    is_scheduled,
    fonte_scheduled,
    destinazione_finale,
    compagnia_aerea,
    modello_aereo,
    orario_schedulato,
    timestamp,
    pista,
    fase_volo,
    quota_ft,
    distanza_km,
    matched_score,
    icao24,
    stima_passeggeri,
    stima_rumore_db,
    EXTRACT(HOUR FROM timestamp)::int AS ora_effettiva
FROM h24_reports;
"""


def _db_cfg():
    return config_manager.get_database_config()


def is_enabled():
    return bool(_db_cfg().get("enabled", False))


def get_connection():
    if not is_enabled():
        return None
    cfg = _db_cfg()
    try:
        import psycopg
        return psycopg.connect(
            host=cfg.get("host", "localhost"),
            port=int(cfg.get("port", 5432)),
            dbname=cfg.get("dbname", "bgy_monitoring"),
            user=cfg.get("user", "bgy_user"),
            password=cfg.get("password", ""),
            connect_timeout=int(cfg.get("connect_timeout", 10)),
            application_name=cfg.get("application_name", "BGY Monitoring Suite"),
        )
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
        conn.close()
        return True, row[0] if row else "unknown"
    except Exception as e:
        return False, f"Errore: {e}"


def get_schema_version():
    conn = get_connection()
    if conn is None:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'schema_version')")
            if not cur.fetchone()[0]:
                return 0
            cur.execute("SELECT MAX(version) FROM schema_version")
            row = cur.fetchone()
            return row[0] if row and row[0] is not None else 0
    except Exception:
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
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
            cur.execute(
                "INSERT INTO schema_version (version, note) VALUES (%s, %s) ON CONFLICT (version) DO NOTHING",
                (SCHEMA_VERSION, "Schema BGY Monitoring Suite 2.11 (B.2: h24_reports + v_h24_report)")
            )
        conn.commit()
        return True, f"Schema v{SCHEMA_VERSION} applicato"
    except Exception as e:
        conn.rollback()
        return False, f"Errore: {e}"
    finally:
        conn.close()


def execute_query(sql, params=None, fetch=True):
    conn = get_connection()
    if conn is None:
        return False, "DB non disponibile"
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            has_results = cur.description is not None
            if fetch and has_results:
                rows = cur.fetchall()
                conn.commit()
                return True, rows
            else:
                conn.commit()
                return True, cur.rowcount
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
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
            total_rowcount = cur.rowcount
        conn.commit()
        return True, total_rowcount
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def get_table_counts():
    tables = [
        "scans", "flights_sacbo", "flights_avionio",
        "radar_detections", "weather_hourly", "nightly_reports", "h24_reports"
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
    print(f"Connessione: {'OK' if ok else 'KO'} {msg}")
    if ok:
        print(f"Versione schema: {get_schema_version()}")
        print(f"Tabelle: {get_table_counts()}")