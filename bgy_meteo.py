def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    
    print(f"[METEO] Richiesta bollettino METAR per aeroporto LIME (BGY) il {date_str}...")
    
    # Scarica l'ultimo bollettino meteorologico ufficiale disponibile
    metar_data = get_metar()
    
    if metar_data:
        save_metar(metar_data, date_str)
        print(f"[METEO] ✅ Analisi vento completata. Direzione: {metar_data['wind_direction']}° - Pista teorica calcolata: {metar_data['active_runway']}")
    else:
        print("[METEO] ⚠️ Impossibile recuperare i dati meteo di Orio al Serio dai server NOAA.")

if __name__ == "__main__":
    main()
