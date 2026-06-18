#!/usr/bin/env python3
# bgy_summary.py - Spedizioniere del diario di log e dei dati grezzi

import os
import sys
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

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    email_user = os.environ.get("EMAIL_USER")
    email_password = os.environ.get("EMAIL_PASSWORD")
    
    if not email_user or not email_password:
        print("[SUMMARY] Credenziali SMTP assenti. Impossibile mandare la mail.")
        return

    destinatario = "legambiente.bg@gmail.com"
    data_it = datetime.strptime(date_str, "%Y%m%d").strftime("%d/%m/%Y")
    
    # Leggiamo il file di log per inserirlo nel corpo del messaggio (Priorità 2)
    contenuto_log = "Il file di log non è stato generato o è vuoto."
    if Path(LOG_FILE).exists():
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            contenuto_log = f.read()

    msg = MIMEMultipart()
    msg['From'] = f"Monitor Bot BGY <{email_user}>"
    msg['To'] = destinatario
    msg['Subject'] = f"📋 Registro Diagnostico e Dati BGY - Notte {data_it}"
    
    corpo_testo = (
        f"Buongiorno Circolo,\n\n"
        f"Ecco il riepilogo dello stato di funzionamento del sistema per la notte appena trascorsa ({data_it}).\n\n"
        f"=== DIARIO DELLE OPERAZIONI (LOG) ===\n"
        f"{contenuto_log}\n"
        f"=====================================\n\n"
        f"In allegato trovate i file CSV grezzi acquisiti dal sistema.\n"
        f"Un caro saluto,\nIl Bot Ambientale"
    )
    msg.attach(MIMEText(corpo_testo, 'plain', 'utf-8'))
    
    # Allega tutti i file presenti in dati/ e report/ per controllo totale
    for cartella in [DATA_DIR, REPORT_DIR]:
        for file_path in Path(cartella).glob(f"*{date_str}*"):
            if file_path.suffix in ['.csv', '.txt', '.log'] and file_path.stat().st_size > 0:
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
        print(f"[SUMMARY] ✅ Registro e dati inviati correttamente a {destinatario}")
    except Exception as e:
        print(f"[SUMMARY] ❌ Errore SMTP: {e}")

if __name__ == "__main__":
    main()
