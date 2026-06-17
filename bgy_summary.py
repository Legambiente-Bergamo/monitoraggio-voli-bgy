#!/usr/bin/env python3
# bgy_summary.py - Genera il riassunto e invia la mail a Legambiente in modo nativo

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

def invia_mail(testo_report, date_str):
    email_user = os.environ.get("EMAIL_USER")
    email_password = os.environ.get("EMAIL_PASSWORD")
    
    if not email_user or not email_password:
        print("[MAIL] ⚠️ Credenziali mancanti nell'ambiente. Salto l'invio.")
        return

    destinatario = "info@legambientebergamo.it"
    data_it = datetime.strptime(date_str, "%Y%m%d").strftime("%d/%m/%Y")
    
    msg = MIMEMultipart()
    msg['From'] = f"Monitor Bot Legambiente <{email_user}>"
    msg['To'] = destinatario
    msg['Subject'] = f"📊 Report Monitoraggio Voli Notturni BGY - {data_it}"
    
    # Corpo del messaggio (il riassunto testuale)
    corpo_mail = f"Buongiorno Circolo,\n\nEcco il resoconto della notte appena trascorsa:\n\n{testo_report}"
    msg.attach(MIMEText(corpo_mail, 'plain', 'utf-8'))
    
    # Allegati CSV
    file_da_allegare = [
        Path(REPORT_DIR) / f"report_completo_{date_str}.csv",
        Path(REPORT_DIR) / f"rumore_centraline_{date_str}.csv"
    ]
    
    for file_path in file_da_allegare:
        if file_path.exists() and file_path.stat().st_size > 0:
            with open(file_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename= {file_path.name}")
                msg.attach(part)
                
    try:
        print("[MAIL] Connessione al server SMTP di Gmail...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_user, email_password)
            server.sendmail(email_user, destinatario, msg.as_string())
        print("✅ [MAIL] Spedita con successo a info@legambientebergamo.it")
    except Exception as e:
        print(f"[MAIL] ❌ Errore durante l'invio: {e}")

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    report_completo = Path(REPORT_DIR) / f"report_completo_{date_str}.csv"
    rumore_file = Path(REPORT_DIR) / f"rumore_centraline_{date_str}.csv"
    output_txt = Path(REPORT_DIR) / f"riassunto_notte_{date_str}.txt"
    
    Path(REPORT_DIR).mkdir(exist_ok=True)
    
    total_punti_radar = 0
    voli_unici = set()
    sforamenti_totali = 0
    sforamenti_per_centralina = {}
    
    if report_completo.exists() and report_completo.stat().st_size > 0:
        with open(report_completo, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_punti_radar += 1
                if row.get('volo') and row['volo'] != 'BGY_TEST':
                    voli_unici.add(row['volo'].strip())

    if rumore_file.exists() and rumore_file.stat().st_size > 0:
        with open(rumore_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('valutazione') == 'CRITICO (SFORAMENTO)':
                    sforamenti_totali += 1
                    centr = row.get('centralina', 'Sconosciuta')
                    sforamenti_per_centralina[centr] = sforamenti_per_centralina.get(centr, 0) + 1

    data_it = datetime.strptime(date_str, "%Y%m%d").strftime("%d/%m/%Y")
    linee = [
        f"==================================================",
        f"📊 DIARIO DI MONITORAGGIO NOTTURNO - BGY ORIO",
        f"Report della notte: {data_it}",
        f"==================================================\n",
        f"✈️ TRAFFICO AEREO RILEVATO:",
        f"  - Velivoli unici tracciati dal radar: {len(voli_unici)}",
        f"  - Campionamenti di posizione registrati: {total_punti_radar}\n",
        f"🔊 IMPATTO ACUSTICO STIMATO (Soglia > 60 dB):",
        f"  - Eventi di sforamento totali calcolati: {sforamenti_totali}"
    ]
    
    if sforamenti_totali > 0:
        linee.append("  - Sforamenti per singola centralina ARPA:")
        for cb, count in sforamenti_per_centralina.items():
            linee.append(f"    * {cb}: {count} passaggi primi o critici")
    else:
        linee.append("  - ✅ Nessuno sforamento teorico critico sopra i 60 dB calcolato nei punti sensibili.")
        
    linee.extend([
        f"\n--------------------------------------------------",
        f"Generato automaticamente dal Bot Ambientale Legambiente Bergamo.",
        f"I file CSV di dettaglio sono allegati alla presente mail."
    ])
    
    testo_finale = "\n".join(linee)
    
    # Salva localmente il file txt
    with open(output_txt, 'w', encoding='utf-8') as f:
        f.write(testo_finale)
    print(f"[SUMMARY] ✅ Generato riassunto in {output_txt}")
    
    # Avvia la spedizione mail
    invia_mail(testo_finale, date_str)

if __name__ == "__main__":
    main()
