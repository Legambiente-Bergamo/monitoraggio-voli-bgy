"""
bgy_gui/bgy_gui_scan_config.py - Tab configurazione scansioni e orari.
Versione 2.5.0
- rimosso campo github_upload_time (il sync GitHub usa daily_report_time)
"""
from tkinter import ttk, messagebox

from bgy_core import config_manager


class ScanConfigTab:
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.config_data = config_manager.get_data_config()
        self.tab = ttk.Frame(parent)
        self._create_widgets()

    def _create_widgets(self):
        tab = self.tab

        ttk.Label(tab, text="Configurazione Scansioni e Orari",
                  font=("Helvetica", 14, "bold")).pack(pady=10)

        main_frame = ttk.Frame(tab)
        main_frame.pack(pady=10, fill="both", expand=True, padx=20)

        # Scansioni diurne
        frame1 = ttk.LabelFrame(main_frame, text="🕐 Scansioni SACBO Diurne", padding=10)
        frame1.pack(fill="x", pady=5)
        ttk.Label(frame1, text="Orari (HH:MM, separati da virgola):").pack(anchor="w")
        self.diurne_entry = ttk.Entry(frame1, width=60)
        self.diurne_entry.pack(fill="x", pady=5)
        self.diurne_entry.insert(0, ", ".join(self.config_data.get("scan_schedules", [])))

        # Scansioni notturne
        frame2 = ttk.LabelFrame(main_frame, text="🌙 Scansioni SACBO Notturne", padding=10)
        frame2.pack(fill="x", pady=5)
        ttk.Label(frame2, text="Orari (HH:MM, separati da virgola):").pack(anchor="w")
        self.notturne_entry = ttk.Entry(frame2, width=60)
        self.notturne_entry.pack(fill="x", pady=5)
        self.notturne_entry.insert(0, ", ".join(self.config_data.get("sacbo_night_scans", [])))

        # Intervallo radar
        frame3 = ttk.LabelFrame(main_frame, text="📡 Scansione Radar Notturna", padding=10)
        frame3.pack(fill="x", pady=5)
        ttk.Label(frame3, text="Intervallo (minuti):").pack(anchor="w")
        self.radar_entry = ttk.Entry(frame3, width=20)
        self.radar_entry.pack(anchor="w", pady=5)
        self.radar_entry.insert(0, str(self.config_data.get("night_scan_interval_minutes", 2)))

        # Orario invio mail automatica + sync GitHub
        frame4 = ttk.LabelFrame(main_frame, text="📧 Orario report + sync GitHub", padding=10)
        frame4.pack(fill="x", pady=5)
        ttk.Label(frame4, text="Orario (HH:MM):").pack(anchor="w")
        self.report_time_entry = ttk.Entry(frame4, width=20)
        self.report_time_entry.pack(anchor="w", pady=5)
        self.report_time_entry.insert(0, str(self.config_data.get("daily_report_time", "06:30")))
        ttk.Label(frame4,
                  text="A quest'ora vengono inviati report giornaliero + email + sync GitHub",
                  font=("Helvetica", 8), foreground="#7f8c8d").pack(anchor="w")

        # Pulsante Salva
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="💾 Salva Configurazione",
                   command=self.save_config, width=30).pack()

    def save_config(self):
        try:
            diurne = [t.strip() for t in self.diurne_entry.get().split(",") if t.strip()]
            notturne = [t.strip() for t in self.notturne_entry.get().split(",") if t.strip()]
            radar_interval = int(self.radar_entry.get())
            report_time = self.report_time_entry.get().strip()

            self.config_data["scan_schedules"] = diurne
            self.config_data["sacbo_night_scans"] = notturne
            self.config_data["night_scan_interval_minutes"] = radar_interval
            self.config_data["daily_report_time"] = report_time

            if config_manager.save_data_config(self.config_data):
                self.app.scan_schedules = diurne
                self.app.night_scan_schedules = notturne
                self.app.daily_report_time = report_time
                self.app.log_message("✅ Configurazione scansioni salvata")
                messagebox.showinfo("Salvato", "Configurazione scansioni salvata con successo!")
            else:
                self.app.log_message("❌ Errore salvataggio configurazione scansioni")
                messagebox.showerror("Errore", "Errore durante il salvataggio")
        except Exception as e:
            self.app.log_message(f"❌ Errore: {e}")
            messagebox.showerror("Errore", str(e))