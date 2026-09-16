"""
bgy_reports/bgy_report_year.py - Report annuale (daily e nightly).
Versione 2.5.0
- doppia lettura: report_monthly_{kind}_YYYY-MM.csv e YYYYMM.csv
- output: report_yearly_{kind}_YYYY.csv + HTML con confronto Assaeroporti
"""
import os
import pandas as pd
from datetime import datetime

from bgy_core import get_logger
from bgy_core.bgy_paths import OUTPUT_CSV_DIR
from bgy_core.bgy_mailer import send_email_with_attachments
from bgy_utils.bgy_utils_assaeroporti import get_comparison

logger = get_logger("ReportYear")


def _find_monthly_files(year, kind):
    """Trova i mensili di un anno (nuovo e vecchio formato)."""
    prefix = f"report_monthly_{kind}_"
    found = []
    if not os.path.isdir(OUTPUT_CSV_DIR):
        return found
    for f in os.listdir(OUTPUT_CSV_DIR):
        if not f.startswith(prefix) or not f.endswith(".csv"):
            continue
        ym = f.replace(prefix, "").replace(".csv", "")
        # Nuovo formato YYYY-MM
        if len(ym) == 7 and ym[4] == "-":
            if ym.startswith(f"{year}-"):
                found.append(os.path.join(OUTPUT_CSV_DIR, f))
        # Vecchio formato YYYYMM
        elif len(ym) == 6 and ym.isdigit():
            if ym.startswith(year):
                found.append(os.path.join(OUTPUT_CSV_DIR, f))
    return sorted(found)


def generate_yearly_report(year=None, kind="daily"):
    if not year:
        year = datetime.now().strftime("%Y")
    year = str(year).strip()

    logger.info(f"📊 Avvio generazione report annuale {kind} per {year}")

    files = _find_monthly_files(year, kind)
    if not files:
        logger.warning(f"⚠️ Nessun dato per l'anno {year} ({kind})")
        return None, None, None

    all_dfs = []
    for f in files:
        try:
            df = pd.read_csv(f)
            if not df.empty:
                all_dfs.append(df)
                logger.info(f"📄 Caricato report mensile: {os.path.basename(f)}")
        except Exception as e:
            logger.warning(f"⚠️ Errore lettura {f}: {e}")

    if not all_dfs:
        logger.warning(f"⚠️ Nessun dato per l'anno {year} ({kind})")
        return None, None, None

    yearly_df = pd.concat(all_dfs, ignore_index=True)
    out_csv = os.path.join(OUTPUT_CSV_DIR, f"report_yearly_{kind}_{year}.csv")
    yearly_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    logger.info(f"💾 CSV annuale {kind} salvato: {out_csv}")
    logger.info(f"📊 Totale voli annuali ({kind}): {len(yearly_df)}")

    html_path = create_yearly_html_report(yearly_df, year, kind)
    return out_csv, html_path, []


def _compute_our_estimates(df):
    our_pax = int(df['stima_passeggeri'].sum()) if 'stima_passeggeri' in df.columns else 0
    our_mov = len(df)
    return our_pax, our_mov


def _build_comparison_html(year, our_pax, our_mov):
    try:
        c = get_comparison(year, our_pax, our_mov)
    except Exception as e:
        logger.warning(f"Confronto Assaeroporti non disponibile: {e}")
        return ""

    if not c.get("has_official"):
        return f"""
<div class="comparison-section" style="background:#fff3cd;border:2px solid #ffc107;padding:20px;border-radius:8px;margin-top:25px;">
<h3>📊 Confronto con dati ufficiali Assaeroporti</h3>
<p><em>Dati ufficiali non ancora disponibili per l'anno {year}.</em></p>
<p>Per inserirli manualmente: <code>bgy_config/config_assaeroporti.json</code></p>
</div>
"""

    off = c["official"]
    delta_pax = c.get("delta_pax", 0)
    delta_pax_pct = c.get("delta_pax_pct", 0)
    segno_pax = "+" if delta_pax >= 0 else ""
    colore_pax = "#27ae60" if abs(delta_pax_pct) < 10 else "#e74c3c"

    rows = f"""
<tr><td><strong>Passeggeri</strong></td>
    <td>{our_pax:,}</td>
    <td>{off.get('passeggeri', 0):,}</td>
    <td style="color:{colore_pax};font-weight:bold;">{segno_pax}{delta_pax:,} ({segno_pax}{delta_pax_pct}%)</td>
</tr>
"""
    if "delta_mov" in c and off.get("movimenti"):
        delta_mov = c.get("delta_mov", 0)
        delta_mov_pct = c.get("delta_mov_pct", 0)
        segno_mov = "+" if delta_mov >= 0 else ""
        rows += f"""
<tr><td><strong>Movimenti</strong></td>
    <td>{our_mov:,}</td>
    <td>{off['movimenti']:,}</td>
    <td>{segno_mov}{delta_mov:,} ({segno_mov}{delta_mov_pct}%)</td>
</tr>
"""
    if off.get("cargo_ton"):
        rows += f"""
<tr><td><strong>Cargo (ton)</strong></td>
    <td>N/D</td>
    <td>{off['cargo_ton']:,}</td>
    <td>—</td>
</tr>
"""

    return f"""
<div class="comparison-section" style="background:white;padding:20px;border-radius:8px;margin-top:25px;box-shadow:0 2px 4px rgba(0,0,0,0.1);">
<h3>📊 Confronto con dati ufficiali Assaeroporti</h3>
<p style="font-size:12px;color:#7f8c8d;">
Fonte: {off.get('fonte', 'N/D')} — aggiornato al {off.get('data_aggiornamento', 'N/D')}
</p>
<table style="width:100%;border-collapse:collapse;margin-top:15px;">
<thead><tr style="background:#1a2a6c;color:white;">
<th style="padding:10px;text-align:left;">Metrica</th>
<th style="padding:10px;text-align:right;">Nostra stima</th>
<th style="padding:10px;text-align:right;">Ufficiale</th>
<th style="padding:10px;text-align:right;">Differenza</th>
</tr></thead>
<tbody>{rows}</tbody>
</table>
<p style="font-size:11px;color:#95a5a6;margin-top:10px;">
Nota: la nostra stima è basata su rilevamenti radar e stima PAX per modello aereo.
Eventuali differenze con il dato ufficiale possono riflettere limiti del metodo.
</p>
</div>
"""


def create_yearly_html_report(df, year, kind="daily"):
    try:
        total_voli = len(df)
        compagnie = df['compagnia_aerea'].nunique() if 'compagnia_aerea' in df.columns else 0
        if 'destinazione_finale' in df.columns:
            destinazioni = df['destinazione_finale'].nunique()
        elif 'destinazione_origine' in df.columns:
            destinazioni = df['destinazione_origine'].nunique()
        else:
            destinazioni = 0
        if 'minuti_ritardo' in df.columns:
            ritardi = len(df[df['minuti_ritardo'] > 15])
            in_orario = len(df[df['minuti_ritardo'] <= 15])
            ritardo_medio = df['minuti_ritardo'].mean()
        else:
            ritardi = 0
            in_orario = total_voli
            ritardo_medio = 0
        now = datetime.now()
        tipo_label = "Giornaliero" if kind == "daily" else "Notturno"

        our_pax, our_mov = _compute_our_estimates(df)
        comparison_html = _build_comparison_html(year, our_pax, our_mov)

        html_content = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>Report Annuale {tipo_label} BGY - {year}</title>
<style>
body {{ font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #333;
        max-width: 1000px; margin: 0 auto; padding: 20px; background: #f5f7fa; }}
.header {{ background: linear-gradient(135deg, #1a2a6c, #b21f1f, #fdbb2d);
           color: white; padding: 30px; border-radius: 12px;
           text-align: center; margin-bottom: 25px; }}
.header h1 {{ margin: 0; font-size: 28px; letter-spacing: 2px; }}
.header .subtitle {{ font-size: 14px; opacity: 0.85; margin-top: 5px; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
               gap: 15px; margin-bottom: 25px; }}
.stat-card {{ background: white; padding: 15px; border-radius: 8px;
              box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }}
.stat-card .value {{ font-size: 24px; font-weight: bold; color: #1a2a6c; }}
.stat-card .label {{ font-size: 12px; color: #7f8c8d; margin-top: 5px; }}
table {{ width: 100%; border-collapse: collapse; background: white;
         border-radius: 8px; overflow: hidden;
         box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-top: 20px; }}
th {{ background: #1a2a6c; color: white; padding: 12px; text-align: left; }}
td {{ padding: 10px 12px; border-bottom: 1px solid #eee; }}
.footer {{ text-align: center; font-size: 12px; color: #95a5a6;
           margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; }}
</style></head><body>
<div class="header">
<h1>📈 Report Annuale {tipo_label} BGY - {year}</h1>
<div class="subtitle">Aeroporto di Bergamo - Orio al Serio (BGY)</div>
<div class="subtitle">Anno: {year}</div>
</div>
<div class="stats-grid">
<div class="stat-card"><div class="value">{total_voli}</div><div class="label">Totale Voli</div></div>
<div class="stat-card"><div class="value">{compagnie}</div><div class="label">Compagnie</div></div>
<div class="stat-card"><div class="value">{destinazioni}</div><div class="label">Destinazioni</div></div>
<div class="stat-card"><div class="value">{ritardi}</div><div class="label">Voli in Ritardo</div></div>
<div class="stat-card"><div class="value">{in_orario}</div><div class="label">Voli in Orario</div></div>
<div class="stat-card"><div class="value">{ritardo_medio:.1f} min</div><div class="label">Ritardo Medio</div></div>
</div>
<h2>📋 Dettaglio Voli Annuale ({tipo_label})</h2>
<p><em>Primi 100 voli visualizzati</em></p>
"""
        cols_to_show = ['volo', 'callsign', 'tipo_movimento', 'compagnia_aerea',
                        'destinazione_origine', 'destinazione_finale',
                        'orario_schedulato', 'minuti_ritardo', 'stato_ritardo']
        cols = [c for c in cols_to_show if c in df.columns]
        html_content += "<table><thead><tr>"
        for col in cols:
            html_content += f"<th>{col.replace('_', ' ').capitalize()}</th>"
        html_content += "</tr></thead><tbody>"
        for _, row in df.head(100).iterrows():
            html_content += "<tr>"
            for col in cols:
                val = row[col] if col in row else ""
                html_content += f"<td>{val if pd.notna(val) else ''}</td>"
            html_content += "</tr>"
        html_content += "</tbody></table>"
        if len(df) > 100:
            html_content += f"<p><em>... e altri {len(df) - 100} voli</em></p>"

        html_content += comparison_html

        html_content += f"""
<div class="footer">
<p>Report generato automaticamente il {now.strftime('%d/%m/%Y %H:%M')}</p>
<p>Dati elaborati da fonti pubbliche (SACBO e OpenSky Network)</p>
<p>BGY Monitoring Suite v2.5.0</p>
</div>
</body></html>"""
        html_path = os.path.join(OUTPUT_CSV_DIR, f"report_yearly_{kind}_{year}.html")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"📄 Report HTML annuale {kind} salvato: {html_path}")
        return html_path
    except Exception as e:
        logger.error(f"❌ Errore creazione HTML annuale: {e}")
        return None


def send_yearly_report(year=None, kind="daily"):
    if not year:
        year = datetime.now().strftime("%Y")
    logger.info(f"📧 Invio report annuale {kind} per {year}")
    csv_path, html_path, charts = generate_yearly_report(year, kind)
    if not csv_path:
        logger.warning(f"⚠️ Nessun dato per il report annuale {kind} di {year}")
        return False
    attachments = [csv_path]
    if html_path and os.path.exists(html_path):
        attachments.append(html_path)
    subject = f"📊 Report Annuale {kind.capitalize()} BGY - {year}"
    success = send_email_with_attachments(attachments, subject=subject)
    if success:
        logger.info(f"✅ Report annuale {kind} inviato con {len(attachments)} allegati")
    else:
        logger.error(f"❌ Errore invio report annuale {kind}")
    return success


if __name__ == "__main__":
    send_yearly_report()