-- =============================================================================
-- BGY Monitoring Suite - Schema anagrafiche (F12a)
-- =============================================================================

CREATE TABLE IF NOT EXISTS airlines (
    code         VARCHAR(10) PRIMARY KEY,
    name         VARCHAR(200) NOT NULL,
    is_cargo     BOOLEAN DEFAULT FALSE,
    is_charter   BOOLEAN DEFAULT FALSE,
    source       VARCHAR(20) DEFAULT 'config',
    created_at   TIMESTAMP DEFAULT NOW(),
    updated_at   TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_airlines_name ON airlines (name);
CREATE INDEX IF NOT EXISTS idx_airlines_flags ON airlines (is_cargo, is_charter);

CREATE TABLE IF NOT EXISTS iata_to_icao (
    iata       VARCHAR(3) PRIMARY KEY,
    icao       VARCHAR(4) NOT NULL
);

CREATE TABLE IF NOT EXISTS countries (
    destination  VARCHAR(200) PRIMARY KEY,
    country      VARCHAR(100) NOT NULL,
    updated_at   TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_countries_country ON countries (country);

CREATE TABLE IF NOT EXISTS aircraft_models (
    model          VARCHAR(100) PRIMARY KEY,
    seats_2class   INTEGER,
    seats_max      INTEGER,
    seats_default  INTEGER,
    updated_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS aircraft_by_code (
    code   VARCHAR(10) PRIMARY KEY,
    model  VARCHAR(100) REFERENCES aircraft_models(model) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS load_factors (
    code         VARCHAR(10) PRIMARY KEY,
    load_factor  NUMERIC(4,3) NOT NULL
);

CREATE TABLE IF NOT EXISTS noise_stations (
    name  VARCHAR(200) PRIMARY KEY,
    lat   NUMERIC(10,6),
    lon   NUMERIC(10,6)
);

CREATE TABLE IF NOT EXISTS noise_curves (
    id              SERIAL PRIMARY KEY,
    aircraft_model  VARCHAR(100) NOT NULL,
    phase           VARCHAR(50) NOT NULL,
    distance_m      INTEGER NOT NULL,
    noise_db        NUMERIC(5,1) NOT NULL,
    UNIQUE (aircraft_model, phase, distance_m)
);
CREATE INDEX IF NOT EXISTS idx_noise_curves_model ON noise_curves (aircraft_model);

CREATE TABLE IF NOT EXISTS alert_messages (
    key         VARCHAR(50) PRIMARY KEY,
    subject     VARCHAR(300),
    body        TEXT,
    updated_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS assaeroporti_stats (
    year         INTEGER PRIMARY KEY,
    passengers   BIGINT,
    movements    INTEGER,
    cargo_ton    INTEGER,
    source       VARCHAR(50),
    updated_at   TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS config_settings (
    key         VARCHAR(100) PRIMARY KEY,
    value       TEXT,
    updated_at  TIMESTAMP DEFAULT NOW()
);