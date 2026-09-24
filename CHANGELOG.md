# Changelog — BGY Monitoring Suite

Tutte le modifiche significative del progetto sono documentate in questo file.
Formato basato su [Keep a Changelog](https://keepachangelog.com/it/1.0.0/).

## [2.9.0] — 2026-09-24

### Aggiunto
- Tab GUI "🔔 Notifiche" con flag silenziamento (master, alerts, daily)
- Statistiche movimenti giorno/notte nell'email di stato 06:30 (F18b)
- Gradiente azzurro header email (F18c)
- 27 check di qualità dati (da 10 originali) con logica `reference_date` (F11e)
- Schema DB per anagrafiche: 11 nuove tabelle (F12a)
- `bgy_core/schema_anagrafiche.sql`

### Modificato
- **Migrazione JSON → PostgreSQL**: anagrafiche (airlines, countries, aircraft, noise, alert, assaeroporti) ora in DB (F12a)
- `bgy_config_manager.py` v3.0.0: legge le anagrafiche dal DB
- `bgy_mailer.py` v2.5.4: gestione flag silenziamento + statistiche
- `bgy_scheduler.py` v2.5.7: raccolta statistiche per email
- `bgy_report_night.py` v2.8.5: colonna `direzione_sacbo` (D/A)
- `bgy_scanner_day.py` v2.5.1: cattura arrivi (fix click tab)
- `bgy_watchdog.py` v2.5.4: grace period radar + no falsi allarmi
- `bgy_db_migrate.py` v2.6.2: 27 check + stats + fix bug

### Corretto
- Watchdog: falsi allarmi "radar mancante" alle 23:00
- Watchdog: falsi allarmi "radar fermo" quando scanner attivo
- Watchdog: auto-conteggio errori OpenSky 429
- Scanner diurno: mancata cattura arrivi (solo D, mai A)
- Quality check: finestra temporale vuota con `reference_date`
- Quality check: check 23 (timestamp = ''), check 27 (nome funzione)
- Quality check: falsi positivi check 15 e 20
- Encoding `bgy_version.py` (`IdentitÃ` → `Identità`)

### Rimosso
- 10 stub deprecati da `bgy_config_manager.py`
- 13 import inutilizzati in vari file
- Funzione `calculate_distance` (consolidata in `haversine`)
- 3 script one-shot archiviati (`add_missing_airlines.py`, `fix_airlines_config.py`, `update_airlines_config.py`)

### Deprecato
- File JSON anagrafici rimossi dal progetto (backup in `bgy_data/bgy_archive/json_v2.7.0/`)

## [2.8.4] — 2026-09-23

### Aggiunto
- Quality check con 10 check base (F11e)
- Statistiche in email di stato (F18b — primo abbozzo)
- Fix tab Notifiche GUI (v1.0.0)

### Corretto
- Bug vari in `bgy_db_migrate.py`, `bgy_mailer.py`

## [2.7.x] — 2026-09-18/22

### Aggiunto
- Deduplica report notturno
- Modello 5 categorie (Passeggeri, Cargo, Charter, Passeggeri radar, Non identificato)
- Matching IATA↔ICAO
- Arricchimento OpenFlights

## [2.5.0] — 2026-09-15/17

### Aggiunto
- Database PostgreSQL in produzione (F8)
- Prima release stabile

## [2.3.x] — 2026-09-14

### Aggiunto
- Fallback multi-sorgente (adsb.lol, adsb.fi)
- Sync GitHub automatico
- Notifiche email