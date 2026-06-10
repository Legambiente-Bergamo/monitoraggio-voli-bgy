#!/usr/bin/env python3
# bgy_sacbo_capture.py - Cattura voli e screenshot dal tabellone SACBO
# Versione ottimizzata per esecuzione locale (Windows) e Cloud (GitHub Actions)

import csv
import time
import sys
import os
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ===============================
# COSTANTI E DIRECTORY
# ===============================
DATA_DIR = "dati"
REPORT_DIR = "report"
SCREENSHOT_DIR = "screenshots"
CONFIG_FILE = "config.txt"

URL = "https://www.milanbergamoairport.it/it/voli-tempo-reale/"

# ===============================
# FUNZIONI DI UTILITY
# ===============================

def create_directories():
    """Crea le directory necessarie se non esistono"""
    for dir_name in [DATA_DIR, REPORT_DIR, SCREENSHOT_DIR]:
        Path(dir_name).mkdir(exist_ok=True)

def get_timestamp():
    """Restituisce timestamp orario per distinguere gli screenshot"""
    return datetime.now().strftime("%H%M%S")

def log_message(message):
    """Stampa un messaggio di log tracciabile dal Master"""
    print(f"[SACBO] {message}")

def load_config():
    """Carica l'intervallo di cattura dal file di configurazione"""
    config = {'INTERVALLO_SACBO': 900} # Default 15 minuti
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and ':' in line:
                        if line.startswith('INTERVALLO_SACBO'):
                            key, value = line.split(':', 1)
                            config[key.strip()] = int(value.strip())
        except Exception as e:
            log_message(f"Errore lettura config: {e}")
    return config

def parse_table(soup, flight_type):
    """Esegue il parsing della tabella arrivi/partenze HTML di SACBO"""
    flights = []
    # Cerca i blocchi riga tipici del tabellone SACBO
    rows = soup.find_all('div', class_='flight-row') or soup.find_all('tr')
    
    for row in rows:
        try:
            cells = [c.text.strip() for c in row.find_all(['div', 'td']) if c.text.strip()]
            if len(cells) >= 4:
                # Estrazione base (adattabile a lievi cambi di layout del sito)
                flights.append({
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'tipo': flight_type,
                    'orario_previsto': cells[0],
                    'volo': cells[1],
                    'provenienza_destinazione': cells[2],
                    'stato': cells[3]
                })
        except:
            continue
    return flights

def save_flights_to_csv(flights, date_str):
    """Salva i dati estratti nel file CSV giornaliero"""
    if not flights:
        return
    
    file_path = Path(DATA_DIR) / f"sacbo_{date_str}.csv"
    file_exists = file_path.exists()
    
    keys = flights[0].keys()
    with open(file_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        if not file_exists:
            writer.writeheader()
        writer.writerows(flights)

# ===============================
# CORE SCRAPER & SCREENSHOT
# ===============================

def capture_flights_and_screenshots(date_str):
    """Avvia Selenium Headless per estrarre i dati e scattare gli screenshot"""
    create_directories()
    
    options = Options()
    options.add_argument("--headless")  # Obbligatorio per GitHub Actions e background Windows
    options.add_argument("--width=1920")
    options.add_argument("--height=1080")
    
    driver = None
    all_flights = []
    
    try:
        log_message("Avvio del browser Firefox Headless...")
        driver = webdriver.Firefox(options=options)
        driver.get(URL)
        
        # Attesa del caricamento della pagina (massimo 15 secondi)
        time.sleep(6)
        
        # Gestione Cookie Banner (se presente, clicca per liberare la visuale dello screenshot)
        try:
            cookie_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Accetta') or contains(.,'ACCETTA') or contains(.,'Close')]"))
            )
            driver.execute_script("arguments[0].click();", cookie_btn)
            time.sleep(1)
        except:
            pass # Se non compare o è già accettato, procede oltre

        # --- SEZIONE ARRIVI ---
        log_message("Estrazione dati ed esecuzione screenshot ARRIVI...")
        soup_arrivals = BeautifulSoup(driver.page_source, 'html.parser')
        arrivals = parse_table(soup_arrivals, 'ARRIVO')
        all_flights.extend(arrivals)
        
        # Salva lo screenshot nella cartella dedicata 'screenshots/'
        screenshot_arr = os.path.join(SCREENSHOT_DIR, f"arrivi_{date_str}_{get_timestamp()}.png")
        driver.save_screenshot(screenshot_arr)
        log_message(f"Screenshot Arrivi archiviato in: {screenshot_arr}")
        
        # --- SEZIONE PARTENZE ---
        log_message("Cambio scheda sul tabellone: PARTENZE...")
        try:
            # Cerca il pulsante delle partenze sul sito SACBO e lo clicca via JavaScript
            dep_btn = driver.find_element(By.XPATH, "//button[contains(., 'Partenze') or contains(., 'Departures')]")
            driver.execute_script("arguments[0].click();", dep_btn)
            time.sleep(4) # Attesa caricamento nuova tabella
            
            soup_departures = BeautifulSoup(driver.page_source, 'html.parser')
            departures = parse_table(soup_departures, 'PARTENZA')
            all_flights.extend(departures)
            
            # Salva lo screenshot delle partenze
            screenshot_dep = os.path.join(SCREENSHOT_DIR, f"partenze_{date_str}_{get_timestamp()}.png")
            driver.save_screenshot(screenshot_dep)
            log_message(f"Screenshot Partenze archiviato in: {screenshot_dep}")
        except Exception as e:
            log_message(f"Impossibile scambiare tabella Partenze: {e}")

        # Salva tutti i dati cumulativi nel file CSV
        save_flights_to_csv(all_flights, date_str)
        log_message(f"Cattura completata con successo: {len(all_flights)} movimenti registrati nel database.")
        
    except Exception as e:
        log_message(f"❌ ERRORE CRITICO durante lo scraping: {e}")
    finally:
        if driver:
            driver.quit()

# ===============================
# MAIN IN LOOP (Gestito dal Master)
# ===============================

def main():
    # Prende la data passata dal master, altrimenti usa quella corrente
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    
    config = load_config()
    interval = config.get('INTERVALLO_SACBO', 900)
    
    log_message(f"Script attivato per la giornata: {date_str}")
    log_message(f"Frequenza di aggiornamento impostata a: {interval} secondi ({interval // 60} minuti)")
    
    # Resta in esecuzione attiva catturando i dati a intervalli regolari.
    # Verrà terminato in modo pulito dal bgy_master.py al raggiungimento dell'ora END.
    while True:
        try:
            capture_flights_and_screenshots(date_str)
            log_message(f"Prossimo controllo tra {interval // 60} minuti...")
            time.sleep(interval)
        except KeyboardInterrupt:
            log_message("Arresto dello script SACBO completato.")
            break
        except Exception as e:
            log_message(f"Riavvio del ciclo per micro-interruzione: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()
