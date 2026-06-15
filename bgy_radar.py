def main():
    # Prende la data passata dal master o usa quella odierna
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    
    print(f"[RADAR] Avvio cattura dati ADS-B in modalità Cloud per il {date_str}...")
    config = load_config()
    
    results_by_fonte = {}
    
    # Fonte 1: OpenSky (Usa le credenziali dell'associazione dal config)
    print("[RADAR] Interrogazione OpenSky Network...")
    results_by_fonte['OpenSky'] = get_opensky_data(config)
    
    # Fonte 2: adsb.fi
    print("[RADAR] Interrogazione adsb.fi...")
    results_by_fonte['adsb.fi'] = get_adsb_fi_data(config)
    
    # Fonte 3: ADS-B Exchange (Solo se le prime fonti hanno dato pochi risultati)
    if len(results_by_fonte['OpenSky']) < 10:
        print("[RADAR] Pochi dati rilevati, interrogazione ADS-B Exchange sussidiaria...")
        results_by_fonte['ADS-B Exchange'] = get_adsb_exchange_data(config)
    
    # Fusione dei tracciati radar ed eliminazione dei duplicati geografici
    merged = merge_results(results_by_fonte)
    
    if merged:
        save_aircraft(merged, date_str, config)
        print(f"[RADAR] ✅ Rilevamento completato. Salvati {len(merged)} tracciati aeromobili.")
    else:
        print("[RADAR] ⚠️ Nessun vettore intercettato nell'area di monitoraggio in questo istante.")

if __name__ == "__main__":
    main()
