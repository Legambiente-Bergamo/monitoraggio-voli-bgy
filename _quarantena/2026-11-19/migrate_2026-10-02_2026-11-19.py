"""
Migrazione anagrafica compagnie - 2026-10-02
- SRR: Star Air -> Maersk Air Cargo, is_cargo=True
- DJ: nuova entry Maersk Air Cargo, is_cargo=True
- LAV, AP: AlbaStar, is_charter=True
- Nuova tabella callsign_classifications (override per callsign)
"""
from bgy_core import bgy_db

def q(sql, params=None):
    ok, res = bgy_db.execute_query(sql, params, fetch=False)
    if not ok:
        print(f"  ERRORE: {res}")
    return ok

print("=== 1. Aggiornamento SRR (Star Air -> Maersk Air Cargo) ===")
ok = q("""
    UPDATE airlines
    SET name = 'Maersk Air Cargo', is_cargo = TRUE, is_charter = FALSE,
        updated_at = NOW()
    WHERE code = 'SRR'
""")
print(f"  {'OK' if ok else 'KO'}")

print("=== 2. Inserimento/aggiornamento DJ (Maersk Air Cargo) ===")
ok = q("""
    INSERT INTO airlines (code, name, is_cargo, is_charter, source)
    VALUES ('DJ', 'Maersk Air Cargo', TRUE, FALSE, 'config')
    ON CONFLICT (code) DO UPDATE
    SET name = 'Maersk Air Cargo', is_cargo = TRUE, is_charter = FALSE,
        updated_at = NOW()
""")
print(f"  {'OK' if ok else 'KO'}")

print("=== 3. Aggiornamento LAV e AP (AlbaStar charter) ===")
for code in ('LAV', 'AP'):
    ok = q("""
        UPDATE airlines
        SET name = 'AlbaStar', is_charter = TRUE, is_cargo = FALSE,
            updated_at = NOW()
        WHERE code = %s
    """, (code,))
    print(f"  {code}: {'OK' if ok else 'KO'}")

print("=== 4. Creazione tabella callsign_classifications ===")
ok = q("""
    CREATE TABLE IF NOT EXISTS callsign_classifications (
        callsign VARCHAR(10) PRIMARY KEY,
        categoria VARCHAR(30) NOT NULL,
        nome_compagnia VARCHAR(100),
        note TEXT,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    )
""")
print(f"  {'OK' if ok else 'KO'}")

print()
print("=== Verifica finale ===")
ok, rows = bgy_db.execute_query(
    "SELECT code, name, is_cargo, is_charter FROM airlines "
    "WHERE code IN ('SRR', 'DJ', 'LAV', 'AP') ORDER BY code"
)
if ok:
    for r in rows:
        print(f"  {r[0]:4s} | {r[1]:20s} | cargo={r[2]} | charter={r[3]}")
else:
    print(f"  Errore: {rows}")

ok, rows = bgy_db.execute_query(
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'callsign_classifications'"
)
if ok and rows:
    print(f"\n  Tabella callsign_classifications: {'creata' if rows[0][0] == 1 else 'NON creata'}")
