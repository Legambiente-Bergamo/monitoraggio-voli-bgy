"""
bgy_tools/faa_bulk_check.py
Scarica il database FAA ReleasableAircraft.zip (con User-Agent da browser),
estrae MASTER.txt e verifica la copertura di YEAR MFR per gli icao24 USA.
"""
import os
import sys
import zipfile
import requests
import pandas as pd

sys.path.insert(0, os.getcwd())
from bgy_core import bgy_db

FAA_URL = "https://registry.faa.gov/database/ReleasableAircraft.zip"
ZIP_PATH = "bgy_data/bgy_assets/ReleasableAircraft.zip"
MASTER_PATH = "bgy_data/bgy_assets/MASTER.txt"

def download_faa():
    if os.path.exists(ZIP_PATH):
        print(f"File ZIP già presente: {ZIP_PATH}")
        return True
    
    print(f"Scarico il database FAA da: {FAA_URL}")
    print("Il file è grande (~500 MB), potrebbe volerci qualche minuto...")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.8,en-US;q=0.5,en;q=0.3",
        }
        r = requests.get(FAA_URL, headers=headers, stream=True, timeout=300)
        r.raise_for_status()
        os.makedirs(os.path.dirname(ZIP_PATH), exist_ok=True)
        
        total_size = int(r.headers.get('content-length', 0))
        downloaded = 0
        
        with open(ZIP_PATH, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0 and downloaded % (50 * 1024 * 1024) < 8192:
                    perc = (downloaded / total_size) * 100
                    print(f"   ... {downloaded / (1024*1024):.1f} MB scaricati ({perc:.1f}%)")
                    
        print(f"✅ Download completato: {ZIP_PATH}")
        return True
    except Exception as e:
        print(f"❌ Errore durante il download: {e}")
        return False

def extract_master():
    if not os.path.exists(ZIP_PATH):
        print("File ZIP non trovato.")
        return False
    try:
        with zipfile.ZipFile(ZIP_PATH, 'r') as z:
            z.extract('MASTER.txt', path=os.path.dirname(MASTER_PATH))
        print(f"✅ Estratto: {MASTER_PATH}")
        return True
    except Exception as e:
        print(f"❌ Errore durante l'estrazione: {e}")
        return False

def main():
    if not download_faa() or not extract_master():
        return

    print("\n1. Recupero degli icao24 americani dal database...")
    ok, rows = bgy_db.execute_query(
        "SELECT icao24 FROM aircraft_icao24_db WHERE LEFT(icao24, 1) = 'a'"
    )
    if not ok:
        print("Errore DB:", rows)
        return
    icao_americani = {str(r[0]).upper() for r in rows if r[0]}
    print(f"   Trovati {len(icao_americani)} icao24 con prefisso 'a' (USA).")

    if not icao_americani:
        print("Nessun icao24 americano da verificare.")
        return

    print("\n2. Lettura del file MASTER.txt...")
    try:
        df = pd.read_csv(MASTER_PATH, dtype=str, encoding='latin-1')
        
        # Pulizia dei nomi delle colonne: rimuove spazi, caratteri BOM (ï»¿) e forza l'uppercase
        df.columns = [c.strip().upper().replace('Ï»¿', '').replace('\ufeff', '') for c in df.columns]
        
        col_hex = None
        col_year = None
        for c in df.columns:
            if 'MODE S CODE HEX' in c:
                col_hex = c
            if 'YEAR MFR' in c:
                col_year = c
        
        if not col_hex or not col_year:
            print(f"ERRORE: Colonne non trovate. Colonne disponibili: {list(df.columns)}")
            return
            
        print(f"   Colonne trovate: {col_hex}, {col_year}")
        
        df[col_hex] = df[col_hex].str.upper().str.strip()
        
        df_nostri = df[df[col_hex].isin(icao_americani)]
        
        con_anno = df_nostri[col_year].notna().sum()
        totale_trovati = len(df_nostri)
        
        copertura = (con_anno / totale_trovati * 100) if totale_trovati > 0 else 0
        
        print("\n=== RISULTATO ===")
        print(f"Icao24 americani nostri totali: {len(icao_americani)}")
        print(f"Trovati nel registro FAA: {totale_trovati}")
        print(f"Di quelli trovati, hanno l'anno di costruzione: {con_anno}")
        print(f"Copertura del campo 'YEAR MFR': {copertura:.1f}%")
        print("==================")
        
    except Exception as e:
        print(f"Errore durante la lettura: {e}")

if __name__ == "__main__":
    main()