# BGY Monitoring Suite

Sistema di monitoraggio automatico dell'Aeroporto di Bergamo - Orio al Serio (BGY).

Sviluppato da [Circolo Legambiente Bergamo APS](https://www.legambientebergamo.it).

**Versione corrente:** 2.5.0 (2026-09-15)

---

## Cosa contiene questo repository

- **Script Python** per il monitoraggio diurno e notturno dei voli
- **Configurazioni generiche** (regole compagnie, paesi, modelli aerei, centraline rumore)
- **Dati raw raccolti** dalla macchina di produzione (`bgy_data/bgy_raw/`)
- **Documentazione** e script di avvio

**NON contiene:**
- Report generati (CSV, XLSX, PDF, DOCX, HTML)
- Grafici
- Log applicativi
- Credenziali (SMTP, OpenSky, GitHub)

---

## Struttura del progetto
Monitoraggio BGY 2.5/
├── bgy_gui.py # Interfaccia grafica (avvio principale)
├── bgy_scheduler.py # Orchestratore automatico
├── bgy_watchdog.py # Controllo anomalie
├── Avvia BGY.bat # Script di avvio Windows
├── README.md # Questo file
├── OPERATIONS.md # Guida operativa
├── SCHEMA.md # Contratti dati
├── Licenza.txt # Licenza
├── requirements.txt # Dipendenze Python
├── .gitignore
│
├── bgy_core/ # Moduli core
│ ├── bgy_version.py # Versione unica della suite
│ ├── bgy_dates.py # Naming file, date, sessioni notturne
│ ├── bgy_paths.py # Percorsi centralizzati
│ ├── bgy_logger.py # Logging
│ ├── bgy_config_manager.py # Gestione configurazioni
│ ├── bgy_update_rules.py # Regole compagnie/paesi/modelli
│ ├── bgy_mailer.py # Invio email (unificato)
│ ├── bgy_notifier.py # (rimosso in 2.5, sostituito da bgy_mailer)
│ ├── bgy_github_sync.py # Sincronizzazione GitHub
│ ├── bgy_retry.py # Decorator retry
│ └── bgy_export_common.py # Utility comuni per gli exporter
│
├── bgy_scanners/ # Acquisizione dati
│ ├── bgy_scanner_day.py # Tabellone SACBO (h24)
│ └── bgy_scanner_night.py # Radar OpenSky + fallback
│
├── bgy_reports/ # Generazione report
│ ├── bgy_report_day.py # Report giornaliero diurno
│ ├── bgy_report_night.py # Report giornaliero notturno
│ ├── bgy_report_month.py # Report mensile (daily/nightly)
│ └── bgy_report_year.py # Report annuale (daily/nightly)
│
├── bgy_exporters/ # Esportazione multi-formato
│ ├── bgy_export_xlsx.py
│ ├── bgy_export_pdf.py
│ ├── bgy_export_docx.py
│ └── bgy_export_html.py
│
├── bgy_gui/ # Tab della GUI
│ ├── bgy_gui_dashboard.py
│ ├── bgy_gui_mail_config.py
│ ├── bgy_gui_scan_config.py
│ ├── bgy_gui_report_export.py
│ └── bgy_watchdog_config.py
│
├── bgy_utils/ # Utility
│ ├── bgy_utils_meteo.py # Meteo Open-Meteo (20:00-06:00)
│ ├── bgy_utils_noise.py # Stima rumore NPD
│ └── bgy_utils_assaeroporti.py # Dati ufficiali Assaeroporti
│
├── bgy_config/ # Configurazioni
│ ├── config_data.json # Configurazioni generali (tracciato)
│ ├── config_assaeroporti.json # Dati ufficiali (tracciato)
│ ├── config_mail.json # Credenziali SMTP (NON tracciato)
│ ├── config_opensky.json # Credenziali OpenSky (NON tracciato)
│ ├── config_github.json # Credenziali GitHub (NON tracciato)
│ ├── config_rules_airlines.json
│ ├── config_rules_countries.json
│ ├── config_rules_aircraft_models.json
│ └── config_noise_impact.json
│
└── bgy_data/
├── bgy_raw/ # Dati grezzi (sincronizzati)
├── bgy_output/
│ ├── bgy_csv/ # Report CSV
│ ├── bgy_xlsx/
│ ├── bgy_pdf/
│ ├── bgy_docx/
│ └── bgy_html/
├── bgy_charts/ # Grafici
└── bgy_logs/ # Log applicativi
└── bgy_archive/ # Log archiviati


---

## Installazione

### 1. Prerequisiti

- **Python 3.12** ([download](https://www.python.org/downloads/))
- **Git** (per clonare il repo)
- **Playwright** (installato con le dipendenze)

### 2. Clona il repository

```bash
git clone https://github.com/Legambiente-Bergamo/monitoraggio-voli-bgy.git
cd monitoraggio-voli-bgy