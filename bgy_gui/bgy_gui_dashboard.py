# bgy_gui_dashboard.py - Tab Dashboard della GUI BGY.
import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime

from scanners import run_day_scan, run_night_scan


class DashboardTab:
    """Tab Dashboard con controlli principali e log."""
    
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.tab = ttk.Frame(parent)
        self._create_widgets()
    
    def _create_widgets(self):
        tab = self.tab
        
        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(pady=10, fill="x", padx=10)
        ttk.Label(header_frame, text="✈️ BGY Monitoring Suite", 
                  font=("Helvetica", 18, "bold"), foreground="#2c3e50").pack()
        ttk.Label(header_frame, text="Aeroporto di Bergamo - Orio al Serio (BGY)", 
                  font=("Helvetica", 10), foreground="#7f8c8d").pack()
        
        # Stato scheduler
        self.scheduler_status_label = ttk.Label(header_frame, text="🔄 Avvio scheduler...", font=("Helvetica", 9))
        self.scheduler_status_label.pack(pady=5)
        
        # Timer
        timer_frame = ttk.Frame(header_frame)
        timer_frame.pack(fill="x", pady=2)
        
        self.day_timer_label = ttk.Label(timer_frame, text="📅 Diurna: --:--:--", 
                                          font=("Helvetica", 10), foreground="#2980b9")
        self.day_timer_label.pack(side="left", padx=10)
        
        self.night_timer_label = ttk.Label(timer_frame, text="🌙 Notturna: --:--:--", 
                                            font=("Helvetica", 10), foreground="#9b59b6")
        self.night_timer_label.pack(side="left", padx=10)
        
        # Ultima operazione
        self.last_operation_label = ttk.Label(header_frame, text="💤 Ultima operazione: Nessuna", 
                                               font=("Helvetica", 9), foreground="#7f8c8d")
        self.last_operation_label.pack(pady=5)
        
        ttk.Separator(tab, orient='horizontal').pack(fill='x', padx=10, pady=5)
        
        # Main frame
        main_frame = ttk.Frame(tab)
        main_frame.pack(pady=10, fill="both", expand=True, padx=10)
        
        # Stato operazioni
        status_frame = ttk.LabelFrame(main_frame, text="📋 Stato Operazioni", padding=10)
        status_frame.pack(fill="x", pady=5)
        
        self.status_label = ttk.Label(status_frame, text="💤 In attesa di comandi", 
                                       relief="sunken", anchor="w", 
                                       font=("Helvetica", 10), padding=5)
        self.status_label.pack(fill="x", pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(status_frame, variable=self.progress_var, 
                                            maximum=100, length=100, mode='indeterminate')
        self.progress_bar.pack(fill="x", pady=5)
        self.progress_bar.pack_forget()
        
        # Scansioni
        scan_frame = ttk.LabelFrame(main_frame, text="📡 Acquisizione Dati", padding=10)
        scan_frame.pack(fill="x", pady=5)
        btn_frame = ttk.Frame(scan_frame)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="📡 Scansione Diurna", 
                   command=lambda: self.app.run_async(run_day_scan, "Scansione Diurna"), 
                   width=20).pack(side="left", padx=5, pady=5, expand=True, fill="x")
        ttk.Button(btn_frame, text="🌙 Scansione Notturna", 
                   command=lambda: self.app.run_async(lambda: run_night_scan(False), "Scansione Notturna"), 
                   width=20).pack(side="left", padx=5, pady=5, expand=True, fill="x")
        
        # Report - Solo pulsante invio email
        report_frame = ttk.LabelFrame(main_frame, text="📧 Report", padding=10)
        report_frame.pack(fill="x", pady=5)
        btn_frame = ttk.Frame(report_frame)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="📧 Invia mail corretto funzionamento", 
                   command=lambda: self.app.run_async(self.app.send_daily_status_email, "Invio Email"), 
                   width=30).pack(side="left", padx=5, pady=5, expand=True, fill="x")
        
        # Log
        log_frame = ttk.LabelFrame(main_frame, text="📝 Log di Sistema", padding=10)
        log_frame.pack(fill="both", expand=True, pady=5)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, font=("Courier", 9), 
                                                   bg="#f8f9fa", fg="#2c3e50", 
                                                   relief="sunken", wrap="word")
        self.log_text.pack(fill="both", expand=True)
        self.log_text.insert("1.0", f"{datetime.now().strftime('%H:%M:%S')} 🚀 Sistema avviato\n")
        self.log_text.insert("end", f"{datetime.now().strftime('%H:%M:%S')} 📌 In attesa di comandi...\n")
        self.log_text.config(state="disabled")
    
    def log_message(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"{timestamp} {message}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
    
    def update_scheduler_status(self, text, color="#27ae60"):
        self.scheduler_status_label.config(text=text, foreground=color)
    
    def update_day_timer(self, timer_text):
        self.day_timer_label.config(text=f"📅 Diurna: {timer_text}")
    
    def update_night_timer(self, timer_text):
        self.night_timer_label.config(text=f"🌙 Notturna: {timer_text}")
    
    def update_last_operation(self, operation):
        self.last_operation_label.config(text=f"🔄 Ultima operazione: {operation}")
    
    def set_status(self, text):
        self.status_label.config(text=text)
    
    def show_progress(self, show=True):
        if show:
            self.progress_bar.pack(fill="x", pady=5)
            self.progress_bar.start(10)
        else:
            self.progress_bar.stop()
            self.progress_bar.pack_forget()