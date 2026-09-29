# Changelog — BGY Monitoring Suite

## v2.9.2 — 29 settembre 2026

### Nuove funzionalità
- **Auto-riavvio servizio PostgreSQL** (F11e-2): watchdog con check 5 "database"
- **Auto-elevazione UAC** in `Avvia BGY.bat` v2.0.0
- **Avionio come fonte di confronto** (check 10 warning-only)
- **Statistiche di puntualità**: ritardi, medio, massimo, cancellati
- **Sconfinamenti gravi** (ritardo ≥ 1h)
- **Anomalie notturne** (voli a tabellone 3+ ore dopo lo sched)
- **Scansioni a 4 ore** (6/giorno diurne)

### Nuovi moduli
- `bgy_core/bgy_db_service.py` — Gestione servizio PostgreSQL
- `bgy_scanners/bgy_scanner_alt.py` — Scraper Avionio
- `bgy_tools/confronto_sacbo_avionio.py` — Confronto SACBO vs Avionio

### Nuovi alert (DB)
- `db_down`, `db_restarted`, `db_down_no_admin`, `db_down_restart_failed`

### Bug fix
- Falso sconfinamento FR 3530 (anomalia STIMA a mezzanotte)
- Voli con STIMA non aggiornata ora catturati (Criterio B)
- Falsi positivi watchdog SACBO stale

## v2.9.0 — 28 settembre 2026

- Aggiunta categoria sconfinamenti (baseline 23:00)
- Screenshot tabellone allegati all'email
- Diagnostica Cloudflare (check 9)
- Recupero scansioni mancate
