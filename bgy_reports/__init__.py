"""
bgy_reports - Moduli per la generazione dei report.
Versione 2.5.0
"""
from bgy_reports.bgy_report_day import generate_daily_report
from bgy_reports.bgy_report_night import generate_nightly_report
from bgy_reports.bgy_report_month import generate_month_report, send_monthly_report
from bgy_reports.bgy_report_year import generate_yearly_report, send_yearly_report

__all__ = [
    "generate_daily_report",
    "generate_nightly_report",
    "generate_month_report",
    "send_monthly_report",
    "generate_yearly_report",
    "send_yearly_report",
]