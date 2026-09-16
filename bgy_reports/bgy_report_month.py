"""
bgy_reports/bgy_report_month.py - Report mensile con grafici.
Versione 2.5.0
- doppia lettura: report_{daily,nightly}_YYYY-MM-DD.csv e YYYYMMDD.csv
- output: report_monthly_{daily,nightly}_YYYY-MM.csv
- grafici incorporati in base64 nel report HTML
"""
import os
import base64
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import numpy as np

from bgy_core import get_logger
from bgy_core.bgy_paths import OUTPUT_CSV_DIR, CHARTS_DIR
from bgy_core.bgy_mailer import send_email_with_attachments
from bgy_core.bgy_dates import (
    normalize_date, report_monthly_filename, to_year_month,
)

logger = get_logger("ReportMonth")
os.makedirs(CHARTS_DIR, exist_ok=True)


def _is_current_month(year_month):
    return year_month == datetime.now().strftime("%Y-%m")


def _month_label(year_month):
    mesi = ["", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
    try:
        ym = str(year_month).replace("-", "")
        y = int(ym[:4])
        m = int(ym[4:6])
        return f"{mesi[m]} {y}"
    except Exception:
        return year_month


def _get_file_prefix(report_type):
    return "report_daily_" if report_type == 'daily' else "report_nightly_"


def _extract_date_from_report(filename, prefix):
    """Estrae YYYY-MM-DD da report_{daily,nightly}_XXX.csv, accetta nuovo e vecchio."""
    base = filename.replace(prefix, "").replace(".csv", "")
    if len(base) == 10 and base[4] == "-" and base[7] == "-":
        return base
    if len(base) == 8 and base.isdigit():
        return f"{base[:4]}-{base[4:6]}-{base[6:8]}"
    return None


def _find_monthly_files(year_month, report_type):
    """Trova i file report giornalieri del mese (nuovo e vecchio formato)."""
    prefix = _get_file_prefix(report_type)
    found = []
    if not os.path.isdir(OUTPUT_CSV_DIR):
        return found
    for f in os.listdir(OUTPUT_CSV_DIR):
        if not f.startswith(prefix) or not f.endswith(".csv"):
            continue
        date_str = _extract_date_from_report(f, prefix)
        if not date_str:
            continue
        if date_str.startswith(year_month):
            found.append((date_str, os.path.join(OUTPUT_CSV_DIR, f)))
    found.sort()
    return found


# -----------------------------------------------------------------------------
# GRAFICI
# -----------------------------------------------------------------------------

def create_daily_flights_chart(df, year_month, report_type='daily'):
    try:
        if 'data_report' not in df.columns or df.empty:
            return None
        daily_counts = df.groupby('data_report').size().reset_index(name='totale_voli')
        fig, ax = plt.subplots(figsize=(12, 6))
        color = '#3498db' if report_type == 'daily' else '#8e44ad'
        ax.bar(daily_counts['data_report'], daily_counts['totale_voli'],
               color=color, alpha=0.8, edgecolor='white')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
        titolo = "Andamento Voli Giornalieri" if report_type == 'daily' else "Andamento Voli Notturni"
        ax.set_title(f'{titolo} - {_month_label(year_month)}', fontsize=14, fontweight='bold')
        ax.set_xlabel('Data', fontsize=12)
        ax.set_ylabel('Numero Voli', fontsize=12)
        ax.grid(axis='y', alpha=0.3)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        chart_path = os.path.join(CHARTS_DIR, f"daily_flights_{report_type}_{year_month}.png")
        plt.savefig(chart_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        logger.info(f"📈 Grafico voli salvato: {chart_path}")
        return chart_path
    except Exception as e:
        logger.error(f"❌ Errore grafico voli: {e}")
        return None


def create_daily_delays_chart(df, year_month, report_type='daily'):
    try:
        if df.empty:
            return None
        if report_type == 'daily':
            if 'minuti_ritardo' not in df.columns:
                return None
            delay_df = df[df['minuti_ritardo'].notna()].copy()
            if delay_df.empty:
                return None
            daily_delays = delay_df.groupby('data_report').agg({
                'minuti_ritardo': ['mean', 'count']
            }).reset_index()
            daily_delays.columns = ['data_report', 'ritardo_medio', 'totale_voli']
            fig, ax = plt.subplots(figsize=(12, 6))
            colors = ['#e74c3c' if x > 15 else '#f39c12' if x > 5 else '#2ecc71'
                      for x in daily_delays['ritardo_medio']]
            ax.bar(daily_delays['data_report'], daily_delays['ritardo_medio'],
                   color=colors, alpha=0.8, edgecolor='white')
            ax.axhline(y=15, color='#e74c3c', linestyle='--', linewidth=2,
                       label='Soglia ritardo (15 min)')
            ax.set_title(f'Ritardi Medi Giornalieri - {_month_label(year_month)}',
                         fontsize=14, fontweight='bold')
            ax.set_xlabel('Data'); ax.set_ylabel('Ritardo Medio (minuti)')
            ax.legend(); ax.grid(axis='y', alpha=0.3)
        else:
            if 'fase_volo' not in df.columns:
                return None
            pivot = df.groupby(['data_report', 'fase_volo']).size().unstack(fill_value=0)
            if pivot.empty:
                return None
            fig, ax = plt.subplots(figsize=(12, 6))
            bottom = None
            colori = {'Atterraggio': '#3498db', 'Decollo': '#e67e22',
                      'Avvicinamento': '#9b59b6', 'Sorvolo': '#95a5a6',
                      'Non rilevato': '#bdc3c7'}
            for fase in pivot.columns:
                vals = pivot[fase].values
                ax.bar(pivot.index, vals, bottom=bottom,
                       label=fase, color=colori.get(fase, '#7f8c8d'),
                       alpha=0.85, edgecolor='white')
                bottom = vals if bottom is None else bottom + vals
            ax.set_title(f'Distribuzione Fasi di Volo - {_month_label(year_month)}',
                         fontsize=14, fontweight='bold')
            ax.set_xlabel('Data'); ax.set_ylabel('Numero Voli')
            ax.legend(); ax.grid(axis='y', alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        chart_path = os.path.join(CHARTS_DIR, f"daily_delays_{report_type}_{year_month}.png")
        plt.savefig(chart_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        logger.info(f"📈 Grafico ritardi/fasi salvato: {chart_path}")
        return chart_path
    except Exception as e:
        logger.error(f"❌ Errore grafico ritardi/fasi: {e}")
        return None


def create_airlines_chart(df, year_month, report_type='daily'):
    try:
        if df.empty or 'compagnia_aerea' not in df.columns:
            return None
        airline_counts = df['compagnia_aerea'].value_counts().head(10)
        fig, ax = plt.subplots(figsize=(10, 6))
        cmap = plt.cm.Blues if report_type == 'daily' else plt.cm.Purples
        colors = cmap(np.linspace(0.4, 0.9, len(airline_counts)))[::-1]
        bars = ax.barh(airline_counts.index, airline_counts.values,
                       color=colors, edgecolor='white')
        for bar, value in zip(bars, airline_counts.values):
            ax.text(value + 0.5, bar.get_y() + bar.get_height()/2,
                    str(value), va='center', fontsize=10, fontweight='bold')
        tipo = "Compagnie Aeree" if report_type == 'daily' else "Compagnie Aeree (Notturno)"
        ax.set_title(f'Top 10 {tipo} - {_month_label(year_month)}',
                     fontsize=14, fontweight='bold')
        ax.set_xlabel('Numero Voli'); ax.set_ylabel('Compagnia')
        ax.grid(axis='x', alpha=0.3)
        plt.tight_layout()
        chart_path = os.path.join(CHARTS_DIR, f"airlines_{report_type}_{year_month}.png")
        plt.savefig(chart_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        logger.info(f"📈 Grafico compagnie salvato: {chart_path}")
        return chart_path
    except Exception as e:
        logger.error(f"❌ Errore grafico compagnie: {e}")
        return None


def create_destinations_chart(df, year_month, report_type='daily'):
    try:
        if df.empty:
            return None
        if report_type == 'daily' and 'destinazione_origine' in df.columns:
            col = 'destinazione_origine'
        elif 'destinazione_finale' in df.columns:
            col = 'destinazione_finale'
        elif 'destinazione_origine' in df.columns:
            col = 'destinazione_origine'
        else:
            return None
        dest_counts = df[col].value_counts().head(10)
        if dest_counts.empty:
            return None
        fig, ax = plt.subplots(figsize=(10, 6))
        cmap = plt.cm.Oranges if report_type == 'daily' else plt.cm.Reds
        colors = cmap(np.linspace(0.3, 0.9, len(dest_counts)))[::-1]
        bars = ax.barh(dest_counts.index, dest_counts.values,
                       color=colors, edgecolor='white')
        for bar, value in zip(bars, dest_counts.values):
            ax.text(value + 0.5, bar.get_y() + bar.get_height()/2,
                    str(value), va='center', fontsize=10, fontweight='bold')
        ax.set_title(f'Top 10 Destinazioni - {_month_label(year_month)}',
                     fontsize=14, fontweight='bold')
        ax.set_xlabel('Numero Voli'); ax.set_ylabel('Destinazione')
        ax.grid(axis='x', alpha=0.3)
        plt.tight_layout()
        chart_path = os.path.join(CHARTS_DIR, f"destinations_{report_type}_{year_month}.png")
        plt.savefig(chart_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        logger.info(f"📈 Grafico destinazioni salvato: {chart_path}")
        return chart_path
    except Exception as e:
        logger.error(f"❌ Errore grafico destinazioni: {e}")
        return None


# -----------------------------------------------------------------------------
# HTML
# -----------------------------------------------------------------------------

def _chart_to_base64(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return None


def create_html_report(df, year_month, chart_paths, report_type='daily',
                       is_partial=False, days_with_data=0):
    try:
        total_voli = len(df)
        compagnie = df['compagnia_aerea'].nunique() if 'compagnia_aerea' in df.columns else 0
        if report_type == 'daily' and 'destinazione_origine' in df.columns:
            destinazioni = df['destinazione_origine'].nunique()
        elif 'destinazione_finale' in df.columns:
            destinazioni = df['destinazione_finale'].nunique()
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
        tipo_label = "Giornaliero" if report_type == 'daily' else "Notturno"

        partial_banner = ""
        if is_partial:
            partial_banner = f"""
    <div class="partial-banner">
        <strong>⚠️ MESE IN CORSO</strong><br>
        Il report copre dal 1° {_month_label(year_month)} all'ultimo giorno con dati disponibili
        ({days_with_data} giorni su {datetime.now().day}).
        Il report è da considerarsi <strong>parziale</strong> e verrà completato alla fine del mese.
    </div>
"""

        html_content = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>Report Mensile {tipo_label} BGY - {_month_label(year_month)}</title>
<style>
body {{ font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #333;
        max-width: 1000px; margin: 0 auto; padding: 20px; background: #f5f7fa; }}
.header {{ background: linear-gradient(135deg, #1a2a6c, #b21f1f, #fdbb2d);
           color: white; padding: 30px; border-radius: 12px;
           text-align: center; margin-bottom: 25px; }}
.header h1 {{ margin: 0; font-size: 28px; letter-spacing: 2px; }}
.header .subtitle {{ font-size: 14px; opacity: 0.85; margin-top: 5px; }}
.partial-banner {{ background: #fff3cd; border: 2px solid #ffc107;
                   color: #856404; padding: 15px 20px; border-radius: 8px;
                   margin-bottom: 20px; text-align: center; font-size: 14px; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
               gap: 15px; margin-bottom: 25px; }}
.stat-card {{ background: white; padding: 15px; border-radius: 8px;
              box-shadow: 0 2px 4px rgba(0,0,0,0.1); text-align: center; }}
.stat-card .value {{ font-size: 24px; font-weight: bold; color: #1a2a6c; }}
.stat-card .label {{ font-size: 12px; color: #7f8c8d; margin-top: 5px; }}
.chart-container {{ background: white; padding: 20px; border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    margin-bottom: 20px; text-align: center; }}
.chart-container img {{ max-width: 100%; height: auto; border-radius: 4px; }}
.footer {{ text-align: center; font-size: 12px; color: #95a5a6;
           margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; }}
</style>
</head>
<body>
<div class="header">
<h1>✈️ Report Mensile {tipo_label} BGY</h1>
<div class="subtitle">Aeroporto di Bergamo - Orio al Serio (BGY)</div>
<div class="subtitle">Periodo: {_month_label(year_month)}</div>
</div>
{partial_banner}
<div class="stats-grid">
<div class="stat-card"><div class="value">{total_voli}</div><div class="label">Totale Voli</div></div>
<div class="stat-card"><div class="value">{compagnie}</div><div class="label">Compagnie</div></div>
<div class="stat-card"><div class="value">{destinazioni}</div><div class="label">Destinazioni</div></div>
<div class="stat-card"><div class="value">{ritardi}</div><div class="label">Voli in Ritardo</div></div>
<div class="stat-card"><div class="value">{in_orario}</div><div class="label">Voli in Orario</div></div>
<div class="stat-card"><div class="value">{ritardo_medio:.1f} min</div><div class="label">Ritardo Medio</div></div>
</div>
"""
        for chart_path in chart_paths:
            if chart_path and os.path.exists(chart_path):
                chart_name = os.path.basename(chart_path).replace('.png', '').replace('_', ' ').title()
                b64 = _chart_to_base64(chart_path)
                if b64:
                    img_tag = f'<img src="data:image/png;base64,{b64}" alt="{chart_name}">'
                else:
                    img_tag = f'<em>Grafico non disponibile: {chart_name}</em>'
                html_content += f"""
<div class="chart-container">
<h3>{chart_name}</h3>
{img_tag}
</div>
"""

        html_content += f"""
<div class="footer">
<p>Report generato automaticamente il {now.strftime('%d/%m/%Y %H:%M')}</p>
<p>Dati elaborati da fonti pubbliche (SACBO e OpenSky Network)</p>
<p>BGY Monitoring Suite v2.5.0</p>
</div>
</body></html>"""

        html_path = os.path.join(
            OUTPUT_CSV_DIR, f"report_monthly_{report_type}_{year_month}.html")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"📄 Report HTML salvato: {html_path}")
        return html_path
    except Exception as e:
        logger.error(f"❌ Errore creazione HTML: {e}")
        return None


# -----------------------------------------------------------------------------
# GENERAZIONE
# -----------------------------------------------------------------------------

def generate_month_report(year_month=None, report_type='daily'):
    if not year_month:
        year_month = datetime.now().strftime("%Y-%m")
    # Normalizza: accetta 'YYYYMM' o 'YYYY-MM'
    ym = str(year_month).strip()
    if len(ym) == 6 and ym.isdigit():
        ym = f"{ym[:4]}-{ym[4:6]}"
    year_month = ym

    is_partial = _is_current_month(year_month)
    tipo_label = "Giornaliero" if report_type == 'daily' else "Notturno"

    logger.info(f"📊 Avvio generazione report mensile {tipo_label} per {year_month}"
                + (" [MESE IN CORSO - parziale]" if is_partial else ""))

    found = _find_monthly_files(year_month, report_type)
    if not found:
        logger.warning(f"⚠️ Nessun report {tipo_label} trovato per il mese {year_month}")
        return None, None, None

    days_with_data = len(found)
    logger.info(f"📄 Trovati {len(found)} report (giorni disponibili: {days_with_data})")

    dfs = []
    for date_str, filepath in found:
        try:
            df = pd.read_csv(filepath)
            if not df.empty:
                df['data_report'] = pd.to_datetime(date_str, format='%Y-%m-%d')
                dfs.append(df)
        except Exception as e:
            logger.warning(f"⚠️ Errore lettura {filepath}: {e}")

    if not dfs:
        logger.error("❌ Nessun dato valido trovato")
        return None, None, None

    monthly_df = pd.concat(dfs, ignore_index=True)
    logger.info(f"📊 Totale voli mensili ({tipo_label}): {len(monthly_df)}")

    charts = []
    for create_fn in (create_daily_flights_chart, create_daily_delays_chart,
                      create_airlines_chart, create_destinations_chart):
        c = create_fn(monthly_df, year_month, report_type)
        if c:
            charts.append(c)

    out_csv = os.path.join(
        OUTPUT_CSV_DIR, f"report_monthly_{report_type}_{year_month}.csv")
    monthly_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    logger.info(f"💾 CSV mensile salvato: {out_csv}")

    html_path = create_html_report(monthly_df, year_month, charts, report_type,
                                    is_partial=is_partial, days_with_data=days_with_data)
    return out_csv, html_path, charts


def send_monthly_report(year_month=None, report_type='daily'):
    if not year_month:
        year_month = datetime.now().strftime("%Y-%m")
    tipo_label = "Giornaliero" if report_type == 'daily' else "Notturno"
    logger.info(f"📧 Invio report mensile {tipo_label} per {year_month}")

    csv_path, html_path, charts = generate_month_report(year_month, report_type)
    if not csv_path:
        logger.warning(f"⚠️ Nessun dato per il report mensile {tipo_label} di {year_month}")
        return False

    attachments = [csv_path]
    if html_path and os.path.exists(html_path):
        attachments.append(html_path)
    for chart in charts:
        if chart and os.path.exists(chart):
            attachments.append(chart)

    subject = f"📊 Report Mensile {tipo_label} BGY - {_month_label(year_month)}"
    success = send_email_with_attachments(attachments, subject=subject)
    if success:
        logger.info(f"✅ Report mensile {tipo_label} inviato ({len(attachments)} allegati)")
    else:
        logger.error("❌ Errore invio report mensile")
    return success


if __name__ == "__main__":
    send_monthly_report()