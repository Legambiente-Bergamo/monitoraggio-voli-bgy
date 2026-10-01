# SCHEMA.md — Contratti dati BGY Monitoring Suite

**Versione**: 2.9.5
**Data**: 30 settembre 2026

Documento di riferimento per **tutti i formati di interscambio** tra moduli.
Se cambi un nome di colonna, un tipo o un valore di enumerazione, **aggiorna questo file**.

---

## 0. Changelog

| Versione | Data | Modifiche |
|---|---|---|
| **2.9.5** | 2026-09-30 | Radar h24: aggiunta `fonte` in `radar_*.csv`; `radar_*.csv` è ora cumulativo per **giorno solare**; `sessione_notturna` in DB è nullable. Aggiunta `notte_categoria` e `direzione_sacbo` in `report_nightly_*.csv`. Aggiunti i valori `sconfinamento`, `sconfinamento_grave`, `anomalia`, `Passeggeri (radar)`, `Charter (...)`. Aggiunta sezione `scanner_radar` in `config_data.json`. Aggiunta sezione `database_service`. Aggiornati valori di `scan_schedules` (6 scansioni). |
| 2.9.0 | 2026-09-28 | Aggiunta `notte_categoria` (valori iniziali: `regolare`, `sconfinamento`). |
| 2.8.5 | 2026-09-24 | Aggiunta `direzione_sacbo` in `report_nightly_*.csv`. |
| 2.7.0 | 2026-09-18 | Introdotta la deduplica radar a 15 min. |
| 2.6.0 | 2026-09-17 | Introdotta la mappatura IATA+ICAO. |

---

## 1. Naming dei file

| Categoria | Pattern | Esempio |
|---|---|---|
| Scansione SACBO (raw) | `scan_YYYY-MM-DD_HH-MM.csv` | `scan_2026-09-30_10-00.csv` |
| Radar h24 (raw, cumulativo per giorno solare) | `radar_YYYY-MM-DD.csv` | `radar_2026-09-30.csv` |
| Riepilogo test parallelo (temporaneo) | `radar_test_YYYY-MM-DD_HH-MM.json` | `radar_test_2026-09-30_11-12.json` |
| Report giornaliero diurno | `report_daily_YYYY-MM-DD.csv` | `report_daily_2026-09-30.csv` |
| Report giornaliero notturno | `report_nightly_YYYY-MM-DD.csv` | `report_nightly_2026-09-29.csv` |
| Meteo notturno | `meteo_YYYY-MM-DD.csv` | `meteo_2026-09-29.csv` |
| Report mensile diurno | `report_monthly_daily_YYYY-MM.csv` | `report_monthly_daily_2026-09.csv` |
| Report mensile notturno | `report_monthly_nightly_YYYY-MM.csv` | `report_monthly_nightly_2026-09.csv` |
| Report annuale diurno | `report_yearly_daily_YYYY.csv` | `report_yearly_daily_2026.csv` |
| Report annuale notturno | `report_yearly_nightly_YYYY.csv` | `report_yearly_nightly_2026.csv` |
| Screenshot tabellone Partenze | `board_dep_YYYY-MM-DD_HH-MM.png` | `board_dep_2026-09-30_23-00.png` |
| Screenshot tabellone Arrivi | `board_arr_YYYY-MM-DD_HH-MM.png` | `board_arr_2026-09-30_23-00.png` |
| Log applicativo | `bgy_app_YYYY-MM-DD.log` | `bgy_app_2026-09-30.log` |

**Regola data di sessione notturna**: nel naming di `radar_*.csv`, `report_nightly_*.csv` e `meteo_*.csv`, la data è quella di **inizio** sessione (il giorno delle 23:00), non quella di fine.

**Regola radar h24**: `radar_*.csv` è cumulativo per **giorno solare** (00:00-23:59). Il file viene esteso a ogni scansione (ogni 2 minuti). La sessione notturna (23:00-05:59) attraversa la mezzanotte: per filtrare la sessione notturna occorre leggere **due file** (`radar_YYYY-MM-DD.csv` di ieri e di oggi) o usare il DB (`radar_detections.sessione_notturna`).

---

## 2. Formato `scan_*.csv` (SACBO diurno)

Prodotto da: `bgy_scanners/bgy_scanner_day.py`
Letto da: `bgy_reports/bgy_report_day.py`, `bgy_reports/bgy_report_night.py`, `bgy_core/bgy_db_migrate.py`

Codifica: UTF-8 con BOM (`utf-8-sig`).

| Colonna | Tipo | Note |
|---|---|---|
| `callsign_volo` | str | Es. `FR1234` |
| `tipo_movimento` | str | `A` (atterraggio) o `D` (decollo) |
| `destinazione_origine` | str | Città o aeroporto (destinazione se D, origine se A) |
| `orario_schedulato` | str | `HH:MM` |
| `orario_effettivo` | str | `HH:MM` |
| `stato_volo` | str | Testo da SACBO (es. `Operativo`, `Atterrato`, `In Ritardo`, `Imbarco Chiuso`, `Cancellato`) |
| `scan_timestamp` | str | `YYYY-MM-DD HH:MM:SS` (istante di scansione) |

**Nota**: il file è la **fotografia del tabellone a un istante preciso**. Lo stesso volo può comparire in più scansioni con STIMA diversa. La deduplica avviene a valle, nel report.

---

## 3. Formato `radar_*.csv` (radar h24 multi-fonte)

Prodotto da: `bgy_scanners/bgy_scanner_radar.py`
Letto da: `bgy_reports/bgy_report_night.py`, `bgy_watchdog.py`, `bgy_core/bgy_db_migrate.py`

Codifica: UTF-8 con BOM (`utf-8-sig`).

**Cumulativo per giorno solare**, deduplicato su `(icao24, finestra 2 minuti)`.

| Colonna | Tipo | Note |
|---|---|---|
| `timestamp` | str | `YYYY-MM-DD HH:MM:SS` (istante del rilevamento) |
| `callsign` | str | Es. `FR1234`, o `UNKNOWN` |
| `icao24` | str | Codice ICAO 24-bit (chiave di deduplicazione) |
| `pista` | str | `RWY 28`, `RWY 10`, `RWY 16`, `RWY 34`, o `N/D` |
| `fase_volo` | str | Vedi Sezione 8.1 |
| `direzione` | str | Testo descrittivo (es. `Est -> Ovest`) o `N/D` |
| `quota_ft` | int | Quota barometrica in piedi (0 se `alt_baro = "ground"`) |
| `rotta_deg` | float | Rotta in gradi (0-360) |
| `distanza_km` | float | Distanza da BGY (45.6739, 9.7042), calcolata con haversine |
| `paese` | str | Paese di registrazione (se disponibile) o `N/D` |
| `fonte` | str | `adsb.lol`, `adsb.fi`, `airplanes.live`, `opensky` |
| `sessione_notturna` | str | `YYYY-MM-DD` — **giorno solare corrente**, non sempre la sessione notturna corretta. Nel DB viene ricalcolata dal timestamp (NULL se fuori fascia 23:00-05:59). |

**Nota sulla `sessione_notturna`**: nel CSV è valorizzata con il giorno solare corrente (comportamento dello scanner). Nel DB (`radar_detections.sessione_notturna`) è **nullable** e viene calcolata correttamente dall'import:
- Se `timestamp.hour >= 23` → data del giorno stesso.
- Se `timestamp.hour < 6` → data del giorno precedente.
- Altrimenti → `NULL`.

---

## 4. Formato `report_daily_*.csv`

Prodotto da: `bgy_reports/bgy_report_day.py`
Letto da: `bgy_core/bgy_db_migrate.py`, `bgy_exporters/*`, `bgy_gui/bgy_gui_report_export.py`

Codifica: UTF-8.

| Colonna | Tipo | Note |
|---|---|---|
| `volo` | str | Estratto da `callsign_volo` |
| `callsign_volo` | str | Chiave di deduplica con `orario_schedulato` |
| `tipo_movimento` | str | `D` o `A` |
| `destinazione_origine` | str | |
| `orario_schedulato` | str | `HH:MM` |
| `orario_effettivo` | str | `HH:MM` |
| `stato_volo` | str | |
| `compagnia_aerea` | str | Da `airlines` (DB) |
| `stato_destinazione` | str | Da `countries` (DB) |
| `minuti_ritardo` | int | Positivo = ritardo, negativo = anticipo |
| `stato_ritardo` | str | `In Orario`, `Ritardo (+N min)`, `In Anticipo (N min)`, `N/D` |

**Nota su `minuti_ritardo`**: calcolato dalla differenza tra `orario_effettivo` e `orario_schedulato`. Gestisce lo scavalcamento di mezzanotte (se il volo è schedulato 23:30 ed effettivo 00:15, il ritardo è 45 min, non -23h15m).

---

## 5. Formato `report_nightly_*.csv`

Prodotto da: `bgy_reports/bgy_report_night.py`
Letto da: `bgy_core/bgy_db_migrate.py`, `bgy_exporters/*`

Codifica: UTF-8.

| Colonna | Tipo | Note |
|---|---|---|
| `callsign` | str | |
| `tipo_movimento` | str | Vedi Sezione 8.2 |
| `direzione_sacbo` | str | `D`, `A`, o vuoto. Dalla colonna `tipo_movimento` del tabellone SACBO. |
| `notte_categoria` | str | Vedi Sezione 8.3 |
| `is_scheduled` | bool | `True` se presente anche a tabellone SACBO |
| `destinazione_finale` | str | |
| `stato_destinazione` | str | |
| `compagnia_aerea` | str | |
| `modello_aereo` | str | Da `aircraft_by_code` (DB) |
| `orario_schedulato` | str | `HH:MM` — vuoto se non schedulato |
| `timestamp` | str | `YYYY-MM-DD HH:MM:SS` — vuoto se non rilevato da radar |
| `pista` | str | |
| `fase_volo` | str | |
| `direzione` | str | |
| `quota_ft` | int | |
| `rotta_deg` | float | |
| `distanza_km` | float | |
| `paese` | str | |
| `matched_score` | int | Vedi Sezione 8.4 |
| `stima_passeggeri` | int | Posti × load factor |
| `stima_rumore_db` | int | dB massimo tra le 8 centraline ARPA |

---

## 6. Formato `meteo_*.csv`

Prodotto da: `bgy_reports/bgy_report_night.py`
Letto da: `bgy_core/bgy_db_migrate.py`

Codifica: UTF-8.

| Colonna | Tipo | Note |
|---|---|---|
| `orario` | str | `HH:MM` (fascia 20:00-06:00) |
| `temperatura_c` | float | Temperatura in °C |
| `precipitazioni_mm` | float | Precipitazioni in mm |
| `vento_kmh` | float | Velocità del vento in km/h |
| `vento_direzione_deg` | int | Direzione del vento in gradi (0-360) |
| `condizioni` | str | Testo descrittivo (es. `Sereno`, `Nuvoloso`) |

---

## 7. File di stato

### 7.1 `bgy_data/bgy_logs/scanner_day_status.json`

Prodotto da: `bgy_scanners/bgy_scanner_day.py` (a ogni scansione diurna)
Letto da: `bgy_scheduler.py` (check 9 del job giornaliero)

```json
{
  "timestamp": "2026-09-30 12:00:15",
  "challenge_superato": true,
  "tab_arrivi_cliccato": true,
  "body_arrivi_cambiato": true,
  "n_decolli": 62,
  "n_arrivi": 61,
  "screenshot_dep": "bgy_data/bgy_screenshots/board_dep_2026-09-30_12-00.png",
  "screenshot_arr": "bgy_data/bgy_screenshots/board_arr_2026-09-30_12-00.png",
  "is_recovery": false,
  "recovered_slot": null,
  "messaggio": "Scanner diurno OK (62 D + 61 A)"
}
Campi:

Campo	Tipo	Note
timestamp	str	YYYY-MM-DD HH:MM:SS
challenge_superato	bool	Cloudflare superato
tab_arrivi_cliccato	bool	Click sul tab "Arrivi" riuscito
body_arrivi_cambiato	bool	Fingerprint del body cambiato dopo il click
n_decolli	int	Voli D estratti
n_arrivi	int	Voli A estratti
screenshot_dep	str|null	Path screenshot Partenze
screenshot_arr	str|null	Path screenshot Arrivi
is_recovery	bool	True se è una scansione di recupero
recovered_slot	str|null	Slot originale mancato (YYYY-MM-DD HH:MM)
messaggio	str	Messaggio human-readable
7.2 bgy_data/bgy_logs/scheduler.lock
File di testo con il PID dello scheduler attivo. Usato da:

Scheduler stesso, per impedire doppio avvio.

Supervisor esterno (bgy_supervisor.ps1), per verificare se lo scheduler è vivo.

7.3 bgy_data/bgy_logs/notifier_cooldown.json
Stato dei cooldown delle notifiche email.

json
{
  "radar_missing": "2026-09-30T02:15:00",
  "opensky_429": "2026-09-30T03:45:00"
}
7.4 bgy_data/bgy_logs/recovery_state.json
Stato dei recuperi di scansioni mancate.

json
{
  "attempted": [
    "2026-09-30 06:00",
    "2026-09-30 10:00"
  ]
}
7.5 bgy_data/bgy_logs/watchdog_state.json
Ultimo check del watchdog.

json
{
  "last_check": "2026-09-30T11:12:30",
  "next_check": "2026-09-30T11:17:30",
  "manual": false,
  "results": {
    "sacbo": {"ok": true, "msg": "..."},
    "radar": {"ok": true, "msg": "..."},
    "opensky": {"ok": true, "msg": "..."},
    "scheduler": {"ok": true, "msg": "..."},
    "database": {"ok": true, "msg": "..."}
  }
}
7.6 bgy_data/bgy_logs/db_service_state.json
Stato del servizio PostgreSQL (F11e-2).

json
{
  "down_since": null,
  "restart_attempts": 0
}
7.7 bgy_data/bgy_logs/supervisor.log
Log dello script bgy_supervisor.ps1. Formato testuale:

text
YYYY-MM-DD HH:MM:SS - Scheduler NON attivo (PID: 12345). Avvio la suite...
YYYY-MM-DD HH:MM:SS - Suite avviata.
7.8 bgy_data/bgy_logs/coverage_log.txt
Log della raccolta copertura radar (temporaneo). Formato:

text
YYYY-MM-DD HH:MM:SS | exit=0 | adsb.lol=N adsb.fi=N airplanes.live=N opensky=N | json=<path>
8. Valori di enumerazione
8.1 fase_volo (radar)
Valore	Significato
Atterraggio	Distanza < 5 km, quota < 3000 ft, rotta > 180°
Decollo	Distanza < 5 km, quota < 3000 ft, rotta ≤ 180°
Avvicinamento	Distanza < 10 km, quota < 5000 ft
Sorvolo	Distanza < 15 km (max_distance_km)
Transito	Distanza ≥ 15 km
N/D	Dati insufficienti
8.2 tipo_movimento (report notturno)
Valore	Significato	Visibile default
Passeggeri	Volo di linea dal tabellone SACBO	Sì
Cargo (Nome)	Volo cargo dal radar	Sì
Charter (Nome)	Volo charter dal radar	Sì
Passeggeri (radar)	Volo passeggeri dal solo radar (opt-in)	No
Non identificato	Volo radar con callsign sconosciuto (opt-in)	No
8.3 notte_categoria (report notturno)
Valore	Significato
regolare	Schedulato in fascia 23:00-05:59
sconfinamento	Schedulato fuori fascia ma operante in fascia notturna (ritardo < 60 min)
sconfinamento_grave	Come sopra, ma con ritardo ≥ 60 min
anomalia	Volo a tabellone 3+ ore dopo lo sched, non cancellato
"" (vuoto)	Voli radar non matchati (cargo, charter, passeggeri radar, non identificati)
8.4 matched_score
Valore	Significato
0	Nessun match radar
50	Match parziale (fase compatibile ma orario lontano)
100	Match esatto (radar entro la finestra e fase compatibile)
8.5 direzione_sacbo
Valore	Significato
D	Decollo (dal tabellone SACBO)
A	Atterraggio (dal tabellone SACBO)
"" (vuoto)	Volo non presente sul tabellone SACBO
9. File di configurazione JSON
9.1 bgy_config/config_data.json
Configurazione generale (versionabile su Git, non contiene credenziali).

Sezioni:

Sezione	Contenuto
scan_schedules	Orari scansioni SACBO diurne (array di HH:MM). Attuale: 6 scansioni ogni 4h.
sacbo_night_scans	Orari scansioni SACBO notturne. Attuale: ["23:00", "00:01", "02:00", "05:00"].
sacbo_night_scan_enabled	Abilita scansioni SACBO notturne.
night_scan_interval_minutes	Intervallo radar (in minuti). Attuale: 2.
daily_report_time	Ora del job giornaliero. Attuale: 06:30.
notifications	Flag email (vedi Sezione 9.2).
weather	Config Open-Meteo (lat, lon, fascia oraria).
scanner_radar	Config scanner radar h24 (bbox, raggi, soglie fase, piste).
scanner_day	Config scanner diurno (URL, timeout Playwright).
report_day	Soglie report diurno (delay_threshold_min, early_threshold_min).
report_night	Config report notturno (match_threshold_score, distanze per fase).
logging	Config logger (archive_days, log_prefix, level).
watchdog	Config watchdog (intervalli, soglie radar stale, grace period).
quality_check	Soglie quality check + reference_date (modalità apprendimento).
openflights	Config dataset OpenFlights (URL, cache, intervallo aggiornamento).
export	Config esportazione (tema, colonne, max_rows).
avionio	Config scanner Avionio (enabled, run_at_every_scan, retention).
database_service	Config servizio PostgreSQL (auto-restart, soglie).
Esempio completo in bgy_docs/config_data.example.json (da mantenere aggiornato).

9.2 Sezione notifications
Campo	Tipo	Default	Note
enabled	bool	true	Master switch email
alerts_enabled	bool	true	Abilita allarmi watchdog
daily_status_enabled	bool	true	Abilita email di stato 06:30 e report mensili/annuali
cooldown_minutes	int	30	Tempo minimo tra due notifiche della stessa chiave
unresolved_airlines_days	int	30	Giorni minimi per considerare una compagnia placeholder "da risolvere"
unresolved_airlines_min_occorrenze	int	1	Occorrenze minime per considerare una compagnia placeholder "da risolvere"
9.3 bgy_config/config_mail.json
Credenziali SMTP. Non versionato.

json
{
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "legambientebergamo@gmail.com",
    "sender_password": "app-specific-password",
    "sender_name": "Sistema di Monitoraggio Automatico BGY",
    "recipients": [],
    "recipients_daily": ["info@legambientebergamo.it"],
    "recipients_monthly": ["info@legambientebergamo.it"],
    "recipients_yearly": ["info@legambientebergamo.it"]
}
9.4 bgy_config/config_opensky.json
Credenziali OpenSky. Non versionato.

json
{
    "opensky_username": "",
    "opensky_password": ""
}
9.5 bgy_config/config_github.json
Token GitHub per il push. Non versionato.

json
{
    "enabled": true,
    "repo_url": "https://github.com/Legambiente-Bergamo/monitoraggio-voli-bgy.git",
    "branch": "main",
    "username": "Legambiente Bergamo",
    "email": "info@legambientebergamo.it",
    "token": "ghp_...",
    "commit_prefix": "BGY Sync",
    "push_timeout_seconds": 300,
    "pull_timeout_seconds": 60
}
9.6 bgy_config/config_database.json
Connessione PostgreSQL. Non versionato.

json
{
    "enabled": true,
    "host": "localhost",
    "port": 5432,
    "dbname": "bgy_monitoring",
    "user": "bgy_user",
    "password": "...",
    "connect_timeout": 10,
    "application_name": "BGY Monitoring Suite"
}
9.7 bgy_config/config_wordpress.json
Credenziali WordPress (F17, non ancora attivo). Non versionato.

json
{
    "enabled": false,
    "url": "https://www.legambientebergamasca.it/wp-admin",
    "username": "BGY",
    "app_password": "..."
}
10. Schema database PostgreSQL
Il DB bgy_monitoring contiene 17 tabelle (v2.9.5).

10.1 Tabelle operative (6)
10.1.1 scans
Metadata delle scansioni SACBO.

Colonna	Tipo	Note
id	BIGSERIAL PK	
scan_timestamp	TIMESTAMP	
file_name	TEXT UNIQUE	Es. scan_2026-09-30_10-00.csv
data_riferimento	DATE	
tipo	VARCHAR(10)	diurno o notturno
righe_importate	INTEGER	
imported_at	TIMESTAMP	
10.1.2 flights_sacbo
Voli estratti dalle scansioni.

Colonna	Tipo	Note
id	BIGSERIAL PK	
scan_id	BIGINT FK → scans.id	
callsign_volo	TEXT	
tipo_movimento	VARCHAR(2)	D o A
destinazione_origine	TEXT	
orario_schedulato	TIME	
orario_effettivo	TIME	
stato_volo	TEXT	
scan_timestamp	TIMESTAMP	
data_riferimento	DATE	
imported_at	TIMESTAMP	
10.1.3 radar_detections
Rilevamenti radar h24.

Colonna	Tipo	Note
id	BIGSERIAL PK	
timestamp	TIMESTAMP	
callsign	TEXT	
icao24	TEXT	
pista	TEXT	
fase_volo	TEXT	
direzione	TEXT	
quota_ft	INTEGER	
rotta_deg	REAL	
distanza_km	REAL	
paese	TEXT	
sessione_notturna	DATE (nullable)	Calcolata dal timestamp. NULL fuori fascia 23:00-05:59.
data_riferimento	DATE	Giorno solare del timestamp
fonte	TEXT	adsb.lol, adsb.fi, airplanes.live, opensky
imported_at	TIMESTAMP	
10.1.4 weather_hourly
Meteo notturno.

Colonna	Tipo	Note
id	BIGSERIAL PK	
data_riferimento	DATE	
orario	TIME	
temperatura_c	REAL	
precipitazioni_mm	REAL	
vento_kmh	REAL	
vento_direzione_deg	INTEGER	
condizioni	TEXT	
imported_at	TIMESTAMP	
UNIQUE	(data_riferimento, orario)	
10.1.5 nightly_reports
Voli notturni arricchiti.

Colonna	Tipo	Note
id	BIGSERIAL PK	
data_riferimento	DATE	
callsign	TEXT	
tipo_movimento	TEXT	Vedi Sezione 8.2
direzione_sacbo	VARCHAR(2)	D, A, o NULL
notte_categoria	VARCHAR(30)	Vedi Sezione 8.3
is_scheduled	BOOLEAN	
destinazione_finale	TEXT	
stato_destinazione	TEXT	
compagnia_aerea	TEXT	
modello_aereo	TEXT	
orario_schedulato	TIME	
timestamp	TIMESTAMP	
pista	TEXT	
fase_volo	TEXT	
direzione	TEXT	
quota_ft	INTEGER	
rotta_deg	REAL	
distanza_km	REAL	
paese	TEXT	
matched_score	INTEGER	
stima_passeggeri	INTEGER	
stima_rumore_db	INTEGER	
imported_at	TIMESTAMP	
Vincolo: indice UNIQUE parziale uniq_nightly_flight su (data_riferimento, callsign, orario_schedulato) con WHERE orario_schedulato IS NOT NULL.

10.1.6 schema_version
Versione dello schema.

Colonna	Tipo	Note
version	INTEGER PK	Attuale: 2
applied_at	TIMESTAMP	
note	TEXT	
10.2 Tabelle anagrafiche (11)
Tabella	Righe	Contenuto
airlines	~190	Compagnie unificate (passeggeri + cargo + charter).
iata_to_icao	50	Mapping IATA → ICAO.
countries	337	Destinazione → paese.
aircraft_models	11	Modelli con capienza.
aircraft_by_code	~80	Codice compagnia → modello.
load_factors	~30	Load factor per compagnia.
noise_stations	8	Centraline ARPA (lat/lon).
noise_curves	~150	Curve NPD per modello e fase.
alert_messages	16	Template email watchdog.
assaeroporti_stats	2	Statistiche annuali Assaeroporti.
config_settings	~5	Costanti generiche.
10.3 Vista v_daily_report
Deduplica flights_sacbo per presentare un report giornaliero pulito. Usata dal tab "Report Personalizzati" della GUI.

Colonne: id, data_riferimento, callsign_volo, tipo_movimento, destinazione_origine, orario_schedulato, orario_effettivo, stato_volo, scan_timestamp.

10.4 Schema updates idempotenti
La funzione apply_schema_updates() in bgy_db_migrate.py esegue ALTER TABLE ... ADD COLUMN IF NOT EXISTS a ogni sync_date(). Questo permette al DB di adeguarsi automaticamente alle nuove versioni del codice.

Update attualmente applicati:

sql
ALTER TABLE nightly_reports ADD COLUMN IF NOT EXISTS direzione_sacbo VARCHAR(2);
ALTER TABLE nightly_reports ADD COLUMN IF NOT EXISTS notte_categoria VARCHAR(30);
ALTER TABLE radar_detections ADD COLUMN IF NOT EXISTS fonte TEXT;
ALTER TABLE radar_detections ADD COLUMN IF NOT EXISTS data_riferimento DATE;
ALTER TABLE radar_detections ALTER COLUMN sessione_notturna DROP NOT NULL;
11. Convenzioni generali
Encoding file CSV: UTF-8 con BOM (utf-8-sig).

Separatore CSV: virgola.

Decimal separator: punto.

Formato data: YYYY-MM-DD.

Formato ora: HH:MM o HH:MM:SS.

Formato timestamp: YYYY-MM-DD HH:MM:SS.

Valori mancanti: stringa vuota (non NULL, non N/D, non NaN).