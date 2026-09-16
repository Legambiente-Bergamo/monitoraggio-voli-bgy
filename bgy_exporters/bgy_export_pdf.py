"""
bgy_exporters/bgy_export_pdf.py - Esporta report in formato PDF (.pdf)
Versione 2.5.0
- colonne, limiti, tema da config_data.json (export)
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

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import OUTPUT_PDF_DIR
from bgy_core.bgy_export_common import (
    get_theme, get_available_columns, get_max_rows, compute_stats, footer_lines,
)

logger = get_logger("ExportPDF")
os.makedirs(OUTPUT_PDF_DIR, exist_ok=True)


def _hex_to_rl(hex_color, fallback="#1a2a6c"):
    try:
        h = str(hex_color).lstrip("#")
        return colors.HexColor(f"#{h}")
    except Exception:
        return colors.HexColor(fallback)


def export_to_pdf(df, report_type, date_str=None):
    if df.empty:
        logger.warning("⚠️ DataFrame vuoto, nessun file creato")
        return None

    if not date_str:
        date_str = datetime.now().strftime("%Y%m%d")

    theme = get_theme()
    primary_rl = _hex_to_rl(theme.get("primary_color", "1a2a6c"))
    max_rows = get_max_rows("pdf") or 50

    filename = f"report_{report_type}_{date_str}.pdf"
    filepath = os.path.join(OUTPUT_PDF_DIR, filename)

    doc = SimpleDocTemplate(filepath, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Heading1'],
        fontSize=20, alignment=TA_CENTER, spaceAfter=12,
    )
    elements.append(Paragraph(f"Report {report_type.capitalize()} Voli BGY", title_style))
    elements.append(Spacer(1, 0.2*cm))

    date_style = ParagraphStyle(
        'CustomDate', parent=styles['Normal'],
        fontSize=10, alignment=TA_CENTER, textColor=colors.grey,
    )
    elements.append(Paragraph(
        f"Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}", date_style))
    elements.append(Spacer(1, 0.5*cm))

    # Statistiche
    stats_data = [["Statistica", "Valore"]]
    for label, value in compute_stats(df, report_type):
        stats_data.append([str(label), str(value)])

    stats_table = Table(stats_data, colWidths=[4*cm, 4*cm])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_rl),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(stats_table)
    elements.append(Spacer(1, 0.5*cm))

    # Tabella voli
    cols = get_available_columns(df, report_type)
    if cols:
        table_data = [cols]
        for idx in range(min(max_rows, len(df))):
            row = []
            for col in cols:
                val = df.iloc[idx][col]
                row.append(str(val) if pd.notna(val) else "")
            table_data.append(row)

        col_widths = [max(1.2*cm, 24*cm / max(len(cols), 1))] * len(cols)
        flight_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        flight_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), primary_rl),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
        ]))
        elements.append(flight_table)

        if len(df) > max_rows:
            elements.append(Paragraph(
                f"... e altri {len(df) - max_rows} voli (non esportati)",
                styles['Normal']
            ))

    # Footer
    elements.append(Spacer(1, 1*cm))
    for line in footer_lines():
        elements.append(Paragraph(line, styles['Normal']))

    doc.build(elements)
    logger.info(f"📄 Report PDF salvato: {filepath}")
    return filepath


def export_daily_pdf(df, date_str=None):
    return export_to_pdf(df, "daily", date_str)


def export_nightly_pdf(df, date_str=None):
    return export_to_pdf(df, "nightly", date_str)


def export_monthly_pdf(df, date_str=None):
    return export_to_pdf(df, "monthly", date_str)


def export_yearly_pdf(df, date_str=None):
    return export_to_pdf(df, "yearly", date_str)


if __name__ == "__main__":
    test_df = pd.DataFrame({
        'volo': ['FR123', 'WZ456'],
        'compagnia_aerea': ['Ryanair', 'Wizz Air'],
        'destinazione_origine': ['Londra', 'Parigi'],
    })
    export_to_pdf(test_df, "daily", "20260915")