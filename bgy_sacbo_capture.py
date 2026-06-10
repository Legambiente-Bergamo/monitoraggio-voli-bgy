#!/usr/bin/env python3
# bgy_sacbo_capture.py - Cattura voli e screenshot dal tabellone SACBO
# Intervallo configurabile da config.txt

import csv
import time
import sys
import os
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
import requests
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ===============================
# COSTANTI
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
    """Crea le directory necessarie"""
    for dir_name in [DATA_DIR, SCREENSHOT_DIR]:
        Path(dir_name).mkdir(exist_ok=True)

def get_date_str():
    """Restituisce la data corrente nel formato YYYYMMDD"""
    return datetime.now().strftime("%Y%m%d")

def get_timestamp():
    """Restituisce timestamp per i file"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def log_message(message):
    """Logga un messaggio"""
    print(f"[SACBO] {message}")

def load_config():
    """Carica la configurazione dal file config.txt"""
    config = {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and ':' in line and not line.startswith('CENTRALINE') and not line.startswith('COMPAGNIE') and not line.startswith('AEROPORTI') and not line.startswith('MODELLI_AEREI'):
                    key, value = line.split(':', 1)
                    config[key.strip()] = value.strip()
        
        # Intervallo SACBO (default 900 secondi = 15 minuti)
        config['INTERVALLO_SACBO'] = int(config.get('INTERVALLO_SACBO', 900))
        
        return config
    except Exception as e:
        print(f"[SACBO] ERRORE caricamento config: {e}")
        return {'INTERVALLO_SACBO': 900}

def setup_driver():
    """Configura driver Firefox headless"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--width=1920")
    options.add_argument("--height=1080")
    
    # Preferenze per evitare rilevamento
    options.set_preference("dom.webdriver.enabled", False)
    options.set_preference("useAutomationExtension", False)
    
    driver = webdriver.Firefox(options=options)
    return driver

def accept_cookies(driver, wait):
    """Accetta i cookie se presenti"""
    try:
        accept_button = wait.until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//button[contains(text(), 'Accetta tutto') or contains(text(), 'Accetta tutti') or contains(text(), 'Accetta')]"
            ))
        )
        driver.execute_script("arguments[0].click();", accept_button)
        log_message("Cookie accettati")
        time.sleep(1)
        return True
    except:
        log_message("Nessun banner cookie trovato")
        return False

def remove_popups(driver):
    """Rimuove popup e banner vari"""
    driver.execute_script("""
        let selectors = [
            '[id*="cookie"]',
            '[class*="cookie"]',
            '[class*="consent"]',
            '[class*="banner"]',
            '[role="dialog"]'
        ];
        selectors.forEach(sel => {
            document.querySelectorAll(sel).forEach(el => el.remove());
        });
        document.body.style.overflow = 'visible';
    """)

def take_screenshot(driver, name, date_str):
    """Scatta screenshot della pagina"""
    filename = Path(SCREENSHOT_DIR) / f"tabellone_{name}_{date_str}.png"
    driver.save_screenshot(str(filename))
    log_message(f"Screenshot salvato: {filename}")
    return filename

def extract_flights(soup, flight_type):
    """Estrae i voli dalla tabella"""
    flights = []
    table = soup.find("table", class_="realtimeTable")
    
    if table is None:
        log_message(f"Tabella non trovata per {flight_type}")
        return flights
    
    tbody = table.find("tbody")
    if tbody is None:
        log_message(f"Tbody non trovato per {flight_type}")
        return flights
    
    rows = tbody.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 6:
            continue
        
        flight = {
            "tipo_volo": flight_type,
            "timestamp": datetime.now().isoformat(),
            "numero_volo": cells[1].get_text(strip=True),
            "destinazione": cells[2].get_text(strip=True),
            "orario_programmato": cells[3].get_text(strip=True),
            "orario_stimato": cells[4].get_text(strip=True),
            "stato": cells[5].get_text(strip=True),
        }
        flights.append(flight)
    
    return flights

def save_flights_to_csv(flights, date_str):
    """Salva i voli in CSV"""
    if not flights:
        log_message("Nessun volo da salvare")
        return
    
    filename = Path(DATA_DIR) / f"sacbo_{date_str}.csv"
    write_header = not filename.exists()
    
    with open(filename, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=flights[0].keys())
        if write_header:
            writer.writeheader()
        writer.writerows(flights)
    
    log_message(f"Salvati {len(flights)} voli in {filename}")

def capture_flights_and_screenshots():
    """Funzione principale di cattura"""
    create_directories()
    date_str = get_date_str()
    
    log_message(f"Avvio cattura tabellone per data {date_str}")
    
    driver = None
    try:
        driver = setup_driver()
        wait = WebDriverWait(driver, 20)
        
        log_message(f"Caricamento pagina: {URL}")
        driver.get(URL)
        
        # Attesa caricamento iniziale
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "realtimeTable")))
        time.sleep(3)
        
        # Gestione cookie e popup
        accept_cookies(driver, wait)
        remove_popups(driver)
        time.sleep(1)
        
        # ===============================
        # CATTURA ARRIVI
        # ===============================
        log_message("Cattura tabella ARRIVI...")
        take_screenshot(driver, "arrivi", date_str)
        
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        arrivals = extract_flights(soup, "arrivo")
        log_message(f"Estratti {len(arrivals)} voli in arrivo")
        
        # ===============================
        # CLICK SU PARTENZE
        # ===============================
        log_message("Passaggio alla tabella PARTENZE...")
        try:
            tab_partenze = wait.until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//button[.//text()[contains(., 'Partenze')]] | //a[.//text()[contains(., 'Partenze')]]"
                ))
            )
            driver.execute_script("arguments[0].click();", tab_partenze)
            time.sleep(4)
        except Exception as e:
            log_message(f"Errore nel click su Partenze: {e}")
            # Prova alternativa
            try:
                driver.execute_script("document.querySelector('button:contains(\"Partenze\")').click();")
                time.sleep(4)
            except:
                log_message("Impossibile passare alla tabella Partenze")
        
        # ===============================
        # CATTURA PARTENZE
        # ===============================
        log_message("Cattura tabella PARTENZE...")
        take_screenshot(driver, "partenze", date_str)
        
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        departures = extract_flights(soup, "partenza")
        log_message(f"Estratti {len(departures)} voli in partenza")
        
        # ===============================
        # SALVATAGGIO
        # ===============================
        all_flights = arrivals + departures
        save_flights_to_csv(all_flights, date_str)
        
        log_message(f"Cattura completata: {len(arrivals)} arrivi, {len(departures)} partenze")
        
    except Exception as e:
        log_message(f"ERRORE: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            driver.quit()
    
    return len(all_flights) if 'all_flights' in locals() else 0

def main():
    """Esecuzione continua (chiamata dal master)"""
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    
    # Carica configurazione per l'intervallo
    config = load_config()
    interval = config.get('INTERVALLO_SACBO', 900)
    interval_minuti = interval // 60
    
    log_message(f"Avviato per data {date_str}")
    log_message(f"Intervallo cattura: {interval} secondi ({interval_minuti} minuti)")
    
    # Loop infinito (sarà terminato dal master)
    while True:
        try:
            capture_flights_and_screenshots()
            
            # Attendi l'intervallo configurato prima della prossima cattura
            log_message(f"Attesa {interval} secondi ({interval_minuti} minuti) prima della prossima cattura...")
            time.sleep(interval)
            
        except KeyboardInterrupt:
            log_message("Arresto richiesto")
            break
        except Exception as e:
            log_message(f"Errore nel loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()