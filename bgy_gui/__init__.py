"""
bgy_gui - Pacchetto moduli GUI della BGY Monitoring Suite.
Versione 1.3.0
- Aggiunto SyncBackupTab (v1.3.0, INFRA-02)
- Aggiunto NotificationsTab (v1.1.0)
- Aggiunto AirlinesTab (v1.2.0)
"""
from bgy_gui.bgy_gui_dashboard import DashboardTab
from bgy_gui.bgy_gui_mail_config import MailConfigTab
from bgy_gui.bgy_gui_scan_config import ScanConfigTab
from bgy_gui.bgy_gui_report_export import ReportExportTab
from bgy_gui.bgy_gui_charts import ChartsTab
from bgy_gui.bgy_gui_notifications import NotificationsTab
from bgy_gui.bgy_gui_airlines import AirlinesTab
from bgy_gui.bgy_watchdog_config import WatchdogConfigTab
from bgy_gui.bgy_gui_sync_backup import SyncBackupTab

__all__ = [
    "DashboardTab",
    "MailConfigTab",
    "ScanConfigTab",
    "ReportExportTab",
    "ChartsTab",
    "NotificationsTab",
    "AirlinesTab",
    "WatchdogConfigTab",
    "SyncBackupTab",
]