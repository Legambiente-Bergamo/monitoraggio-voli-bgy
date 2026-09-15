def check_radar_active():
    """
    Verifica che il file radar si aggiorni durante la finestra notturna.
    v2.3.9: soglia aumentata a 30 min per evitare falsi positivi quando
    non ci sono aerei nell'area.
    """
    now = datetime.now()
    if not (now.hour >= 23 or now.hour < 6):
        return True, "Fuori dalla finestra notturna"

    if now.hour >= 23:
        session = now.strftime("%Y-%m-%d")
    else:
        session = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    radar_file = os.path.join(RAW_DIR, f"bgy_night_flights_{session}.csv")
    if not os.path.exists(radar_file):
        send_alert(
            "radar_missing",
            "⚠️ BGY - File radar notturno mancante",
            f"Nessun file radar per la sessione {session}.\n"
            "Verifica che lo scanner notturno stia girando."
        )
        return False, f"File radar {session} mancante"

    # Soglia aumentata a 30 minuti
    RADAR_STALE_MIN = 30

    mtime = datetime.fromtimestamp(os.path.getmtime(radar_file))
    elapsed_min = (now - mtime).total_seconds() / 60

    if elapsed_min > RADAR_STALE_MIN:
        # Prima di allertare, verifica se il log mostra scansioni recenti
        # (significa che lo scanner gira, ma nessun aereo nell'area)
        log_file = os.path.join(LOGS_DIR, f"bgy_app_{now.strftime('%Y-%m-%d')}.log")
        scanner_working = False
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[-200:]
                # Cerca scansioni negli ultimi 5 minuti
                recent_scans = 0
                for line in lines:
                    if "ScannerNight" in line and "Avvio scansione" in line:
                        try:
                            ts_str = line.split(" - ")[0].strip()
                            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S,%f")
                            if (now - ts).total_seconds() < 300:  # 5 min
                                recent_scans += 1
                        except Exception:
                            continue
                if recent_scans >= 2:
                    scanner_working = True
            except Exception:
                pass

        if scanner_working:
            # Lo scanner gira, semplicemente non ci sono aerei
            return True, (f"File radar fermo da {int(elapsed_min)} min "
                          f"ma scanner attivo (nessun aereo nell'area)")

        send_alert(
            "radar_stale",
            "⚠️ BGY - Radar notturno fermo",
            f"Il file radar non si aggiorna da {int(elapsed_min)} minuti "
            f"e lo scanner sembra non girare.\n"
            "Verifica OpenSky o il loop dello scheduler."
        )
        return False, f"File radar fermo da {int(elapsed_min)} min"

    return True, f"File radar aggiornato {int(elapsed_min)} min fa"