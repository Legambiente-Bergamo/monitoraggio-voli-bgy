"""
Test di accesso a SACBO con Playwright Stealth + rimozione overlay.
Verifica se il tab "Arrivi" è cliccabile e se i voli sono davvero diversi
dalle partenze.
"""
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import re
import time

URL = "https://www.milanbergamoairport.it/it/voli-tempo-reale/"


def dismiss_overlays(page):
    removed = page.evaluate("""
        () => {
            let count = 0;
            const selectors = [
                '#iubenda-cs-banner', '.iubenda-cs-banner',
                '#alert-popup', '.modal-backdrop',
                '.modal.show', '.modal.fade.in',
            ];
            for (const sel of selectors) {
                document.querySelectorAll(sel).forEach(el => { el.remove(); count++; });
            }
            document.body.classList.remove('modal-open');
            document.body.style.overflow = '';
            document.body.style.paddingRight = '';
            return count;
        }
    """)
    return removed


def extract_callsigns(text, max_n=20):
    """Estrae pattern di callsign tipo 'FR 1234', 'W6 5678', 'RYR7HH'."""
    # Pattern: 2-4 caratteri alfanumerici + numero (opzionale) + eventuali altri
    patterns = re.findall(r'\b([A-Z][A-Z0-9]{1,3}\s?\d{1,4})\b', text)
    # Deduplica mantenendo l'ordine
    seen = set()
    result = []
    for p in patterns:
        key = p.strip().upper()
        if key not in seen:
            seen.add(key)
            result.append(p.strip())
        if len(result) >= max_n:
            break
    return result


with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )
    context = browser.new_context(
        viewport={"width": 1366, "height": 768},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        locale="it-IT",
        timezone_id="Europe/Rome",
    )
    page = context.new_page()

    stealth = Stealth()
    stealth.apply_stealth_sync(page)

    print("Navigazione verso SACBO...")
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)

    # Attesa challenge Cloudflare
    for i in range(15):
        title = page.title()
        if "Just a moment" not in title and "Attention" not in title:
            print(f"✅ Challenge superato dopo {i+1}s. Titolo: {title}")
            break
        print(f"⏳ Attesa challenge... ({i+1}s)")
        time.sleep(1)
    else:
        print("❌ Challenge Cloudflare non superato")
        browser.close()
        exit(1)

    page.wait_for_timeout(3000)
    dismiss_overlays(page)
    page.wait_for_timeout(1000)

    # === Estrai callsign dalla tab "Partenze" (default) ===
    print("\n=== TAB PARTENZE (default) ===")
    text_dep = page.inner_text("body")
    callsigns_dep = extract_callsigns(text_dep)
    print(f"Callsign trovati: {len(callsigns_dep)}")
    print(f"Primi 10: {callsigns_dep[:10]}")

    # === Click su tab "Arrivi" ===
    print("\n=== Click su tab 'Arrivi' ===")
    tab = page.locator("[role='tab']:has-text('Arrivi')").first
    tab.wait_for(state="visible", timeout=5000)
    tab.click(timeout=10000)
    print("  ✅ Click eseguito")
    page.wait_for_timeout(3000)

    # === Verifica tab attivo ===
    print("\n=== Verifica contenuto tab ===")
    active_tab = page.evaluate("""
        () => {
            const el = document.querySelector('a[role="tab"].active, a[role="tab"][aria-selected="true"]');
            if (!el) return 'nessuno';
            return el.textContent.trim() + ' | class=' + el.className;
        }
    """)
    print(f"Tab attivo: {active_tab}")

    # === Estrai callsign dalla tab "Arrivi" ===
    text_arr = page.inner_text("body")
    callsigns_arr = extract_callsigns(text_arr)
    print(f"Callsign trovati: {len(callsigns_arr)}")
    print(f"Primi 10: {callsigns_arr[:10]}")

    # === Confronto ===
    print("\n=== Confronto D vs A ===")
    set_dep = set(c.upper() for c in callsigns_dep)
    set_arr = set(c.upper() for c in callsigns_arr)
    comuni = set_dep & set_arr
    solo_dep = set_dep - set_arr
    solo_arr = set_arr - set_dep
    print(f"Unici in Partenze: {len(set_dep)}")
    print(f"Unici in Arrivi:   {len(set_arr)}")
    print(f"In entrambi:       {len(comuni)}")
    print(f"Solo Partenze:     {len(solo_dep)}")
    print(f"Solo Arrivi:       {len(solo_arr)}")

    if len(solo_arr) > 0:
        print("\n✅ SUCCESSO: i due tab hanno contenuti diversi.")
        print("   Il fix funziona: gli arrivi sono catturati correttamente.")
    else:
        print("\n❌ PROBLEMA: i due tab hanno gli stessi callsign.")
        print("   Il click non ha cambiato il contenuto.")

    # Salva HTML per ispezione
    with open("sacbo_after_click.html", "w", encoding="utf-8") as f:
        f.write(page.content())

    print("\nAspetto 10 secondi per ispezione manuale...")
    page.wait_for_timeout(10000)
    browser.close()