"""Check contenuto nightly_reports per una data."""
from bgy_core import bgy_db

date_str = '2026-09-15'

print("=" * 70)
print(f"CHECK nightly_reports per {date_str}")
print("=" * 70)

# 1. Totale
ok, r = bgy_db.execute_query(
    "SELECT COUNT(1) FROM nightly_reports WHERE data_riferimento = %s",
    (date_str,)
)
print(f"\nTotale righe in nightly_reports: {r[0][0]}")

# 2. Per fase_volo
print("\n--- Conteggio per fase_volo ---")
ok, r = bgy_db.execute_query(
    "SELECT fase_volo, COUNT(1) FROM nightly_reports "
    "WHERE data_riferimento = %s GROUP BY 1 ORDER BY 2 DESC",
    (date_str,)
)
for row in r:
    print(f"  {row[0]!r}: {row[1]}")

# 3. Per tipo_movimento
print("\n--- Conteggio per tipo_movimento ---")
ok, r = bgy_db.execute_query(
    "SELECT tipo_movimento, COUNT(1) FROM nightly_reports "
    "WHERE data_riferimento = %s GROUP BY 1 ORDER BY 2 DESC",
    (date_str,)
)
for row in r:
    print(f"  {row[0]!r}: {row[1]}")

# 4. Per compagnia
print("\n--- Conteggio per compagnia_aerea ---")
ok, r = bgy_db.execute_query(
    "SELECT compagnia_aerea, COUNT(1) FROM nightly_reports "
    "WHERE data_riferimento = %s GROUP BY 1 ORDER BY 2 DESC LIMIT 15",
    (date_str,)
)
for row in r:
    print(f"  {row[0]!r}: {row[1]}")

# 5. Solo atterraggi/decolli/avvicinamenti (esclusi sorvoli)
print("\n--- Solo atterraggi/decolli/avvicinamenti ---")
ok, r = bgy_db.execute_query(
    "SELECT fase_volo, COUNT(1) FROM nightly_reports "
    "WHERE data_riferimento = %s "
    "AND fase_volo IN ('Atterraggio', 'Decollo', 'Avvicinamento') "
    "GROUP BY 1 ORDER BY 2 DESC",
    (date_str,)
)
for row in r:
    print(f"  {row[0]!r}: {row[1]}")

# 6. Ryanair: record vs callsign distinti
print("\n--- Ryanair: record vs callsign distinti ---")
ok, r = bgy_db.execute_query(
    "SELECT COUNT(1) AS n_records, COUNT(DISTINCT callsign) AS n_callsign "
    "FROM nightly_reports "
    "WHERE data_riferimento = %s "
    "AND compagnia_aerea = %s",
    (date_str, "Ryanair")
)
if ok and r:
    print(f"  Record: {r[0][0]}, Callsign distinti: {r[0][1]}")

# 7. Elenco callsign Ryanair
print("\n--- Elenco callsign Ryanair ---")
ok, r = bgy_db.execute_query(
    "SELECT DISTINCT callsign FROM nightly_reports "
    "WHERE data_riferimento = %s AND compagnia_aerea = %s "
    "ORDER BY callsign",
    (date_str, "Ryanair")
)
if ok:
    for row in r:
        print(f"  {row[0]!r}")

# 8. Prime 15 righe Ryanair
print("\n--- Prime 15 righe Ryanair ---")
ok, r = bgy_db.execute_query(
    "SELECT callsign, fase_volo, orario_schedulato, timestamp, "
    "pista, distanza_km, matched_score "
    "FROM nightly_reports "
    "WHERE data_riferimento = %s AND compagnia_aerea = %s "
    "ORDER BY callsign LIMIT 15",
    (date_str, "Ryanair")
)
for row in r:
    print(f"  callsign={row[0]!r}, fase={row[1]!r}, "
          f"sched={row[2]!r}, ts={row[3]!r}, "
          f"pista={row[4]!r}, dist={row[5]}, score={row[6]}")

# 9. Voli schedulati (SACBO) per il 15/09 (dal tabellone)
print("\n--- Voli schedulati SACBO per il 15/09 (solo notturni, 23:00-05:59) ---")
ok, r = bgy_db.execute_query(
    "SELECT COUNT(1) FROM flights_sacbo "
    "WHERE data_riferimento = %s "
    "AND (orario_schedulato >= '23:00' OR orario_schedulato < '06:00')",
    (date_str,)
)
if ok and r:
    print(f"  Voli schedulati notturni: {r[0][0]}")

# 10. Rilevamenti radar per il 15/09
print("\n--- Rilevamenti radar per il 15/09 ---")
ok, r = bgy_db.execute_query(
    "SELECT COUNT(1) FROM radar_detections "
    "WHERE sessione_notturna = %s",
    (date_str,)
)
if ok and r:
    print(f"  Rilevamenti radar: {r[0][0]}")

# 11. Radar per fase_volo
print("\n--- Radar: conteggio per fase_volo ---")
ok, r = bgy_db.execute_query(
    "SELECT fase_volo, COUNT(1) FROM radar_detections "
    "WHERE sessione_notturna = %s GROUP BY 1 ORDER BY 2 DESC",
    (date_str,)
)
for row in r:
    print(f"  {row[0]!r}: {row[1]}")

# 12. Radar: callsign distinti
print("\n--- Radar: callsign distinti ---")
ok, r = bgy_db.execute_query(
    "SELECT COUNT(1) AS total, COUNT(DISTINCT callsign) AS distinti "
    "FROM radar_detections WHERE sessione_notturna = %s",
    (date_str,)
)
if ok and r:
    print(f"  Record radar: {r[0][0]}, Callsign distinti: {r[0][1]}")