# OPERATIONS.md — Guida operativa BGY Monitoring Suite 2.5

Guida pratica per chi usa la suite ogni giorno.

---

## 1. Avvio e arresto

### Avvio
Doppio click su `Avvia BGY.bat`. La GUI si apre automaticamente e avvia:
- uno scheduler (in background)
- un watchdog (in background)

### Arresto
Chiudi la GUI (pulsante X della finestra). Scheduler e watchdog vengono terminati automaticamente.

### Riavvio pulito
Se qualcosa non risponde, chiudi tutto e rilancia `Avvia BGY.bat`. Il batch esegue una pulizia di eventuali processi orfani prima dell'avvio.

---

## 2. Configurazione credenziali

I file di configurazione sensibili **non sono nel repository** e vanno creati manualmente in `bgy_config/`.

### `config_mail.json` — credenziali SMTP

```json
{
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "tuo.indirizzo@gmail.com",
    "sender_password": "password-per-app",
    "sender_name": "Sistema di Monitoraggio Automatico BGY",
    "recipients_daily": ["destinatario1@example.com"],
    "recipients_monthly": ["destinatario1@example.com"],
    "recipients_yearly": ["destinatario1@example.com"]
}
Nota Gmail: sender_password deve essere una password per app, non la password dell'account. Generala qui: https://myaccount.google.com/apppasswords

config_opensky.json — credenziali OpenSky
json
{
    "opensky_username": "tuo_username",
    "opensky_password": "tua_password"
}
Se non hai un account OpenSky, registrati su https://opensky-network.org/. Senza credenziali il sistema funziona lo stesso ma con rate limit molto più severo.

config_github.json — sync GitHub
json
{
    "enabled": true,
    "repo_url": "https://github.com/Legambiente-Bergamo/monitoraggio-voli-bgy.git",
    "branch": "main",
    "username": "Legambiente Bergamo",
    "email": "info@legambientebergamo.it",
    "token": "ghp_xxxxxxxxxxxxxxxxxx",
    "commit_prefix": "BGY Sync",
    "push_timeout_seconds": 300,
    "pull_timeout_seconds": 60
}
Nota token: crea un Personal Access Token con permessi di scrittura sul repo. Genera qui: https://github.com/settings/tokens

3. Uso della GUI
Tab "📊 Dashboard"
Timer diurni/notturni — countdown alla prossima scansione

Scansione Diurna — forza una scansione SACBO immediata

Scansione Notturna — forza una scansione radar immediata

Invia mail corretto funzionamento — invia email di stato manuale

Log di sistema — ultimi messaggi

Tab "📧 Configura Mail"
Gestisci i destinatari delle email per:

Report giornaliero

Report mensile

Report annuale

I cambiamenti si applicano subito dopo aver cliccato "💾 Salva Configurazione".

Tab "⏰ Configura Scansioni"
Configura:

Orari scansioni SACBO diurne (default: 00:00, 06:00, 12:00, 18:00)

Orari scansioni SACBO notturne (default: 23:00, 02:00, 05:00)

Intervallo radar (default: 2 minuti)

Orario report + sync GitHub (default: 06:30)

Dopo il salvataggio, riavvia la GUI per applicare i nuovi orari allo scheduler.

Tab "📄 Report Personalizzati"
Genera report su richiesta:

Giorno — un giorno specifico (diurno e/o notturno)

Mese — un mese (diurno e/o notturno)

Anno — un anno (diurno e/o notturno)

Per ciascun tipo, scegli:

Periodo (Da / A)

Formati (CSV, XLSX, PDF, DOCX, HTML)

Cartella di destinazione (default: bgy_data/bgy_output/bgy_csv/)

Clicca "📄 Genera Report Selezionati". Una finestra di progresso mostra l'avanzamento.

Tab "🐕 Watchdog"
Stato watchdog — ultimo check, prossimo check, esito dei 4 controlli

Cooldown notifiche — intervallo minimo tra due notifiche dello stesso tipo

Esegui Check Ora — forza un check manuale

Reset Cooldown — azzera i cooldown (le prossime notifiche partono subito)

Log dettagliato — esito degli ultimi 4 check

4. Report automatici
Ogni mattina alle 06:30
La routine giornaliera fa, in sequenza:

Verifica acquisizione SACBO diurna (per ieri)

Genera report giornaliero diurno (per ieri)

Verifica acquisizione notturna (per la notte iniziata ieri)

Genera report giornaliero notturno (per ieri)

Sincronizza GitHub (script + dati raw)

Invia email con esito dei 5 check

Se un check fallisce, l'email allega automaticamente il log di sistema.

Primo del mese alle 06:30
In aggiunta alla routine giornaliera:

Genera ed invia report mensile diurno

Genera ed invia report mensile notturno

Report annuale
Il report annuale non è automatico. Va generato manualmente dal tab "📄 Report Personalizzati" (daily + nightly).

5. Dove trovare i file
Cosa	Dove
Dati raw (scansioni, radar)	bgy_data/bgy_raw/
Report CSV	bgy_data/bgy_output/bgy_csv/
Report Excel	bgy_data/bgy_output/bgy_xlsx/
Report PDF	bgy_data/bgy_output/bgy_pdf/
Report Word	bgy_data/bgy_output/bgy_docx/
Report HTML	bgy_data/bgy_output/bgy_html/
Grafici	bgy_data/bgy_charts/
Log applicativi	bgy_data/bgy_logs/
Log archiviati (>7gg)	bgy_data/bgy_logs/bgy_archive/
Configurazioni	bgy_config/
6. Diagnostica rapida
"Nessun dato acquisito"
Controlla che la connessione internet funzioni

Apri bgy_data/bgy_logs/bgy_app_YYYY-MM-DD.log e cerca errori

Verifica che il sito SACBO sia raggiungibile: https://www.milanbergamoairport.it/it/voli-tempo-reale/

"Rate limit OpenSky"
Il watchdog invia una notifica quando rileva 5+ errori 429 in 500 righe di log

Verifica le credenziali in config_opensky.json

Attendi qualche ora prima di ritentare

"Radar fermo"
In fascia notturna, il file radar_YYYY-MM-DD.csv si aggiorna ogni 2 minuti

Se fermo, il watchdog verifica se lo scanner sta girando (log recenti)

Se lo scanner gira ma non ci sono aerei nell'area, non è un problema

Se lo scanner non gira, il watchdog tenta di riavviarlo

"Scheduler non attivo"
Il watchdog lo riavvia automaticamente

Se il riavvio fallisce, il watchdog invia un'email con urgenza

"Email non inviate"
Verifica config_mail.json (email mittente, password, destinatari)

Per Gmail, verifica che la password sia una "password per app"

Controlla il log per errori SMTP

7. Manutenzione periodica
Settimanale
Controlla il tab "🐕 Watchdog" per anomalie ricorrenti

Verifica che i log in bgy_data/bgy_logs/ non crescano troppo (archiviazione automatica a 7 giorni)

Mensile
Verifica che i report mensili vengano generati correttamente

Controlla il file bgy_config/config_rules_airlines.json: se ci sono molte voci "Compagnia XXX", aggiornale con i nomi reali

Stessa cosa per bgy_config/config_rules_countries.json

Annuale
Genera i report annuali (daily + nightly) dal tab "Report Personalizzati"

Aggiorna i dati ufficiali Assaeroporti in bgy_config/config_assaeroporti.json

8. Contatti e supporto
In caso di problemi non risolvibili con questa guida:

Circolo Legambiente Bergamo APS

Email: info@legambientebergamo.it

GitHub Issues: https://github.com/Legambiente-Bergamo/monitoraggio-voli-bgy/issues