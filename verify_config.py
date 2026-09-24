from bgy_core import config_manager

print("✅ config_manager OK")
a = config_manager.get_airlines()
n_pax = len([k for k in a if not k.startswith("_")])
print(f"   Compagnie: {n_pax}")
print(f"   Cargo: {len(a.get('_cargo_airlines', {}))}")
print(f"   Charter: {len(a.get('_charter_airlines', {}))}")
print(f"   IATA→ICAO: {len(a.get('_iata_to_icao', {}))}")

c = config_manager.get_countries()
print(f"   Paesi: {len(c)}")

m = config_manager.get_aircraft_models()
print(f"   Modelli: {len(m.get('_seats', {}))}")

n = config_manager.get_noise_impact()
print(f"   Centraline: {len(n.get('_stations', {}))}")
print(f"   Curve NPD: {len(n.get('_curves', {}))}")