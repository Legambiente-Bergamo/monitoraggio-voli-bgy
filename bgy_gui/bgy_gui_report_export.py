"""
bgy_gui_report_export.py - Tab Report Personalizzati e Esportazione.
v2.3.2 - Formato date DD/MM/YYYY, robustezza thread, log per ogni passo,
         supporto daily/nightly nella generazione mensile.
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, Checkbutton, IntVar, scrolledtext
from datetime import datetime, timedelta
import pandas as pd
import shutil
import threading

from bgy_reports import generate_daily_report, generate_nightly_report
from bgy_reports.bgy_report_month import generate_month_report
from bgy_reports.bgy_report_year import generate_yearly_report
from core.bgy_paths import REPORTS_CSV_DIR
from core import get_logger

from exporters import (
    export_daily_xlsx, export_nightly_xlsx, export_monthly_xlsx,
    export_daily_pdf, export_nightly_pdf, export_monthly_pdf,
    export_daily_docx, export_nightly_docx, export_monthly_docx,
    export_daily_html, export_nightly_html, export_monthly_html
)

logger = get_logger("ReportExport")

EXPORT_FUNCTIONS = {
    'daily': {
        'csv': lambda df, d: (df, d), 'xlsx': export_daily_xlsx,
        'pdf': export_daily_pdf, 'docx': export_daily_docx, 'html': export_daily_html,
    },
    'nightly': {
        'csv': lambda df, d: (df, d), 'xlsx': export_nightly_xlsx,
        'pdf': export_nightly_pdf, 'docx': export_nightly_docx, 'html': export_nightly_html,
    },
    'monthly': {
        'csv': lambda df, d: (df, d), 'xlsx': export_monthly_xlsx,
        'pdf': export_monthly_pdf, 'docx': export_monthly_docx, 'html': export_monthly_html,
    },
}

FORMAT_NAMES = {
    'csv': 'CSV', 'xlsx': 'Excel (.xlsx)', 'pdf': 'PDF',
    'docx': 'Word (.docx)', 'html': 'HTML',
}

# Formato date italiano
DATE_FMT = "%d/%m/%Y"
MONTH_FMT = "%m/%Y"
YEAR_FMT = "%Y"


class ProgressWindow:
    def __init__(self, parent, title="Generazione Report in corso..."):
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.geometry("550x450")
        self.window.resizable(True, True)
        self.window.transient(parent)
        self.window.grab_set()
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - 275
        y = (self.window.winfo_screenheight() // 2) - 225
        self.window.geometry(f"550x450+{x}+{y}")

        ttk.Label(self.window, text="🔄 Generazione Report in corso...",
                  font=("Helvetica", 12, "bold")).pack(pady=10)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.window, variable=self.progress_var,
                                            maximum=100, length=450, mode='determinate')
        self.progress_bar.pack(pady=10, padx=20)

        self.percent_label = ttk.Label(self.window, text="0%", font=("Helvetica", 10))
        self.percent_label.pack()

        ttk.Separator(self.window, orient='horizontal').pack(fill='x', padx=20, pady=10)

        log_frame = ttk.LabelFrame(self.window, text="📋 Log operazioni", padding=10)
        log_frame.pack(fill="both", expand=True, padx=20, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, font=("Courier", 9),
                                                   bg="#f8f9fa", fg="#2c3e50",
                                                   relief="sunken", wrap="word")
        self.log_text.pack(fill="both", expand=True)

        self.cancel_button = ttk.Button(self.window, text="❌ Annulla",
                                        command=self.cancel, state="normal")
        self.cancel_button.pack(pady=10)

        self.is_cancelled_flag = False

    def update_progress(self, value, message=""):
        self.progress_var.set(value)
        self.percent_label.config(text=f"{int(value)}%")
        if message:
            self.log_message(message)
        self.window.update_idletasks()

    def log_message(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"{timestamp} {message}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        self.window.update_idletasks()

    def cancel(self):
        self.is_cancelled_flag = True
        self.log_message("⛔ Annullamento richiesto...")
        self.cancel_button.config(state="disabled")

    def complete(self):
        self.progress_var.set(100)
        self.percent_label.config(text="100%")
        self.log_message("✅ Operazione completata!")
        self.cancel_button.config(text="✅ Chiudi", command=self.window.destroy, state="normal")
        self.window.update_idletasks()

    def is_cancelled(self):
        return self.is_cancelled_flag


class ReportExportTab:
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.tab = ttk.Frame(parent)
        self.export_folder = REPORTS_CSV_DIR

        self.format_vars = {
            'csv': IntVar(value=1), 'xlsx': IntVar(value=0),
            'pdf': IntVar(value=0), 'docx': IntVar(value=0), 'html': IntVar(value=0),
        }

        # Date in formato italiano DD/MM/YYYY
        today_it = datetime.now().strftime(DATE_FMT)
        self.daily_vars = {
            'daily_active': IntVar(value=1), 'nightly_active': IntVar(value=0),
            'start_date': tk.StringVar(value=today_it),
            'end_date': tk.StringVar(value=today_it),
        }

        current_month = datetime.now().strftime("%m/%Y")
        self.monthly_vars = {
            'daily_active': IntVar(value=0), 'nightly_active': IntVar(value=0),
            'start_month': tk.StringVar(value=current_month),
            'end_month': tk.StringVar(value=current_month),
        }

        current_year = datetime.now().strftime("%Y")
        self.yearly_vars = {
            'daily_active': IntVar(value=0), 'nightly_active': IntVar(value=0),
            'start_year': tk.StringVar(value=current_year),
            'end_year': tk.StringVar(value=current_year),
        }

        self._create_widgets()

    def _create_widgets(self):
        tab = self.tab
        ttk.Label(tab, text="Report Personalizzati e Esportazione",
                  font=("Helvetica", 14, "bold")).pack(pady=10)

        main_frame = ttk.Frame(tab)
        main_frame.pack(pady=10, fill="both", expand=True, padx=20)

        # Giorno
        day_frame = ttk.LabelFrame(main_frame, text="📅 Giorno (formato: GG/MM/AAAA)", padding=10)
        day_frame.pack(fill="x", pady=5)
        row1 = ttk.Frame(day_frame); row1.pack(fill="x", pady=2)
        Checkbutton(row1, text="☀️ Giornaliero", variable=self.daily_vars['daily_active'],
                    font=("Helvetica", 10)).pack(side="left", padx=10)
        Checkbutton(row1, text="🌙 Notturno", variable=self.daily_vars['nightly_active'],
                    font=("Helvetica", 10)).pack(side="left", padx=10)
        row2 = ttk.Frame(day_frame); row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="Da:").pack(side="left", padx=5)
        ttk.Entry(row2, textvariable=self.daily_vars['start_date'], width=12).pack(side="left", padx=5)
        ttk.Label(row2, text="A:").pack(side="left", padx=5)
        ttk.Entry(row2, textvariable=self.daily_vars['end_date'], width=12).pack(side="left", padx=5)
        ttk.Button(row2, text="📅 Oggi", command=self.set_today_date, width=8).pack(side="left", padx=5)
        ttk.Button(row2, text="📅 Ieri", command=self.set_yesterday_date, width=8).pack(side="left", padx=5)

        # Mese
        month_frame = ttk.LabelFrame(main_frame, text="📅 Mese (formato: MM/AAAA)", padding=10)
        month_frame.pack(fill="x", pady=5)
        row1 = ttk.Frame(month_frame); row1.pack(fill="x", pady=2)
        Checkbutton(row1, text="📊 Giornaliero Mensile", variable=self.monthly_vars['daily_active'],
                    font=("Helvetica", 10)).pack(side="left", padx=10)
        Checkbutton(row1, text="🌙 Notturno Mensile", variable=self.monthly_vars['nightly_active'],
                    font=("Helvetica", 10)).pack(side="left", padx=10)
        row2 = ttk.Frame(month_frame); row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="Da:").pack(side="left", padx=5)
        ttk.Entry(row2, textvariable=self.monthly_vars['start_month'], width=10).pack(side="left", padx=5)
        ttk.Label(row2, text="A:").pack(side="left", padx=5)
        ttk.Entry(row2, textvariable=self.monthly_vars['end_month'], width=10).pack(side="left", padx=5)
        ttk.Button(row2, text="📅 Mese corrente", command=self.set_current_month, width=14).pack(side="left", padx=5)

        # Anno
        year_frame = ttk.LabelFrame(main_frame, text="📅 Anno (formato: AAAA)", padding=10)
        year_frame.pack(fill="x", pady=5)
        row1 = ttk.Frame(year_frame); row1.pack(fill="x", pady=2)
        Checkbutton(row1, text="📈 Giornaliero Annuale", variable=self.yearly_vars['daily_active'],
                    font=("Helvetica", 10)).pack(side="left", padx=10)
        Checkbutton(row1, text="🌙 Notturno Annuale", variable=self.yearly_vars['nightly_active'],
                    font=("Helvetica", 10)).pack(side="left", padx=10)
        row2 = ttk.Frame(year_frame); row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="Da:").pack(side="left", padx=5)
        ttk.Entry(row2, textvariable=self.yearly_vars['start_year'], width=8).pack(side="left", padx=5)
        ttk.Label(row2, text="A:").pack(side="left", padx=5)
        ttk.Entry(row2, textvariable=self.yearly_vars['end_year'], width=8).pack(side="left", padx=5)
        ttk.Button(row2, text="📅 Anno corrente", command=self.set_current_year, width=14).pack(side="left", padx=5)

        # Formati
        format_frame = ttk.LabelFrame(main_frame, text="📁 Formati di Esportazione", padding=10)
        format_frame.pack(fill="x", pady=5)
        row1 = ttk.Frame(format_frame); row1.pack(fill="x")
        Checkbutton(row1, text="📊 CSV", variable=self.format_vars['csv'], font=("Helvetica", 10)).pack(side="left", padx=15)
        Checkbutton(row1, text="📊 Excel (.xlsx)", variable=self.format_vars['xlsx'], font=("Helvetica", 10)).pack(side="left", padx=15)
        Checkbutton(row1, text="📄 PDF", variable=self.format_vars['pdf'], font=("Helvetica", 10)).pack(side="left", padx=15)
        row2 = ttk.Frame(format_frame); row2.pack(fill="x", pady=5)
        Checkbutton(row2, text="📝 Word (.docx)", variable=self.format_vars['docx'], font=("Helvetica", 10)).pack(side="left", padx=15)
        Checkbutton(row2, text="🌐 HTML", variable=self.format_vars['html'], font=("Helvetica", 10)).pack(side="left", padx=15)
        format_btn_frame = ttk.Frame(format_frame); format_btn_frame.pack(fill="x", pady=5)
        ttk.Button(format_btn_frame, text="☑️ Seleziona Tutti i Formati",
                   command=self.select_all_formats, width=25).pack(side="left", padx=5)
        ttk.Button(format_btn_frame, text="⬜ Deseleziona Tutti i Formati",
                   command=self.deselect_all_formats, width=25).pack(side="left", padx=5)

        # Cartella
        folder_frame = ttk.Frame(main_frame); folder_frame.pack(fill="x", pady=5)
        ttk.Label(folder_frame, text="📁 Cartella di destinazione:").pack(side="left", padx=5)
        self.folder_label = ttk.Label(folder_frame, text=REPORTS_CSV_DIR,
                                       font=("Helvetica", 9), foreground="#2980b9")
        self.folder_label.pack(side="left", padx=5)
        ttk.Button(folder_frame, text="📁 Scegli", command=self.choose_folder).pack(side="left", padx=5)

        # Genera
        btn_frame = ttk.Frame(main_frame); btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="📄 Genera Report Selezionati",
                   command=self.start_generation, width=30).pack()

        # Stato
        status_frame = ttk.LabelFrame(main_frame, text="📋 Stato Ultima Operazione", padding=10)
        status_frame.pack(fill="x", pady=5)
        self.status_text = scrolledtext.ScrolledText(status_frame, height=5,
                                                      font=("Courier", 9), bg="#f8f9fa",
                                                      fg="#2c3e50", relief="sunken")
        self.status_text.pack(fill="both", expand=True)
        self.status_text.insert("1.0", "💤 In attesa di generare report...\n")
        self.status_text.config(state="disabled")

    # --- Bottoni rapidi ---
    def set_today_date(self):
        today = datetime.now().strftime(DATE_FMT)
        self.daily_vars['start_date'].set(today)
        self.daily_vars['end_date'].set(today)

    def set_yesterday_date(self):
        yesterday = (datetime.now() - timedelta(days=1)).strftime(DATE_FMT)
        self.daily_vars['start_date'].set(yesterday)
        self.daily_vars['end_date'].set(yesterday)

    def set_current_month(self):
        month_str = datetime.now().strftime(MONTH_FMT)
        self.monthly_vars['start_month'].set(month_str)
        self.monthly_vars['end_month'].set(month_str)

    def set_current_year(self):
        self.yearly_vars['start_year'].set(datetime.now().strftime(YEAR_FMT))
        self.yearly_vars['end_year'].set(datetime.now().strftime(YEAR_FMT))

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Seleziona cartella per salvare i report")
        if folder:
            self.export_folder = folder
            self.folder_label.config(text=folder)

    def select_all_formats(self):
        for var in self.format_vars.values():
            var.set(1)

    def deselect_all_formats(self):
        for var in self.format_vars.values():
            var.set(0)

    # --- Generazione ---
    def start_generation(self):
        selected_formats = [fmt for fmt, var in self.format_vars.items() if var.get() == 1]
        if not selected_formats:
            messagebox.showwarning("Attenzione", "Seleziona almeno un formato")
            return

        has_any = any([
            self.daily_vars['daily_active'].get(),
            self.daily_vars['nightly_active'].get(),
            self.monthly_vars['daily_active'].get(),
            self.monthly_vars['nightly_active'].get(),
            self.yearly_vars['daily_active'].get(),
            self.yearly_vars['nightly_active'].get(),
        ])
        if not has_any:
            messagebox.showwarning("Attenzione", "Seleziona almeno un tipo di report")
            return

        self.progress_window = ProgressWindow(self.tab.winfo_toplevel(),
                                              "Generazione Report in corso...")
        thread = threading.Thread(target=self._generate_and_export_thread,
                                  args=(selected_formats,), daemon=True)
        thread.start()

    def _generate_and_export_thread(self, formats):
        try:
            total_steps = 0

            if self.daily_vars['daily_active'].get() == 1:
                try:
                    start = datetime.strptime(self.daily_vars['start_date'].get(), DATE_FMT)
                    end = datetime.strptime(self.daily_vars['end_date'].get(), DATE_FMT)
                    total_steps += (end - start).days + 1
                except Exception as e:
                    self.progress_window.log_message(f"❌ Data giornaliero non valida: {e}")
            if self.daily_vars['nightly_active'].get() == 1:
                try:
                    start = datetime.strptime(self.daily_vars['start_date'].get(), DATE_FMT)
                    end = datetime.strptime(self.daily_vars['end_date'].get(), DATE_FMT)
                    total_steps += (end - start).days + 1
                except Exception as e:
                    self.progress_window.log_message(f"❌ Data notturno non valida: {e}")
            if self.monthly_vars['daily_active'].get() == 1 or self.monthly_vars['nightly_active'].get() == 1:
                try:
                    start = datetime.strptime(self.monthly_vars['start_month'].get(), MONTH_FMT)
                    end = datetime.strptime(self.monthly_vars['end_month'].get(), MONTH_FMT)
                    total_steps += ((end.year - start.year) * 12 + (end.month - start.month) + 1)
                except Exception as e:
                    self.progress_window.log_message(f"❌ Mese non valido: {e}")
            if self.yearly_vars['daily_active'].get() == 1 or self.yearly_vars['nightly_active'].get() == 1:
                try:
                    y1 = int(self.yearly_vars['start_year'].get())
                    y2 = int(self.yearly_vars['end_year'].get())
                    total_steps += (y2 - y1 + 1)
                except Exception as e:
                    self.progress_window.log_message(f"❌ Anno non valido: {e}")

            if total_steps == 0:
                total_steps = 1

            self.progress_window.log_message(f"📊 Avvio generazione report...")
            self.progress_window.log_message(f"📁 Cartella: {self.export_folder}")
            self.progress_window.log_message(f"📄 Formati: {', '.join(formats)}")
            self.progress_window.log_message("-" * 40)

            all_files = []
            current_step = [0]

            if self.daily_vars['daily_active'].get() == 1 and not self.progress_window.is_cancelled():
                all_files.extend(self._generate_day_reports(formats, current_step, total_steps, 'daily'))
            if self.daily_vars['nightly_active'].get() == 1 and not self.progress_window.is_cancelled():
                all_files.extend(self._generate_day_reports(formats, current_step, total_steps, 'nightly'))
            if self.monthly_vars['daily_active'].get() == 1 and not self.progress_window.is_cancelled():
                all_files.extend(self._generate_month_reports(formats, current_step, total_steps, 'daily'))
            if self.monthly_vars['nightly_active'].get() == 1 and not self.progress_window.is_cancelled():
                all_files.extend(self._generate_month_reports(formats, current_step, total_steps, 'nightly'))
            if self.yearly_vars['daily_active'].get() == 1 and not self.progress_window.is_cancelled():
                all_files.extend(self._generate_year_reports(formats, current_step, total_steps, 'daily'))
            if self.yearly_vars['nightly_active'].get() == 1 and not self.progress_window.is_cancelled():
                all_files.extend(self._generate_year_reports(formats, current_step, total_steps, 'nightly'))

            if self.progress_window.is_cancelled():
                self.progress_window.log_message("⛔ Generazione interrotta dall'utente")
                return

            if all_files:
                self.progress_window.log_message("-" * 40)
                self.progress_window.log_message(f"✅ Generati {len(all_files)} file con successo!")
            else:
                self.progress_window.log_message("⚠️ Nessun file generato. Verifica che ci siano dati per il periodo selezionato.")

            self.app.log_message(f"📊 Report generati: {len(all_files)} file")

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.progress_window.log_message(f"❌ Errore: {e}")
            self.progress_window.log_message(tb)
            logger.error(f"Errore generazione report: {e}\n{tb}")
        finally:
            self.progress_window.complete()

    def _generate_day_reports(self, formats, current_step, total_steps, report_type='daily'):
        try:
            start_date = datetime.strptime(self.daily_vars['start_date'].get(), DATE_FMT)
            end_date = datetime.strptime(self.daily_vars['end_date'].get(), DATE_FMT)
        except ValueError as e:
            self.progress_window.log_message(f"❌ Formato data non valido (usa GG/MM/AAAA): {e}")
            return []
        if start_date > end_date:
            self.progress_window.log_message("⚠️ Data inizio > Data fine")
            return []

        all_files = []
        current_date = start_date
        total_days = (end_date - start_date).days + 1
        report_label = "☀️ Giornaliero" if report_type == 'daily' else "🌙 Notturno"
        self.progress_window.log_message(f"📅 {report_label}: {start_date.strftime(DATE_FMT)} - {end_date.strftime(DATE_FMT)} ({total_days} giorni)")

        day_count = 0
        while current_date <= end_date:
            day_count += 1
            date_str = current_date.strftime("%Y%m%d")
            date_display = current_date.strftime(DATE_FMT)

            if self.progress_window.is_cancelled():
                return all_files

            progress = int((current_step[0] / total_steps) * 100) if total_steps > 0 else 0
            self.progress_window.update_progress(progress, f"📄 Elaborazione {date_display}...")
            self.progress_window.log_message(f"  {report_label} {date_display}...")

            try:
                if report_type == 'daily':
                    result = generate_daily_report(date_str)
                else:
                    result = generate_nightly_report(date_str)
                csv_path = self._handle_result(result, report_type)
                if csv_path and os.path.exists(csv_path):
                    files = self._export_report(csv_path, report_type, formats, date_str)
                    if files:
                        all_files.extend(files)
                        self.progress_window.log_message(f"    ✅ Generati {len(files)} file")
            except Exception as e:
                self.progress_window.log_message(f"    ❌ Errore: {e}")

            current_step[0] += 1
            progress = int((current_step[0] / total_steps) * 100) if total_steps > 0 else 0
            self.progress_window.update_progress(progress, f"📄 Completato {date_display} ({day_count}/{total_days})")
            current_date += timedelta(days=1)

        return all_files

    def _generate_month_reports(self, formats, current_step, total_steps, report_type='daily'):
        try:
            start_month = datetime.strptime(self.monthly_vars['start_month'].get(), MONTH_FMT)
            end_month = datetime.strptime(self.monthly_vars['end_month'].get(), MONTH_FMT)
        except ValueError as e:
            self.progress_window.log_message(f"❌ Formato mese non valido (usa MM/AAAA): {e}")
            return []
        if start_month > end_month:
            self.progress_window.log_message("⚠️ Mese inizio > Mese fine")
            return []

        all_files = []
        current = start_month
        total_months = (end_month.year - start_month.year) * 12 + (end_month.month - start_month.month) + 1
        month_count = 0
        report_label = "📊 Giornaliero Mensile" if report_type == 'daily' else "🌙 Notturno Mensile"

        self.progress_window.log_message(f"📅 {report_label}: {start_month.strftime(MONTH_FMT)} - {end_month.strftime(MONTH_FMT)} ({total_months} mesi)")

        today = datetime.now()
        while current <= end_month:
            month_count += 1
            month_str = current.strftime("%Y%m")
            month_display = current.strftime(MONTH_FMT)

            if self.progress_window.is_cancelled():
                return all_files

            is_current_month = (current.year == today.year and current.month == today.month)
            if is_current_month:
                self.progress_window.log_message(f"  ℹ️ {month_display} è il mese corrente → report parziale fino al {today.strftime(DATE_FMT)}")

            progress = int((current_step[0] / total_steps) * 100) if total_steps > 0 else 0
            self.progress_window.update_progress(progress, f"📄 Elaborazione {month_display}...")
            self.progress_window.log_message(f"  {report_label} {month_display}...")

            try:
                # FIX: passa report_type a generate_month_report
                result = generate_month_report(month_str, report_type=report_type)
                csv_path = self._handle_result(result, 'monthly')
                if csv_path and os.path.exists(csv_path):
                    files = self._export_report(csv_path, 'monthly', formats, month_str)
                    if files:
                        all_files.extend(files)
                        self.progress_window.log_message(f"    ✅ Generati {len(files)} file")
            except Exception as e:
                self.progress_window.log_message(f"    ❌ Errore: {e}")

            current_step[0] += 1
            progress = int((current_step[0] / total_steps) * 100) if total_steps > 0 else 0
            self.progress_window.update_progress(progress, f"📄 Completato {month_display} ({month_count}/{total_months})")

            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

        return all_files

    def _generate_year_reports(self, formats, current_step, total_steps, report_type='daily'):
        try:
            start_year = int(self.yearly_vars['start_year'].get())
            end_year = int(self.yearly_vars['end_year'].get())
        except ValueError as e:
            self.progress_window.log_message(f"❌ Formato anno non valido (usa AAAA): {e}")
            return []
        if start_year > end_year:
            self.progress_window.log_message("⚠️ Anno inizio > Anno fine")
            return []

        all_files = []
        total_years = end_year - start_year + 1
        year_count = 0
        report_label = "📈 Giornaliero Annuale" if report_type == 'daily' else "🌙 Notturno Annuale"
        self.progress_window.log_message(f"📅 {report_label}: {start_year} - {end_year} ({total_years} anni)")

        for year in range(start_year, end_year + 1):
            year_count += 1
            if self.progress_window.is_cancelled():
                return all_files
            progress = int((current_step[0] / total_steps) * 100) if total_steps > 0 else 0
            self.progress_window.update_progress(progress, f"📄 Elaborazione {year}...")
            self.progress_window.log_message(f"  {report_label} {year}...")
            try:
                result = generate_yearly_report(str(year))
                csv_path = self._handle_result(result, 'yearly')
                if csv_path and os.path.exists(csv_path):
                    files = self._export_report(csv_path, 'yearly', formats, str(year))
                    if files:
                        all_files.extend(files)
                        self.progress_window.log_message(f"    ✅ Generati {len(files)} file")
            except Exception as e:
                self.progress_window.log_message(f"    ❌ Errore: {e}")
            current_step[0] += 1
            progress = int((current_step[0] / total_steps) * 100) if total_steps > 0 else 0
            self.progress_window.update_progress(progress, f"📄 Completato {year} ({year_count}/{total_years})")

        return all_files

    def _handle_result(self, result, report_type):
        if isinstance(result, tuple):
            if len(result) == 2:
                csv_path, msg = result
                self.progress_window.log_message(f"    📄 {msg}")
                return csv_path
            elif len(result) == 3:
                csv_path, html_path, charts = result
                if html_path:
                    self.progress_window.log_message(f"    📄 HTML: {os.path.basename(html_path)}")
                    if 'html' in [fmt for fmt, var in self.format_vars.items() if var.get() == 1]:
                        dest = os.path.join(self.export_folder, os.path.basename(html_path))
                        if os.path.abspath(html_path) != os.path.abspath(dest):
                            shutil.copy2(html_path, dest)
                            self.progress_window.log_message(f"      ✅ HTML: {os.path.basename(dest)}")
                return csv_path
        else:
            return result
        return None

    def _export_report(self, csv_path, report_type, formats, date_str):
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            self.progress_window.log_message(f"      ❌ Errore lettura CSV: {e}")
            return []
        exported = []

        for fmt in formats:
            if fmt == 'csv':
                dest = os.path.join(self.export_folder, os.path.basename(csv_path))
                if os.path.abspath(csv_path) != os.path.abspath(dest):
                    shutil.copy2(csv_path, dest)
                    self.progress_window.log_message(f"      ✅ CSV: {os.path.basename(dest)}")
                else:
                    self.progress_window.log_message(f"      ✅ CSV già presente: {os.path.basename(csv_path)}")
                exported.append(dest)
                continue

            if report_type in EXPORT_FUNCTIONS and fmt in EXPORT_FUNCTIONS[report_type]:
                try:
                    result_path = EXPORT_FUNCTIONS[report_type][fmt](df, date_str)
                    if result_path:
                        dest = os.path.join(self.export_folder, os.path.basename(result_path))
                        if os.path.abspath(result_path) != os.path.abspath(dest):
                            shutil.copy2(result_path, dest)
                            self.progress_window.log_message(f"      ✅ {FORMAT_NAMES[fmt]}: {os.path.basename(dest)}")
                        else:
                            self.progress_window.log_message(f"      ✅ {FORMAT_NAMES[fmt]}: {os.path.basename(result_path)}")
                        exported.append(dest)
                except Exception as e:
                    self.progress_window.log_message(f"      ❌ Errore {FORMAT_NAMES[fmt]}: {str(e)}")

        return exported

    def add_status_message(self, message):
        self.status_text.config(state="normal")
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.status_text.insert("end", f"{timestamp} {message}\n")
        self.status_text.see("end")
        self.status_text.config(state="disabled")