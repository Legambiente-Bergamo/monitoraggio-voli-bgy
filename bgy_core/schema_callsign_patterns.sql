-- Tabella di mapping pattern callsign → airline IATA.
-- Usata da bgy_report_night.py per risolvere i callsign operativi
-- (es. MAC455) in voli commerciali (es. 3O455) quando il pattern è noto.
--
-- pattern: prefisso 3-lettere del callsign radar operativo
-- airline_iata: prefisso IATA della compagnia commerciale
-- note: libera
--
-- Regola: il numero commerciale è lo stesso numero del callsign operativo.

CREATE TABLE IF NOT EXISTS callsign_airline_patterns (
    pattern VARCHAR(10) PRIMARY KEY,
    airline_iata VARCHAR(3) NOT NULL,
    note TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO callsign_airline_patterns (pattern, airline_iata, note) VALUES
    ('MAC', '3O', 'Malta Air opera per Air Arabia Maroc'),
    ('MMO', 'MT', 'Malta MedAir'),
    ('FIE', '3F', 'FlyOne Armenia')
ON CONFLICT (pattern) DO NOTHING;