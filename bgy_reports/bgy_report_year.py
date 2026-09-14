"""
bgy_reports/bgy_report_year.py - Report annuale.
"""
import os
import pandas as pd
from datetime import datetime

from core import get_airline, get_country, load_rules, get_logger
from core.bgy_paths import REPORTS_CSV_DIR
from bgy_utils.bgy_utils_mailer import send_email_with_attachments

logger = get_logger("ReportYear")


def generate_yearly_report(year=None):
    if not year:
        year = datetime.now().strftime("%Y")
    
    logger.info(f"📊 Avvio generazione report annuale per {year}")
    
    all_dfs = []
    for month in range(1, 13):
        month_str = f"{year}{str(month).zfill(2)}"
        monthly_file = os.path.join(REPORTS_CSV_DIR, f"report_monthly_{month_str}.csv")
        if os.path.exists(monthly_file):
            try:
                df = pd.read_csv(monthly_file)
                if not df.empty:
                    all_dfs.append(df)
                    logger.info(f"📄 Caricato report mensile: {month_str}")
            except Exception as e:
                logger.warning(f"⚠️ Errore lettura {monthly_file}: {e}")
    
    if not all_dfs:
        logger.warning(f"⚠️ Nessun dato per l'anno {year}")
        return None, None, None
    
    yearly_df = pd.concat(all_dfs, ignore_index=True)
    yearly_csv = os.path.join(REPORTS_CSV_DIR, f"report_yearly_{year}.csv")
    yearly_df.to_csv(yearly_csv, index=False, encoding="utf-8-sig")
    logger.info(f"💾 CSV annuale salvato: {yearly_csv}")
    logger.info(f"📊 Totale voli annuali: {len(yearly_df)}")
    
    if 'minuti_ritardo' in yearly_df.columns:
        ritardi = len(yearly_df[yearly_df['minuti_ritardo'] > 15])
        in_orario = len(yearly_df[yearly_df['minuti_ritardo'] <= 15])
        ritardo_medio = yearly_df['minuti_ritardo'].mean()
        logger.info(f"📊 Statistiche annuali:")
        logger.info(f"   - Voli in Ritardo (>15m): {ritardi}")
        logger.info(f"   - Voli in Orario: {in_orario}")
        logger.info(f"   - Ritardo Medio: {ritardo_medio:.1f} min")
    
    html_path = create_yearly_html_report(yearly_df, year)
    
    return yearly_csv, html_path, []


def create_yearly_html_report(df, year):
    try:
        total_voli = len(df)
        compagnie = df['compagnia_aerea'].nunique() if 'compagnia_aerea' in df.columns else 0
        destinazioni = df['destinazione_origine'].nunique() if 'destinazione_origine' in df.columns else 0
        
        if 'minuti_ritardo' in df.columns:
            ritardi = len(df[df['minuti_ritardo'] > 15])
            in_orario = len(df[df['minuti_ritardo'] <= 15])
            ritardo_medio = df['minuti_ritardo'].mean()
        else:
            ritardi = 0
            in_orario = total_voli
            ritardo_medio = 0
        
        now = datetime.now()
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Report Annuale BGY - {year}</title>
    <style>
        body {{
            font-family: Arial, Helvetica, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f7fa;
        }}
        .header {{
            background: linear-gradient(135deg, #1a2a6c, #b21f1f, #fdbb2d);
            color: white;
            padding: 30px;
            border-radius: 12px;
            text-align: center;
            margin-bottom: 25px;
        }}
        .header h1 {{ margin: 0; font-size: 28px; letter-spacing: 2px; }}
        .header .subtitle {{ font-size: 14px; opacity: 0.85; margin-top: 5px; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }}
        .stat-card {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .stat-card .value {{ font-size: 24px; font-weight: bold; color: #1a2a6c; }}
        .stat-card .label {{ font-size: 12px; color: #7f8c8d; margin-top: 5px; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-top: 20px;
        }}
        th {{
            background: #1a2a6c;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #eee;
        }}
        tr:hover {{ background: #f0f4f8; }}
        .footer {{
            text-align: center;
            font-size: 12px;
            color: #95a5a6;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📈 Report Annuale BGY - {year}</h1>
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
    
    <h2>📋 Dettaglio Voli Annuale</h2>
    <p><em>Primi 100 voli visualizzati</em></p>
"""
        
        cols_to_show = ['volo', 'callsign', 'tipo_movimento', 'compagnia_aerea', 
                        'destinazione_origine', 'orario_schedulato', 'minuti_ritardo', 'stato_ritardo']
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
        
        html_content += f"""
    <div class="footer">
        <p>Report generato automaticamente il {now.strftime('%d/%m/%Y %H:%M')}</p>
        <p>Dati elaborati da fonti pubbliche (SACBO e OpenSky Network)</p>
        <p>BGY Monitoring Suite v2.2</p>
    </div>
</body>
</html>
"""
        
        html_path = os.path.join(REPORTS_CSV_DIR, f"report_yearly_{year}.html")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"📄 Report HTML annuale salvato: {html_path}")
        return html_path
        
    except Exception as e:
        logger.error(f"❌ Errore creazione HTML annuale: {e}")
        return None


def send_yearly_report(year=None):
    if not year:
        year = datetime.now().strftime("%Y")
    
    logger.info(f"📧 Invio report annuale per {year}")
    
    csv_path, html_path, charts = generate_yearly_report(year)
    
    if not csv_path:
        logger.warning(f"⚠️ Nessun dato per il report annuale di {year}")
        return False
    
    attachments = [csv_path]
    if html_path and os.path.exists(html_path):
        attachments.append(html_path)
    
    subject = f"📊 Report Annuale BGY - {year}"
    success = send_email_with_attachments(attachments, subject=subject)
    
    if success:
        logger.info(f"✅ Report annuale inviato con {len(attachments)} allegati")
    else:
        logger.error("❌ Errore invio report annuale")
    
    return success


if __name__ == "__main__":
    send_yearly_report()