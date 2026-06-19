#!/usr/bin/env python3
# bgy_summary.py - Report flessibile con controllo anti-duplicazione mail

import csv
import sys
import os
import smtplib
from datetime import datetime
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

DATA_DIR = "dati"
REPORT_DIR = "report"
LOG_FILE = "report/diario_operazioni.log"

def scrivi_log(testo):
    ora = datetime.now().strftime("%H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ora}][SUMMARY] {testo}\n")

def invia_mail(testo_report, date_str):
    email_user = os.environ.get("EMAIL_USER")
    email_password = os.environ.get("EMAIL_PASSWORD")
    
    if not email_user or not email_password:
        scrivi_log("⚠️ Spedizione mail fallita: credenziali mancanti.")
        return

    destinatario = "legambiente.bg@gmail.com"
    data_it = datetime.strptime(date_str, "%Y%m%d").strftime("%d/%m/%Y")
    
    msg = MIMEMultipart()
    msg['From'] = f"Monitor Bot BGY <{email_user}>"
    msg['To'] = destinatario
    msg['Subject'] = f"📊 Report Monitoraggio Voli BGY - Notte {data_it}"
    
    msg.attach(MIMEText(testo_report, 'plain', 'utf-8'))
    
    for cartella in [DATA_DIR, REPORT_DIR]:
        for file_path in Path(cartella).glob(f"*{date_str}*"):
            if file_path.suffix in ['.csv', '.log'] and file_path.stat().st_size > 0:
                with open(file_path, "rb") as attachment:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename= {file_path.name}")
                    msg.attach(part)
                    
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_user, email_password)
            server.sendmail(email_user, destinatario, msg.as_string())
        scrivi_log(f"✅ SUCCESS: Mail inoltrata a {destinatario}")
    except Exception as e:
        scrivi_log(f"❌ ERROR SMTP: {e}")

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    output_txt = Path(REPORT_DIR) / f"riassunto_notte_{date_str}.txt"
    
    # CONTROLLO SICUREZZA ANTI-DUPLICAZIONE:
    # Se il file di riassunto di oggi esiste già E non siamo in un lancio manuale forzato,
    # significa che abbiamo già elaborato e spedito la mail per questa notte.
    is_manual = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
    if output_txt.exists() and not is_manual:
        scrivi_log("ℹ️ Report di oggi già inviato in precedenza. Salto il blocco mail per evitare duplicati.")
        return

    sacbo_file = Path(DATA_DIR) / f"sacbo_{date_str}.csv"
    radar_file = Path(DATA_DIR) / f"radar_{date_str}.csv"
    
    Path(REPORT_DIR).mkdir(exist_ok=True)
    data_it = datetime.strptime(date_str, "%Y%m%d").strftime("%d/%m/%Y")
    
    corpo = [
        f"==================================================",
        f"📊 REPORT DI MONITORAGGIO VOLI - BGY ORIO AL SERIO",
        f"Data del monitoraggio: {data_it}",
        f"==================================================\n",
    ]
    
    # 1. TABELLONE SACBO
    corpo.append("📋 1. MOVIMENTI DAL TABELLONE AEROPORTO (Fascia Ore 23:00)")
    voli_tabellone = []
    fonte_tabellone = "Non rilevata"
    
    if sacbo_file.exists() and sacbo_file.stat().st_size > 0:
        with open(sacbo_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('volo') and row['volo'] != 'ASSENTE':
                    voli_tabellone.append(row)
                    fonte_tabellone = row.get('fonte_informazione', 'SACBO Mirror')
                    
        if voli_tabellone:
            corpo.append(f"  [Fonte: {fonte_tabellone}]")
            corpo.append(f"  Rilevati {len(voli_tabellone)} movimenti pianificati nella fascia critica:")
            for v in voli_tabellone:
                corpo.append(f"    ✈️ Volo {v['volo']} delle {v['orario_previsto']} -> Dest: {v['destinazione']} ({v['stato']})")
        else:
            corpo.append("  ⚠️ Nessun volo commerciale attivo registrato nel tabellone per questa notte.")
    else:
        corpo.append("  ❌ Errore: File del tabellone aeroporto non generato o vuoto.")
        
    corpo.append("\n--------------------------------------------------\n")
    
    # 2. RADAR GEOGRAFICO
    corpo.append("📡 2. RILEVAZIONI RADAR IN TEMPO REALE (Spazio Aereo Bergamo)")
    
    if radar_file.exists() and radar_file.stat().st_size > 0:
        aerei_radar = set()
        campionamenti = 0
        with open(radar_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                campionamenti += 1
                if row.get('callsign') and row['callsign'] != 'UNK':
                    aerei_radar.add(row['callsign'].strip())
                    
        if campionamenti > 0:
            corpo.append("  [Fonte: Reti SDR Aperte (OpenSky Network / ADSB.fi)]")
            corpo.append(f"  - Velivoli fisicamente intercettati nei cieli: {len(aerei_radar)}")
            corpo.append(f"  - Posizioni radar totali archiviate: {campionamenti}")
            if aerei_radar:
                corpo.append(f"  - Codici volo identificati in volo: {', '.join(aerei_radar)}")
        else:
            corpo.append("  ✅ Radar attivo: Nessun aeromobile ha attraversato le coordinate della centralina in questa sessione.")
    else:
        corpo.append("  ℹ️ Dati radar non disponibili per questa notte (Nessun aereo tracciato o server offline).")
        
    contenuto_log = ""
    if Path(LOG_FILE).exists():
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            contenuto_log = f.read()
            
    corpo.extend([
        f"\n==================================================",
        f"🛠️ REGISTRO DIAGNOSTICO DI SISTEMA (LOG)",
        f"==================================================",
        contenuto_log,
        f"--------------------------------------------------",
        f"Generato dal Bot Ambientale di Legambiente Bergamo."
    ])
    
    testo_finale = "\n".join(corpo)
    with open(output_txt, 'w', encoding='utf-8') as f:
        f.write(testo_finale)
        
    scrivi_log("✅ Report leggibile strutturato con successo.")
    invia_mail(testo_finale, date_str)

if __name__ == "__main__":
    main()
