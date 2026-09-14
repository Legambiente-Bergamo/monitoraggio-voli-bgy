"""
bgy_gui - Tab della GUI.
"""
from .bgy_gui_dashboard import DashboardTab
from .bgy_gui_mail_config import MailConfigTab
from .bgy_gui_scan_config import ScanConfigTab
from .bgy_gui_report_export import ReportExportTab
from .bgy_watchdog_config import WatchdogConfigTab

__all__ = [
    "DashboardTab",
    "MailConfigTab",
    "ScanConfigTab",
    "ReportExportTab",
    "WatchdogConfigTab",
]