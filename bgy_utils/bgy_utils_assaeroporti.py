"""
bgy_utils/bgy_utils_assaeroporti.py - Dati ufficiali Assaeroporti.
Versione 2.5.0

- Nessun dato hardcoded nel codice: tutto in bgy_config/config_assaeroporti.json
- Prova il parsing automatico del sito Assaeroporti (link a file Excel/PDF),
  ma non è garantito: se fallisce, i dati si inseriscono a mano (via config).
- Espone get_comparison() per confrontare la nostra stima PAX con l'ufficiale.
"""
import os
import re
import sys
import requests
from datetime import datetime
# Bootstrap path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_config_manager import config_manager
from bgy_core.bgy_paths import RAW_DIR

logger = get_logger("Assaeroporti")


# =============================================================================
# CONFIG
# =============================================================================

def _cfg():
    return config_manager.get_assaeroporti_config()


# =============================================================================
# LETTURA / SCRITTURA DATI ANNUALI
# =============================================================================

def get_bgy_official_stats(year):
    """
    Ritorna il dict {passeggeri, movimenti, cargo_ton, fonte, data_aggiornamento}
    per l'anno richiesto, oppure {} se non disponibile.
    """
    cfg = _cfg()
    years = cfg.get("years", {})
    return years.get(str(year), {})


def save_bgy_official_stats(year, data):
    """
    Salva i dati ufficiali per l'anno specificato.
    data: dict con chiavi passeggeri, movimenti, cargo_ton (opzionali).
    """
    if not data:
        return False
    cfg = _cfg()
    cfg.setdefault("years", {})
    entry = dict(data)
    entry.setdefault("fonte", "manuale")
    entry["data_aggiornamento"] = datetime.now().strftime("%Y-%m-%d")
    cfg["years"][str(year)] = entry
    ok = config_manager.save_assaeroporti_config(cfg)
    if ok:
        logger.info(f"💾 Dati ufficiali {year} salvati: {entry}")
    return ok


# =============================================================================
# FETCH E PARSING
# =============================================================================

def download_assaeroporti_html(year=None, force=False):
    """
    Scarica la pagina statistiche di Assaeroporti e salva l'HTML in RAW_DIR.
    Ritorna il path del file HTML o None.
    """
    cfg = _cfg()
    url = cfg.get("source_url", "https://assaeroporti.com/statistiche/")
    timeout = cfg.get("http_timeout", 30)

    if year is None:
        year = datetime.now().year - 1

    try:
        logger.info(f"📥 Download pagina Assaeroporti...")
        resp = requests.get(url, timeout=timeout)
        if resp.status_code != 200:
            logger.error(f"Assaeroporti HTTP {resp.status_code}")
            return None
        os.makedirs(RAW_DIR, exist_ok=True)
        out_path = os.path.join(RAW_DIR, f"assaeroporti_{year}.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(resp.text)
        logger.info(f"💾 HTML salvato: {out_path}")
        return out_path
    except Exception as e:
        logger.error(f"Errore download Assaeroporti: {e}")
        return None


def _find_stats_links(html_text, year=None):
    """
    Cerca nell'HTML link a file di statistiche (xlsx, xls, pdf, csv).
    Ritorna una lista di URL (assoluti).
    """
    links = set()
    # href="..." con estensione
    pattern = re.compile(
        r'href=["\']([^"\']+\.(?:xlsx?|pdf|csv))["\']',
        re.IGNORECASE
    )
    for m in pattern.finditer(html_text):
        href = m.group(1)
        if not href.startswith("http"):
            href = "https://assaeroporti.com" + (
                href if href.startswith("/") else "/" + href
            )
        if year is None or str(year) in href:
            links.add(href)
    return sorted(links)


def fetch_assaeroporti_data(year=None):
    """
    Tenta il download e il parsing del file statistiche di Assaeroporti.
    Ritorna il dict dei dati per BGY, o None se il parsing fallisce.

    ATTENZIONE: il parsing è best-effort. Se il sito cambia struttura,
    il parsing fallisce e si deve inserire il dato manualmente.
    """
    if year is None:
        year = datetime.now().year - 1

    html_path = download_assaeroporti_html(year)
    if not html_path:
        return None

    try:
        with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
    except Exception as e:
        logger.error(f"Errore lettura HTML: {e}")
        return None

    links = _find_stats_links(html, year)
    if not links:
        logger.warning(f"Nessun link a file statistiche trovato per {year}")
        return None

    logger.info(f"🔍 Trovati {len(links)} link potenziali per {year}")

    for link in links:
        if link.lower().endswith((".xlsx", ".xls")):
            data = _try_parse_excel(link, year)
            if data:
                save_bgy_official_stats(year, data)
                return data

    logger.warning(
        f"Parsing automatico non riuscito per {year}. "
        "Inserire i dati manualmente in bgy_config/config_assaeroporti.json"
    )
    return None


def _try_parse_excel(url, year):
    """
    Scarica un file Excel e cerca la riga di Bergamo/BGY.
    Ritorna dict con passeggeri/movimenti/cargo_ton o None.
    """
    try:
        logger.info(f"📊 Tento parsing Excel: {url}")
        resp = requests.get(url, timeout=60)
        if resp.status_code != 200:
            logger.warning(f"HTTP {resp.status_code} su {url}")
            return None

        # Salva temporaneamente
        tmp_path = os.path.join(RAW_DIR, f"_tmp_assaeroporti_{year}.xlsx")
        with open(tmp_path, "wb") as f:
            f.write(resp.content)

        import pandas as pd
        # Prova tutti i fogli
        xl = pd.ExcelFile(tmp_path)
        for sheet in xl.sheet_names:
            df = xl.parse(sheet, header=None)
            result = _search_bgy_in_df(df)
            if result:
                logger.info(f"✅ Dati BGY trovati in foglio '{sheet}': {result}")
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                return result

        try:
            os.remove(tmp_path)
        except Exception:
            pass
        return None
    except Exception as e:
        logger.warning(f"Errore parsing Excel: {e}")
        return None


def _search_bgy_in_df(df):
    """
    Cerca la riga con 'Bergamo' o 'Orio al Serio' o 'BGY' nel DataFrame.
    Prova a estrarre passeggeri/movimenti/cargo dalle colonne numeriche.
    """
    try:
        import pandas as pd
        for idx, row in df.iterrows():
            row_str = " ".join(str(v) for v in row.values if pd.notna(v)).lower()
            if "bergamo" in row_str or "orio al serio" in row_str or " bgy " in row_str:
                numerics = []
                for v in row.values:
                    try:
                        if pd.notna(v):
                            f = float(v)
                            if f > 1000:  # scarta valori piccoli
                                numerics.append(int(f))
                    except (ValueError, TypeError):
                        continue
                if len(numerics) >= 2:
                    result = {}
                    # Euristica: il più grande è passeggeri, poi movimenti, poi cargo
                    numerics_sorted = sorted(numerics, reverse=True)
                    result["passeggeri"] = numerics_sorted[0]
                    if len(numerics_sorted) >= 2:
                        result["movimenti"] = numerics_sorted[1]
                    if len(numerics_sorted) >= 3:
                        result["cargo_ton"] = numerics_sorted[2]
                    result["fonte"] = "parsing_auto"
                    return result
        return None
    except Exception as e:
        logger.warning(f"Errore ricerca BGY nel DataFrame: {e}")
        return None


# =============================================================================
# CONFRONTO
# =============================================================================

def get_comparison(year, our_pax_estimate, our_movements=None):
    """
    Confronta la nostra stima con i dati ufficiali Assaeroporti.

    Args:
        year: anno (int o str)
        our_pax_estimate: passeggeri stimati da noi (int)
        our_movements: movimenti stimati da noi (int, opzionale)

    Returns:
        dict con:
          - year
          - official: dict dati ufficiali (o {})
          - ours: dict nostre stime
          - delta_pax: differenza passeggeri (nostro - ufficiale)
          - delta_pax_pct: differenza percentuale
          - delta_mov: differenza movimenti
          - delta_mov_pct: differenza percentuale
          - has_official: bool (True se ci sono dati ufficiali)
    """
    official = get_bgy_official_stats(year) or {}
    result = {
        "year": str(year),
        "official": official,
        "ours": {
            "passeggeri": int(our_pax_estimate or 0),
            "movimenti": int(our_movements) if our_movements is not None else None,
        },
        "has_official": bool(official),
    }

    off_pax = official.get("passeggeri")
    if off_pax and our_pax_estimate:
        delta = int(our_pax_estimate) - int(off_pax)
        result["delta_pax"] = delta
        result["delta_pax_pct"] = round((delta / off_pax) * 100, 2)

    off_mov = official.get("movimenti")
    if off_mov and our_movements:
        delta = int(our_movements) - int(off_mov)
        result["delta_mov"] = delta
        result["delta_mov_pct"] = round((delta / off_mov) * 100, 2)

    return result


def get_comparison_summary(year, our_pax_estimate, our_movements=None):
    """
    Versione testuale del confronto, per log e report.
    """
    c = get_comparison(year, our_pax_estimate, our_movements)
    if not c["has_official"]:
        return f"Anno {year}: nessun dato ufficiale Assaeroporti disponibile."

    lines = [f"=== Confronto {year} ==="]
    off = c["official"]
    ours = c["ours"]
    lines.append(
        f"  Passeggeri:  noi {ours['passeggeri']:,} | "
        f"ufficiale {off.get('passeggeri', 'N/D'):,} "
        if isinstance(off.get('passeggeri'), int) else
        f"  Passeggeri:  noi {ours['passeggeri']} | ufficiale N/D"
    )
    if "delta_pax" in c:
        segno = "+" if c["delta_pax"] >= 0 else ""
        lines.append(f"  Delta PAX:   {segno}{c['delta_pax']:,} "
                     f"({segno}{c['delta_pax_pct']}%)")
    if our_movements is not None and off.get("movimenti"):
        segno = "+" if c.get("delta_mov", 0) >= 0 else ""
        lines.append(f"  Movimenti:   noi {ours['movimenti']:,} | "
                     f"ufficiale {off['movimenti']:,}")
        lines.append(f"  Delta MOV:   {segno}{c.get('delta_mov', 0):,} "
                     f"({segno}{c.get('delta_mov_pct', 0)}%)")
    lines.append(f"  Fonte:       {off.get('fonte', 'N/D')} "
                 f"({off.get('data_aggiornamento', 'N/D')})")
    return "\n".join(lines)


if __name__ == "__main__":
    print("🧪 Test Assaeroporti...")
    print()
    print("Dati ufficiali 2024:", get_bgy_official_stats(2024))
    print("Dati ufficiali 2025:", get_bgy_official_stats(2025))
    print()
    # Confronto di esempio
    print(get_comparison_summary(2024, our_pax_estimate=17_100_000,
                                  our_movements=118_000))