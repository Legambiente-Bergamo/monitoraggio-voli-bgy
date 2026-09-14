"""
exporters/bgy_export_pdf.py - Esporta report in formato PDF (.pdf)
"""
import os
import pandas as pd
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER
from datetime import datetime

from core.bgy_logger import get_logger  # <-- CORRETTO
from core.bgy_paths import REPORTS_PDF_DIR

logger = get_logger("ExportPDF")
os.makedirs(REPORTS_PDF_DIR, exist_ok=True)


def export_to_pdf(df, report_type, date_str=None):
    """
    Esporta un DataFrame in formato PDF (.pdf)
    """
    if df.empty:
        logger.warning("⚠️ DataFrame vuoto, nessun file creato")
        return None
    
    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")
    
    filename = f"report_{report_type}_{date_str}.pdf"
    filepath = os.path.join(REPORTS_PDF_DIR, filename)
    
    doc = SimpleDocTemplate(filepath, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = []
    
    # Titolo
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        alignment=TA_CENTER,
        spaceAfter=12
    )
    elements.append(Paragraph(f"Report {report_type.capitalize()} Voli BGY", title_style))
    elements.append(Spacer(1, 0.2*cm))
    
    # Data
    date_style = ParagraphStyle(
        'CustomDate',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.grey
    )
    elements.append(Paragraph(f"Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}", date_style))
    elements.append(Spacer(1, 0.5*cm))
    
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
    
    stats_data = [["Statistica", "Valore"]]
    for label, value in stats:
        stats_data.append([label, str(value)])
    
    stats_table = Table(stats_data, colWidths=[3*cm, 3*cm])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a2a6c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(stats_table)
    elements.append(Spacer(1, 0.5*cm))
    
    # Tabella voli
    cols_to_show = ['volo', 'callsign', 'tipo_movimento', 'compagnia_aerea', 
                    'destinazione_origine', 'orario_schedulato', 'orario_effettivo', 
                    'minuti_ritardo', 'stato_ritardo']
    cols = [c for c in cols_to_show if c in df.columns]
    
    table_data = [cols]
    max_rows = min(50, len(df))
    for idx in range(max_rows):
        row = []
        for col in cols:
            val = df.iloc[idx][col] if col in df.columns else ""
            row.append(str(val) if pd.notna(val) else "")
        table_data.append(row)
    
    col_widths = [1.5*cm] * len(cols)
    flight_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    flight_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a2a6c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
    ]))
    elements.append(flight_table)
    
    if len(df) > 50:
        elements.append(Paragraph(f"... e altri {len(df) - 50} voli", styles['Normal']))
    
    # Footer
    elements.append(Spacer(1, 1*cm))
    elements.append(Paragraph("Report generato automaticamente da BGY Monitoring Suite", styles['Normal']))
    elements.append(Paragraph("Dati da fonti pubbliche (SACBO e OpenSky Network)", styles['Normal']))
    
    doc.build(elements)
    logger.info(f"📄 Report PDF salvato: {filepath}")
    return filepath


def export_daily_pdf(df, date_str=None):
    return export_to_pdf(df, "daily", date_str)


def export_nightly_pdf(df, date_str=None):
    return export_to_pdf(df, "nightly", date_str)


def export_monthly_pdf(df, date_str=None):
    return export_to_pdf(df, "monthly", date_str)


if __name__ == "__main__":
    test_df = pd.DataFrame({
        'volo': ['FR123', 'WZ456'],
        'compagnia_aerea': ['Ryanair', 'Wizz Air'],
        'destinazione_origine': ['Londra', 'Parigi']
    })
    export_to_pdf(test_df, "daily", "20260828")