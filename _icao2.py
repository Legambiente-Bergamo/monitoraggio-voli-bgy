from bgy_core import bgy_db

print("=== icao24 dei radar-only (sessione 02/10, decolli 03/10) ===\n")
ok, rows = bgy_db.execute_query("""
    SELECT DISTINCT callsign, icao24
    FROM radar_detections
    WHERE data_riferimento IN ('2026-10-02', '2026-10-03')
      AND callsign IN ('RYR79WD','RYR2DL','RYR13PK','RYR1WF','RYR7HH','WZZ6579','RYR1KW')
    ORDER BY callsign
""")
print("Radar-only:")
for r in rows or []:
    print(f"  {r[0]:10s}  icao={r[1]}")

print()
print("=== icao24 di tutti i radar RYR/WZZ/WMT dalle 00:00 alle 00:50 del 03/10 ===")
print()
ok, rows = bgy_db.execute_query("""
    SELECT callsign, icao24, timestamp, fase_volo
    FROM radar_detections
    WHERE data_riferimento = '2026-10-03'
      AND timestamp::time BETWEEN '00:00' AND '00:50'
      AND (callsign LIKE 'RYR%%' OR callsign LIKE 'W%%' OR callsign LIKE 'MAC%%' OR callsign LIKE 'MMO%%')
    ORDER BY timestamp
""")
for r in rows or []:
    print(f"  {r[0]:10s}  icao={r[1]}  {r[2]}  {r[3]}")

print()
print("=== icao24 4cad39: tutti i radar ===")
print()
ok, rows = bgy_db.execute_query("""
    SELECT callsign, icao24, timestamp, fase_volo, data_riferimento
    FROM radar_detections
    WHERE icao24 = '4cad39'
      AND data_riferimento IN ('2026-10-02', '2026-10-03')
    ORDER BY timestamp
""")
for r in rows or []:
    print(f"  {r[0]:10s}  {r[2]}  {r[3]}  (data {r[4]})")

print()
print("=== icao24 48c123: tutti i radar (RYR79WD) ===")
print()
ok, rows = bgy_db.execute_query("""
    SELECT callsign, icao24, timestamp, fase_volo, data_riferimento
    FROM radar_detections
    WHERE icao24 = '48c123'
      AND data_riferimento IN ('2026-10-02', '2026-10-03')
    ORDER BY timestamp
""")
for r in rows or []:
    print(f"  {r[0]:10s}  {r[2]}  {r[3]}  (data {r[4]})")