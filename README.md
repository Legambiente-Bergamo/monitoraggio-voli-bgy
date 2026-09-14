# BGY Monitoring Suite

Sistema di monitoraggio automatico dell'Aeroporto di Bergamo - Orio al Serio (BGY).

Sviluppato da [Circolo Legambiente Bergamo APS](https://www.legambientebergamo.it).

## 📋 Cosa contiene questo repository

- **Script Python** per il monitoraggio diurno e notturno dei voli
- **Configurazioni generiche** (regole compagnie, paesi, modelli aerei, centraline rumore)
- **Dati raw raccolti** dalla macchina di produzione (`bgy_data/raw/`)
- **Documentazione** e script di avvio

**NON contiene:**
- Report generati (CSV, XLSX, PDF, DOCX, HTML)
- Grafici
- Log applicativi
- Credenziali (SMTP, OpenSky, GitHub)

## 🚀 Installazione

### 1. Prerequisiti

- **Python 3.12** ([download](https://www.python.org/downloads/))
- **Playwright** (installato automaticamente con le dipendenze)
- **Git** (per clonare il repo)

### 2. Clona il repository

```bash
git clone https://github.com/Legambiente-Bergamo/monitoraggio-voli-bgy.git
cd monitoraggio-voli-bgy