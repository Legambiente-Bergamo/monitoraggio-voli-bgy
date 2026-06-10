#!/usr/bin/env python3
# bgy_master.py - Gestore centrale del sistema di monitoraggio BGY
# Versione definitiva - Rimane in esecuzione fino a orario END

import subprocess
import time
import sys
import signal
from datetime import datetime
from pathlib import Path

# Costanti
CONFIG_FILE = "config.txt"
LOG_DIR = "logs"
DATA_DIR = "dati"
REPORT_DIR = "report"
SCREENSHOT_DIR = "screenshots"

def create_directories():
    """Crea le directory necessarie"""
    for dir_name in [LOG_DIR, DATA_DIR, REPORT_DIR, SCREENSHOT_DIR]:
        Path(dir_name).mkdir(exist_ok=True)
    print("[MASTER] Directory create")

def load_config():
    """Carica la configurazione dal file config.txt"""
    config = {
        'START': '23:00',
        'END': '06:00'
    }
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if ':' in line:
                    # Salta le sezioni con dati lunghi
                    if line.startswith('CENTRALINE') or line.startswith('COMPAGNIE') or line.startswith('AEROPORTI') or line.startswith('MODELLI_AEREI'):
                        continue
                    key, value = line.split(':', 1)
                    config[key.strip()] = value.strip()
        print("[MASTER] Configurazione caricata")
    except FileNotFoundError:
        print(f"[MASTER] ATTENZIONE: File {CONFIG_FILE} non trovato, uso valori default")
    except Exception as e:
        print(f"[MASTER] ERRORE: {e}")
    
    return config

def get_date_str():
    return datetime.now().strftime("%Y%m%d")

def log_message(message):
    """Scrive un messaggio nel file di log"""
    try:
        log_file = Path(LOG_DIR) / f"master_{get_date_str()}.log"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")
    except:
        pass
    print(f"[MASTER] {message}")

def run_radar():
    """Avvia lo script radar"""
    date_str = get_date_str()
    return subprocess.Popen(
        ["py", "bgy_radar.py", date_str],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

def run_meteo():
    """Avvia lo script meteo"""
    date_str = get_date_str()
    return subprocess.Popen(
        ["py", "bgy_meteo.py", date_str],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

def run_sacbo():
    """Avvia lo script SACBO capture"""
    date_str = get_date_str()
    return subprocess.Popen(
        ["py", "bgy_sacbo_capture.py", date_str],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

def run_report():
    """Genera il report finale"""
    date_str = get_date_str()
    log_message(f"Generazione report per {date_str}")
    try:
        result = subprocess.run(["py", "bgy_report.py", date_str], capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            log_message("Report completato")
            print(result.stdout)
        else:
            log_message(f"Errore report: {result.stderr}")
    except subprocess.TimeoutExpired:
        log_message("Timeout generazione report")
    except Exception as e:
        log_message(f"Eccezione report: {e}")

def stop_process(process, name):
    """Termina un processo"""
    if process and process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=5)
            log_message(f"Terminato {name}")
        except:
            try:
                process.kill()
                log_message(f"Kill forzato {name}")
            except:
                pass

def main():
    print("\n" + "="*60)
    print("SISTEMA DI MONITORAGGIO BGY")
    print("   Aeroporto di Orio al Serio")
    print("="*60)
    
    # Setup
    create_directories()
    config = load_config()
    
    start_time = config.get('START', '23:00')
    end_time = config.get('END', '06:00')
    
    print(f"\nData: {get_date_str()}")
    print(f"Orario START: {start_time}")
    print(f"Orario END: {end_time}")
    print(f"Log: {LOG_DIR}/")
    print(f"Dati: {DATA_DIR}/")
    print(f"Report: {REPORT_DIR}/")
    
    # Stato
    radar_process = None
    meteo_process = None
    sacbo_process = None
    monitoring_active = False
    manual_stop = False
    
    def start_monitoring():
        nonlocal radar_process, meteo_process, sacbo_process, monitoring_active
        if not monitoring_active:
            print("\n" + "="*60)
            print("🟢 INIZIO MONITORAGGIO")
            print("="*60)
            
            radar_process = run_radar()
            print(f"📡 RADAR avviato (PID: {radar_process.pid})")
            
            meteo_process = run_meteo()
            print(f"🌤️ METEO avviato (PID: {meteo_process.pid})")
            
            sacbo_process = run_sacbo()
            print(f"📋 SACBO avviato (PID: {sacbo_process.pid})")
            
            monitoring_active = True
            print("\n✅ Tutti gli script sono in esecuzione")
            print(f"   Il monitoraggio terminerà automaticamente alle {end_time}\n")
    
    def stop_monitoring():
        nonlocal radar_process, meteo_process, sacbo_process, monitoring_active, manual_stop
        if monitoring_active:
            print("\n" + "="*60)
            if manual_stop:
                print("🛑 ARRESTO MANUALE RICHIESTO")
            else:
                print("🔴 FINE MONITORAGGIO PROGRAMMATA")
            print("="*60)
            
            print("Arresto RADAR...")
            stop_process(radar_process, "radar")
            
            print("Arresto METEO...")
            stop_process(meteo_process, "meteo")
            
            print("Arresto SACBO...")
            stop_process(sacbo_process, "sacbo")
            
            monitoring_active = False
            print("\n📊 Generazione report finale...")
            run_report()
    
    # Gestione Ctrl+C
    def signal_handler(sig, frame):
        nonlocal manual_stop
        print("\n")
        manual_stop = True
        log_message("Arresto richiesto dall'utente (Ctrl+C)")
        if monitoring_active:
            stop_monitoring()
        else:
            print("Nessun monitoraggio attivo. Uscita...")
        log_message("Sistema arrestato")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    
    print(f"\n⏰ Ora attuale: {current_time}")
    
    # Se siamo in orario di monitoraggio, avvia subito
    if current_time >= start_time and current_time < end_time:
        print("✅ Orario di monitoraggio in corso - Avvio immediato!")
        start_monitoring()
    else:
        # Calcola minuti mancanti
        start_h, start_m = map(int, start_time.split(':'))
        start_dt = now.replace(hour=start_h, minute=start_m, second=0)
        if start_dt < now:
            start_dt = start_dt.replace(day=now.day + 1)
        minuti_mancanti = int((start_dt - now).total_seconds() / 60)
        print(f"⏳ In attesa dell'orario START ({start_time})")
        print(f"   Manca: {minuti_mancanti} minuti")
    
    print("\n" + "="*60)
    print("🟢 SISTEMA IN ESECUZIONE")
    print("   Premi Ctrl+C per arrestare manualmente")
    print("="*60 + "\n")
    
    # Loop principale - controlla ogni 30 secondi
    try:
        while True:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            
            # Avvia il monitoraggio se è ora e non è attivo
            if not monitoring_active and current_time >= start_time and current_time < end_time:
                start_monitoring()
            
            # Ferma il monitoraggio se è ora e è attivo
            if monitoring_active and current_time >= end_time:
                print(f"\n⏰ Raggiunto orario END ({end_time})")
                stop_monitoring()
                print("\n✅ Monitoraggio completato. Il sistema rimane in attesa del prossimo ciclo.")
                print("   Premi Ctrl+C per uscire completamente.\n")
                # Resetta lo stato per il prossimo ciclo notturno
                monitoring_active = False
                radar_process = None
                meteo_process = None
                sacbo_process = None
            
            # Heartbeat ogni ora
            if now.minute == 0 and now.second < 30:
                if monitoring_active:
                    print(f"[HEARTBEAT] {current_time} - Monitoraggio ATTIVO")
                else:
                    print(f"[HEARTBEAT] {current_time} - In attesa START ({start_time})")
                time.sleep(30)
            
            time.sleep(30)  # Controlla ogni 30 secondi
            
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()