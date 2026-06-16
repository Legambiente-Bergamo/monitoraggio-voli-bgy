#!/usr/bin/env python3
# bgy_sacbo_capture.py - Cattura voli e screenshot dal tabellone SACBO - Versione Cloud Aggiornata

import csv
import time
import sys
import os
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
    
    # FORZATURA PERCORSO BINARIO CLOUD: Cerca l'eseguibile impostato dall'Action di GitHub
    firefox_bin = os.environ.get("FIREFOX_BIN")
    if firefox_bin and os.path.exists(firefox_bin):
        options.binary_location = firefox_bin
        print(path_msg := f"[SACBO] Utilizzo binario Firefox personalizzato: {firefox_bin}")
        
    driver = None
    try:
        driver = webdriver.Firefox(options=options)
        driver.get(URL)
        time.sleep(6)
        
        try:
            cookie_btn = WebDriverWait(driver, 4).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Accetta') or contains(.,'ACCETTA') or contains(.,'Ok')]"))
            )
            driver.execute_script("arguments[0].click();", cookie_btn)
        except:
            pass

        soup_arr = BeautifulSoup(driver.page_source, 'html.parser')
        all_flights = parse_table(soup_arr, 'ARRIVO')
        ts = datetime.now().strftime("%H%M%S")
        driver.save_screenshot(os.path.join(SCREENSHOT_DIR, f"arrivi_{date_str}_{ts}.png"))
        
        try:
            dep_btn = driver.find_element(By.XPATH, "//button[contains(., 'Partenze') or contains(., 'Departures')]")
            driver.execute_script("arguments[0].click();", dep_btn)
            time.sleep(4)
            soup_dep = BeautifulSoup(driver.page_source, 'html.parser')
            all_flights.extend(parse_table(soup_dep, 'PARTENZA'))
            driver.save_screenshot(os.path.join(SCREENSHOT_DIR, f"partenze_{date_str}_{ts}.png"))
        except Exception as e:
            print(f"[SACBO] Nota switch pannello partenze non riuscito: {e}")

        if all_flights:
            save_flights_to_csv(all_flights, date_str)
            print(f"[SACBO] ✅ Estratti con successo {len(all_flights)} record operativi.")
    except Exception as e:
        print(f"[SACBO] ⚠️ Errore durante l'acquisizione Selenium: {e} (Evito il crash del workflow)")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
