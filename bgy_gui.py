"""
BGY Monitoring Suite - Interfaccia Grafica di Controllo
v2.5.0 - night_scan_schedules da config
"""
import sys
import subprocess
import importlib


def ensure_dependencies():
    required = [
        ("pandas", "pandas"), ("requests", "requests"),
        ("beautifulsoup4", "bs4"), ("schedule", "schedule"),
        ("playwright", "playwright"), ("matplotlib", "matplotlib"),
        ("seaborn", "seaborn"), ("lxml", "lxml"),
        ("openpyxl", "openpyxl"), ("python-docx", "docx"),
        ("reportlab", "reportlab"),
    ]
    missing = []
    for pkg, imp in required:
        try:
            importlib.import_module(imp)
            print(f"✅ {pkg} OK")
        except ImportError:
            missing.append(pkg)
            print(f"❌ {pkg} mancante")
    if missing:
        print(f"\n📦 Installazione: {', '.join(missing)}")
        for pkg in missing:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
            except Exception:
                pass
        if "playwright" in missing:
            try:
                subprocess.check_call(["playwright", "install", "chromium"])
            except Exception:
                pass
    else:
        print("✅ Tutte le dipendenze sono già installate.")


ensure_dependencies()

import os
import json
import threading
import subprocess as sp
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

from bgy_core import get_logger, config_manager, ensure_directories
from bgy_core.bgy_version import __version__
from bgy_gui import (
    DashboardTab, MailConfigTab, ScanConfigTab, ReportExportTab,
    WatchdogConfigTab,
)

logger = get_logger("GUI")


def kill_orphan_instances():
    if sys.platform != "win32":
        return 0
    current_pid = os.getpid()
    killed = []
    try:
        ps_command = (
            "Get-WmiObject Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | "
            "Where-Object { ($_.CommandLine -like '*bgy_gui*' "
            "  -or $_.CommandLine -like '*bgy_scheduler*' "
            "  -or $_.CommandLine -like '*bgy_watchdog*') } | "
            "ForEach-Object { Write-Output ($_.ProcessId.ToString() + '|' + $_.CommandLine) }"
        )
        result = sp.run(
            ["powershell", "-NoProfile", "-Command", ps_command],
            capture_output=True, text=True, timeout=15
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if "|" not in line:
                continue
            pid_str, cmdline = line.split("|", 1)
            if not pid_str.isdigit():
                continue
            pid = int(pid_str)
            if pid == current_pid:
                continue
            try:
                sp.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True, timeout=5)
                if "bgy_gui" in cmdline:
                    kind = "GUI"
                elif "bgy_scheduler" in cmdline:
                    kind = "Scheduler"
                else:
                    kind = "Watchdog"
                killed.append((pid, kind))
            except Exception:
                pass
    except Exception as e:
        print(f"⚠️ Errore kill orphan: {e}")
    if killed:
        print(f"🗑️ Terminate {len(killed)} istanze precedenti:")
        for pid, kind in killed:
            print(f"   - PID {pid} ({kind})")
    return len(killed)


print("🔍 Ricerca istanze precedenti...")
killed_count = kill_orphan_instances()
if killed_count == 0:
    print("✅ Nessuna istanza precedente trovata.")
else:
    print(f"✅ Pulizia completata ({killed_count} processi terminati).")
    import time
    time.sleep(1)


class BgyAppGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("BGY Monitoring Suite - Control Panel")
        self.root.geometry("1000x900")
        self.root.resizable(True, True)
        self.root.minsize(850, 800)

        ensure_directories()

        self.is_running = False
        self.current_operation = ""
        self.scheduler_process = None
        self.scheduler_running = False
        self.watchdog_process = None
        self.watchdog_running = False
        self.countdown_running = True

        self.config_data = config_manager.get_data_config()
        self.scan_schedules = self.config_data.get(
            "scan_schedules", ["00:00", "06:00", "12:00", "18:00"])
        self.daily_report_time = self.config_data.get("daily_report_time", "06:30")
        # FIX blocco 7: night_scan_schedules da config
        self.night_scan_schedules = self.config_data.get(
            "sacbo_night_scans", ["23:00", "02:00", "05:00"])

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(pady=10, fill="both", expand=True, padx=20)

        self.dashboard = DashboardTab(self.notebook, self)
        self.notebook.add(self.dashboard.tab, text="📊 Dashboard")

        self.mail_config = MailConfigTab(self.notebook, self)
        self.notebook.add(self.mail_config.tab, text="📧 Configura Mail")

        self.scan_config = ScanConfigTab(self.notebook, self)
        self.notebook.add(self.scan_config.tab, text="⏰ Configura Scansioni")

        self.report_export = ReportExportTab(self.notebook, self)
        self.notebook.add(self.report_export.tab, text="📄 Report Personalizzati")

        self.watchdog_tab = WatchdogConfigTab(self.notebook, self)
        self.notebook.add(self.watchdog_tab.tab, text="🐕 Watchdog")

        footer_frame = ttk.Frame(root)
        footer_frame.pack(fill="x", padx=20, pady=5)
        ttk.Label(footer_frame, text=f"BGY Monitoring Suite v{__version__}",
                  font=("Helvetica", 8), foreground="#95a5a6").pack(side="left")
        ttk.Label(footer_frame, text=f"© 2026 - Aggiornato: {datetime.now().strftime('%H:%M:%S')}",
                  font=("Helvetica", 8), foreground="#95a5a6").pack(side="right")

        self.root.after(100, self.avvia_scheduler)
        self.root.after(500, self.avvia_watchdog)
        self.update_timer()
        self.update_clock()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _is_scheduler_alive(self):
        if self.scheduler_process is None:
            return False
        return self.scheduler_process.poll() is None

    def avvia_scheduler(self):
        if self.scheduler_running and self._is_scheduler_alive():
            self.log_message("⚠️ Scheduler già in esecuzione, ignoro richiesta duplicata")
            self.dashboard.update_scheduler_status("✅ Scheduler già attivo", "#27ae60")
            return
        self.log_message("🔄 Avvio scheduler...")
        self.dashboard.update_scheduler_status("🔄 Avvio scheduler...", "#f39c12")

        def start():
            try:
                scheduler_path = os.path.join(os.path.dirname(__file__), "bgy_scheduler.py")
                self.scheduler_process = sp.Popen(
                    [sys.executable, scheduler_path],
                    stdout=sp.DEVNULL,
                    stderr=sp.DEVNULL,
                    creationflags=sp.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                self.scheduler_running = True
                self.root.after(0, lambda: self.dashboard.update_scheduler_status(
                    "✅ Scheduler in esecuzione", "#27ae60"))
                self.root.after(0, lambda: self.log_message("✅ Scheduler avviato"))
            except Exception as e:
                self.root.after(0, lambda: self.dashboard.update_scheduler_status(
                    f"❌ Errore: {str(e)[:30]}", "#e74c3c"))
                self.root.after(0, lambda: self.log_message(f"❌ Errore avvio scheduler: {e}"))

        threading.Thread(target=start, daemon=True).start()

    def ferma_scheduler(self):
        self.log_message("🔄 Arresto scheduler...")
        if self.scheduler_process:
            pid = self.scheduler_process.pid
            try:
                self.scheduler_process.terminate()
                try:
                    self.scheduler_process.wait(timeout=5)
                except sp.TimeoutExpired:
                    self.scheduler_process.kill()
            except Exception:
                pass
            if sys.platform == "win32":
                try:
                    sp.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           capture_output=True, timeout=5)
                except Exception:
                    pass
        self.scheduler_running = False
        self.scheduler_process = None
        self.dashboard.update_scheduler_status("💤 Scheduler fermato", "#95a5a6")
        self.log_message("✅ Scheduler arrestato")

    def _is_watchdog_alive(self):
        if self.watchdog_process is None:
            return False
        return self.watchdog_process.poll() is None

    def avvia_watchdog(self):
        if self.watchdog_running and self._is_watchdog_alive():
            self.log_message("⚠️ Watchdog già in esecuzione")
            return
        self.log_message("🐕 Avvio watchdog...")

        def start():
            try:
                wd_path = os.path.join(os.path.dirname(__file__), "bgy_watchdog.py")
                self.watchdog_process = sp.Popen(
                    [sys.executable, wd_path],
                    stdout=sp.DEVNULL,
                    stderr=sp.DEVNULL,
                    creationflags=sp.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                self.watchdog_running = True
                self.root.after(0, lambda: self.log_message("✅ Watchdog avviato"))
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"❌ Errore avvio watchdog: {e}"))

        threading.Thread(target=start, daemon=True).start()

    def ferma_watchdog(self):
        self.log_message("🔄 Arresto watchdog...")
        if self.watchdog_process:
            pid = self.watchdog_process.pid
            try:
                self.watchdog_process.terminate()
                try:
                    self.watchdog_process.wait(timeout=5)
                except sp.TimeoutExpired:
                    self.watchdog_process.kill()
            except Exception:
                pass
            if sys.platform == "win32":
                try:
                    sp.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           capture_output=True, timeout=5)
                except Exception:
                    pass
        self.watchdog_running = False
        self.watchdog_process = None
        self.log_message("✅ Watchdog arrestato")

    def get_next_scan_time(self, schedules):
        now = datetime.now()
        today = now.date()
        times = []
        for t in schedules:
            try:
                h, m = map(int, t.split(':'))
                times.append(datetime(today.year, today.month, today.day, h, m))
            except Exception:
                continue
        future = [t for t in times if t > now]
        if future:
            return min(future)
        tomorrow = today + timedelta(days=1)
        try:
            h, m = map(int, schedules[0].split(':'))
            return datetime(tomorrow.year, tomorrow.month, tomorrow.day, h, m)
        except Exception:
            return now + timedelta(hours=1)

    def update_timer(self):
        if not self.countdown_running:
            return
        try:
            day_next = self.get_next_scan_time(self.scan_schedules)
            day_diff = day_next - datetime.now()
            dt = int(day_diff.total_seconds())
            if dt <= 0:
                self.dashboard.update_day_timer("IN CORSO...")
            else:
                h, m, s = dt // 3600, (dt % 3600) // 60, dt % 60
                self.dashboard.update_day_timer(f"{h:02d}:{m:02d}:{s:02d}")

            night_next = self.get_next_scan_time(self.night_scan_schedules)
            nd = night_next - datetime.now()
            nt = int(nd.total_seconds())
            if nt <= 0:
                self.dashboard.update_night_timer("IN CORSO...")
            else:
                h, m, s = nt // 3600, (nt % 3600) // 60, nt % 60
                self.dashboard.update_night_timer(f"{h:02d}:{m:02d}:{s:02d}")
        except Exception:
            pass
        self.root.after(1000, self.update_timer)

    def update_clock(self):
        try:
            now = datetime.now().strftime("%H:%M:%S")
            for child in self.root.winfo_children():
                if isinstance(child, ttk.Frame):
                    for sub in child.winfo_children():
                        if isinstance(sub, ttk.Label) and "Aggiornato:" in sub.cget("text"):
                            sub.config(text=f"© 2026 - Aggiornato: {now}")
                            break
        except Exception:
            pass
        self.root.after(10000, self.update_clock)

    def run_async(self, func, operation_name="Operazione"):
        if self.is_running:
            messagebox.showwarning("Attenzione", f"⚠️ Operazione in corso: {self.current_operation}")
            return
        self.is_running = True
        self.current_operation = operation_name
        self.dashboard.show_progress(True)
        self.dashboard.set_status(f"⏳ {operation_name} in corso...")
        self.dashboard.update_last_operation(f"{operation_name} (in corso)")
        self.log_message(f"🔄 Avvio {operation_name}")

        def worker():
            try:
                result = func()
                if isinstance(result, tuple) and len(result) == 2:
                    path, msg = result
                    self.root.after(0, lambda: self.dashboard.set_status(f"✅ {operation_name} completata"))
                    self.root.after(0, lambda: self.log_message(f"✅ {msg}"))
                    if path:
                        self.root.after(0, lambda: self.log_message(f"📁 File: {os.path.basename(path)}"))
                else:
                    self.root.after(0, lambda: self.dashboard.set_status(f"✅ {operation_name} completata"))
                    self.root.after(0, lambda: self.log_message(f"✅ {operation_name} completata"))
                self.root.after(0, lambda: self.dashboard.update_last_operation(f"{operation_name} (completata)"))
                self.root.after(0, lambda: messagebox.showinfo("Completato", f"✅ {operation_name} completata!"))
            except Exception as e:
                err = str(e)
                self.root.after(0, lambda: self.dashboard.set_status(f"❌ Errore: {err[:50]}"))
                self.root.after(0, lambda: self.log_message(f"❌ Errore: {err}"))
                self.root.after(0, lambda: self.dashboard.update_last_operation(f"{operation_name} (fallita)"))
                self.root.after(0, lambda: messagebox.showerror("Errore", err))
            finally:
                self.root.after(0, self._cleanup_after_operation)

        threading.Thread(target=worker, daemon=True).start()

    def _cleanup_after_operation(self):
        self.is_running = False
        self.current_operation = ""
        self.dashboard.show_progress(False)
        if self.dashboard.status_label.cget("text") == "⏳ Operazione in corso...":
            self.dashboard.set_status("💤 In attesa di comandi")

    def log_message(self, message):
        self.dashboard.log_message(message)
        logger.info(message)

    def check_mail_config(self):
        cfg = config_manager.get_mail_config()
        if not cfg:
            return False, "config_mail.json non trovato o vuoto"
        if not cfg.get("sender_email"):
            return False, "sender_email non configurato"
        if not cfg.get("sender_password"):
            return False, "sender_password non configurata"
        if not (cfg.get("recipients_daily") or cfg.get("recipients")):
            return False, "Nessun destinatario configurato"
        return True, "Configurazione OK"

    def send_daily_status_email(self):
        from bgy_core.bgy_mailer import send_daily_status
        from bgy_reports import generate_daily_report, generate_nightly_report

        self.log_message("📧 Invio email di stato...")
        ok, msg = self.check_mail_config()
        if not ok:
            self.log_message(f"❌ Config email incompleta: {msg}")
            messagebox.showerror("Errore Configurazione", f"Configurazione email incompleta:\n\n{msg}")
            return False

        try:
            day_ok, night_ok = False, False
            day_msg, night_msg = "Non generato", "Non generato"
            try:
                day_path, day_msg = generate_daily_report()
                day_ok = day_path is not None and os.path.exists(day_path)
            except Exception as e:
                day_msg = f"Errore: {e}"
            try:
                night_path, night_msg = generate_nightly_report()
                night_ok = night_path is not None and os.path.exists(night_path)
            except Exception as e:
                night_msg = f"Errore: {e}"

            success = day_ok and night_ok
            details = f"Report giornaliero: {day_msg}\nReport notturno: {night_msg}"
            result = send_daily_status(success, details)
            if result:
                self.log_message(f"✅ Email di stato inviata ({'OK' if success else 'Problemi'})")
            else:
                self.log_message("❌ Errore invio email di stato")
            return result
        except Exception as e:
            self.log_message(f"❌ Errore invio email: {e}")
            return False

    def on_closing(self):
        self.countdown_running = False
        self.ferma_scheduler()
        self.ferma_watchdog()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = BgyAppGUI(root)
    root.mainloop()