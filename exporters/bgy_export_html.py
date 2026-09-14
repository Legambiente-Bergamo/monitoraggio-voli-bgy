"""
exporters/bgy_export_html.py - Esporta report in formato HTML (.html)
"""
import os
import pandas as pd
from datetime import datetime

from core.bgy_logger import get_logger  # <-- CORRETTO
from core.bgy_paths import REPORTS_HTML_DIR

logger = get_logger("ExportHTML")
os.makedirs(REPORTS_HTML_DIR, exist_ok=True)


def export_to_html(df, report_type, date_str=None):
    """
    Esporta un DataFrame in formato HTML (.html)
    """
    if df.empty:
        logger.warning("⚠️ DataFrame vuoto, nessun file creato")
        return None
    
    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")
    
    # Statistiche
    stats = [("Totale Voli", len(df))]
    
    if 'tipo_movimento' in df.columns:
        atterraggi = len(df[df['tipo_movimento'].str.contains('Atterraggio|A', na=False)])
        decolli = len(df[df['tipo_movimento'].str.contains('Decollo|D', na=False)])
        stats.append(("Atterraggi", atterraggi))
        stats.append(("Decolli", decolli))
    
    if 'minuti_ritardo' in df.columns:
        ritardi = len(df[df['minuti_ritardo'] > 15])
        in_orario = len(df[df['minuti_ritardo'] <= 15])
        ritardo_medio = df['minuti_ritardo'].mean()
        stats.append(("Voli in Ritardo (>15m)", ritardi))
        stats.append(("Voli in Orario", in_orario))
        stats.append(("Ritardo Medio (min)", f"{ritardo_medio:.1f}"))
    
    # Colonne da mostrare
    cols_to_show = ['volo', 'callsign', 'tipo_movimento', 'compagnia_aerea', 
                    'destinazione_origine', 'orario_schedulato', 'orario_effettivo', 
                    'minuti_ritardo', 'stato_ritardo']
    cols = [c for c in cols_to_show if c in df.columns]
    
    # Crea tabella HTML
    max_rows = min(100, len(df))
    table_rows = ""
    for idx in range(max_rows):
        row = "<tr>"
        for col in cols:
            val = df.iloc[idx][col] if col in df.columns else ""
            row += f"<td>{val if pd.notna(val) else ''}</td>"
        row += "</tr>"
        table_rows += row
    
    now = datetime.now()
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Report {report_type.capitalize()} Voli BGY</title>
    <style>
        body {{
            font-family: Arial, Helvetica, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
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
        <h1>✈️ Report {report_type.capitalize()} Voli BGY</h1>
        <div class="subtitle">Aeroporto di Bergamo - Orio al Serio (BGY)</div>
        <div class="subtitle">Generato il {now.strftime('%d/%m/%Y %H:%M')}</div>
    </div>
    
    <div class="stats-grid">
"""
    
    for label, value in stats:
        html_content += f"""
        <div class="stat-card">
            <div class="value">{value}</div>
            <div class="label">{label}</div>
        </div>
"""
    
    html_content += f"""
    </div>
    
    <h2>Dettaglio Voli</h2>
    <table>
        <thead>
            <tr>
"""
    
    for col in cols:
        html_content += f"<th>{col.replace('_', ' ').capitalize()}</th>"
    
    html_content += f"""
            </tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
    </table>
"""
    
    if len(df) > 100:
        html_content += f"<p><em>... e altri {len(df) - 100} voli</em></p>"
    
    html_content += f"""
    <div class="footer">
        <p>Report generato automaticamente da BGY Monitoring Suite</p>
        <p>Dati elaborati da fonti pubbliche (SACBO e OpenSky Network)</p>
    </div>
</body>
</html>
"""
    
    filename = f"report_{report_type}_{date_str}.html"
    filepath = os.path.join(REPORTS_HTML_DIR, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    logger.info(f"📄 Report HTML salvato: {filepath}")
    return filepath


def export_daily_html(df, date_str=None):
    return export_to_html(df, "daily", date_str)


def export_nightly_html(df, date_str=None):
    return export_to_html(df, "nightly", date_str)


def export_monthly_html(df, date_str=None):
    return export_to_html(df, "monthly", date_str)


if __name__ == "__main__":
    test_df = pd.DataFrame({
        'volo': ['FR123', 'WZ456'],
        'compagnia_aerea': ['Ryanair', 'Wizz Air'],
        'destinazione_origine': ['Londra', 'Parigi']
    })
    export_to_html(test_df, "daily", "20260828")