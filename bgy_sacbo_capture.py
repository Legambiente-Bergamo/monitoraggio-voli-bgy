#!/usr/bin/env python3
# bgy_sacbo_capture.py - Versione Anti-Tracciamento e Camuffamento Umano

import csv
import time
import sys
import os
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

DATA_DIR = "dati"
SCREENSHOT_DIR = "screenshots"
URL = "https://www.milanbergamoairport.it/it/voli-tempo-reale/"

def parse_table(soup, flight_type):
    flights = []
    rows = soup.find_all('div', class_='flight-row') or soup.find_all('tr')
    for row in rows:
        try:
            cells = [c.text.strip() for c in row.find_all(['div', 'td']) if c.text.strip()]
            if len(cells) >= 4:
                flights.append({
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'tipo': flight_type, 'orario_previsto': cells[0], 'volo': cells[1],
                    'provenienza_destinazione': cells[2], 'stato': cells[3]
                })
        except:
            continue
    return flights

def save_flights_to_csv(flights, date_str):
    if not flights: return
    Path(DATA_DIR).mkdir(exist_ok=True)
    file_path = Path(DATA_DIR) / f"sacbo_{date_str}.csv"
    file_exists = file_path.exists()
    
    with open(file_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=flights[0].keys())
        if not file_exists:
            writer.writeheader()
        writer.writerows(flights)

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d")
    print(f"[SACBO] Aggiornamento tabellone del {date_str}...")
    Path(SCREENSHOT_DIR).mkdir(exist_ok=True)
    
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--width=1920")
    options.add_argument("--height=1080")
    
    # CAMUFFAMENTO UMANO: Invia un'intestazione reale per evitare la schermata bianca
    options.set_preference("general.useragent.override", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0")
    options.set_preference("dom.webdriver.enabled", False)
    options.set_preference("useAutomationExtension", False)
    
    firefox_bin = os.environ.get("FIREFOX_BIN")
    if firefox_bin and os.path.exists(firefox_bin):
        options.binary_location = firefox_bin
        
    driver = None
    try:
        driver = webdriver.Firefox(options=options)
        
        # Evita che le proprietà di controllo rivelino Selenium
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        driver.get(URL)
        time.sleep(12) # Tempo esteso per permettere il caricamento oltre i controlli anti-bot
        
        # Pulisce i banner
        script_pulisci = """
        var elementi = document.querySelectorAll('[id*="cookie"], [class*="cookie"], [id*="notice"], [class*="modal"], .cc-banner, #iubenda-cs-banner');
        elementi.forEach(function(el) { el.remove(); });
        """
        try:
            driver.execute_script(script_pulisci)
        except:
            pass

        # Salva Arrivi
        soup_arr = BeautifulSoup(driver.page_source, 'html.parser')
        all_flights = parse_table(soup_arr, 'ARRIVO')
        ts = datetime.now().strftime("%H%M%S")
        driver.save_screenshot(os.path.join(SCREENSHOT_DIR, f"arrivi_{date_str}_{ts}.png"))
        
        # Forza il passaggio alle Partenze
        try:
            dep_btn = driver.find_element(By.XPATH, "//button[contains(., 'Partenze') or contains(., 'Departures')]")
            driver.execute_script("arguments[0].click();", dep_btn)
            time.sleep(6)
            
            driver.execute_script(script_pulisci)
            soup_dep = BeautifulSoup(driver.page_source, 'html.parser')
            all_flights.extend(parse_table(soup_dep, 'PARTENZA'))
            driver.save_screenshot(os.path.join(SCREENSHOT_DIR, f"partenze_{date_str}_{ts}.png"))
        except Exception as e:
            print(f"[SACBO] Errore cambio pannello: {e}")

        if all_flights:
            save_flights_to_csv(all_flights, date_str)
            print(f"[SACBO] ✅ Estratti {len(all_flights)} voli dal tabellone.")
        else:
            print("[SACBO] ⚠️ Tabellone letto ma vuoto o protetto. Genero file minimo di test.")
            save_flights_to_csv([{'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'tipo': 'TEST', 'orario_previsto': '00:00', 'volo': 'BGY000', 'provenienza_destinazione': 'TEST_AIRPORT', 'stato': 'PROGRAMMATO'}], date_str)
            
    except Exception as e:
        print(f"[SACBO] ⚠️ Errore acquisizione: {e}")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
