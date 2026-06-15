def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    
    print(f"[RADAR] Avvio cattura dati ADS-B in modalità Cloud per il {date_str}...")
    config = load_config()
    
    results_by_fonte = {}
    results_by_fonte['OpenSky'] = get_opensky_data(config)
    results_by_fonte['adsb.fi'] = get_adsb_fi_data(config)
    
    if len(results_by_fonte['OpenSky']) < 10:
        results_by_fonte['ADS-B Exchange'] = get_adsb_exchange_data(config)
    
    merged = merge_results(results_by_fonte)
    
    if merged:
        save_aircraft(merged, date_str, config)
        print(f"[RADAR] ✅ Rilevamento completato. Salvati {len(merged)} tracciati aeromobili.")
    else:
        print("[RADAR] ⚠️ Nessun vettore intercettato nell'area di monitoraggio in questo istante.")

if __name__ == "__main__":
    main()
