def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    log_message(f"Script attivato in modalità Cloud per la giornata: {date_str}")
    
    try:
        capture_flights_and_screenshots(date_str)
    except Exception as e:
        log_message(f"⚠️ Errore nel ciclo di esecuzione: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
