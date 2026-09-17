# SCHEMA.md — Contratti dati BGY Monitoring Suite

Documento di riferimento per tutti i formati di interscambio tra moduli.
**Se cambi un nome di colonna o un formato, aggiorna questo file.**

---

## 1. Naming dei file

| Categoria | Pattern | Esempio |
|-----------|---------|---------|
| Scansione SACBO (raw) | `scan_YYYY-MM-DD_HH-MM.csv` | `scan_2026-09-15_06-00.csv` |
| Radar notturno (raw, cumulativo per sessione) | `radar_YYYY-MM-DD.csv` | `radar_2026-09-15.csv` |
| Report giornaliero diurno | `report_daily_YYYY-MM-DD.csv` | `report_daily_2026-09-15.csv` |
| Report giornaliero notturno | `report_nightly_YYYY-MM-DD.csv` | `report_nightly_2026-09-15.csv` |
| Report mensile diurno | `report_monthly_daily_YYYY-MM.csv` | `report_monthly_daily_2026-09.csv` |
| Report mensile notturno | `report_monthly_nightly_YYYY-MM.csv` | `report_monthly_nightly_2026-09.csv` |
| Report annuale diurno | `report_yearly_daily_YYYY.csv` | `report_yearly_daily_2026.csv` |
| Report annuale notturno | `report_yearly_nightly_YYYY.csv` | `report_yearly_nightly_2026.csv` |

**Regola data di sessione notturna**: la data nel nome è quella di **inizio** sessione (il giorno delle 23:00), non quella di fine.

---

## 2. Formato `scan_*.csv` (SACBO diurno)

Prodotto da: `bgy_scanners/bgy_scanner_day.py`
Letto da: `bgy_reports/bgy_report_day.py`, `bgy_reports/bgy_report_night.py`

| Colonna | Tipo | Note |
|---------|------|------|
| `callsign_volo` | str | Es. `FR1234` |
| `tipo_movimento` | str | `A` (atterraggio) o `D` (decollo) |
| `destinazione_origine` | str | Città o aeroporto (destinazione se D, origine se A) |
| `orario_schedulato` | str | `HH:MM` |
| `orario_effettivo` | str | `HH:MM` |
| `stato_volo` | str | Testo da SACBO (es. "Operativo", "Atterrato") |
| `scan_timestamp` | str | `YYYY-MM-DD HH:MM:SS` (istante di scansione) |

---

## 3. Formato `radar_*.csv` (radar notturno)

Prodotto da: `bgy_scanners/bgy_scanner_night.py`
Letto da: `bgy_reports/bgy_report_night.py`, `bgy_watchdog.py`

**Cumulativo per sessione**, deduplicato per `icao24`.

| Colonna | Tipo | Note |
|---------|------|------|
| `timestamp` | str | `YYYY-MM-DD HH:MM:SS` (istante del rilevamento) |
| `callsign` | str | Es. `FR1234`, o `UNKNOWN` |
| `icao24` | str | Codice ICAO 24-bit (chiave di deduplicazione) |
| `pista` | str | `RWY 28`, `RWY 10`, `RWY 16`, `RWY 34`, o `N/D` |
| `fase_volo` | str | `Atterraggio`, `Decollo`, `Avvicinamento`, `Sorvolo`, `Transito`, `N/D` |
| `direzione` | str | Testo descrittivo (es. `Est -> Ovest`) o `N/D` |
| `quota_ft` | int | Quota in piedi |
| `rotta_deg` | float | Rotta in gradi (0-360) |
| `distanza_km` | float | Distanza da BGY (45.6739, 9.7042) |
| `paese` | str | Paese di registrazione o `N/D` |
| `sessione_notturna` | str | `YYYY-MM-DD` (data di inizio sessione) |

---

## 4. Formato `report_daily_*.csv`

Prodotto da: `bgy_reports/bgy_report_day.py`

| Colonna | Tipo | Note |
|---------|------|------|
| `volo` | str | Estratto da `callsign_volo` |
| `tipo_movimento` | str | `Atterraggio (A)` o `Decollo (D)` |
| `destinazione_origine` | str | |
| `orario_schedulato` | str | `HH:MM` |
| `orario_effettivo` | str | `HH:MM` |
| `stato_volo` | str | |
| `compagnia_aerea` | str | Da `config_rules_airlines.json` |
| `stato_destinazione` | str | Da `config_rules_countries.json` |
| `minuti_ritardo` | int | Positivo = ritardo, negativo = anticipo |
| `stato_ritardo` | str | `In Orario`, `Ritardo (+N min)`, `In Anticipo (N min)`, `N/D` |

---

## 5. Formato `report_nightly_*.csv`

Prodotto da: `bgy_reports/bgy_report_night.py`

| Colonna | Tipo | Note |
|---------|------|------|
| `callsign` | str | |
| `tipo_movimento` | str | `Passeggeri (...)`, `Cargo (...)`, `Non identificato / Sorvolo` |
| `is_scheduled` | bool | True se presente anche a tabellone SACBO |
| `destinazione_finale` | str | |
| `stato_destinazione` | str | |
| `compagnia_aerea` | str | |
| `modello_aereo` | str | Da `config_rules_aircraft_models.json` |
| `orario_schedulato` | str | Vuoto se non schedulato |
| `timestamp` | str | Vuoto se non rilevato da radar |
| `pista` | str | |
| `fase_volo` | str | |
| `direzione` | str | |
| `quota_ft` | int | |
| `rotta_deg` | float | |
| `distanza_km` | float | |
| `paese` | str | |
| `matched_score` | int | 0 (nessun match), 50 (match parziale), 100 (match esatto) |
| `stima_passeggeri` | int | Posti × load factor |
| `stima_rumore_db` | int | dB massimo tra le 8 centraline ARPA |

---

## 6. File di configurazione JSON

### 6.1 `bgy_config/config_data.json`

```json
{
  "scan_schedules": ["00:00", "06:00", "12:00", "18:00"],
  "sacbo_night_scans": ["23:00", "02:00", "05:00"],
  "sacbo_night_scan_enabled": true,
  "night_scan_interval_minutes": 2,
  "daily_report_time": "06:30",
  "notifications": {
    "cooldown_minutes": 30,
    "enabled": true
  }
}