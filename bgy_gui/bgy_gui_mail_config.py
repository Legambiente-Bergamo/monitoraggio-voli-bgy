"""
bgy_gui/bgy_gui_mail_config.py - Tab configurazione destinatari email.
Versione 2.5.0
- gestisce recipients_* mancanti (li crea se assenti)
- dopo il salvataggio notifica al parent di ricaricare la config
"""
import tkinter as tk
from tkinter import ttk, messagebox

from bgy_core import config_manager


class MailConfigTab:
    """Tab configurazione destinatari email."""

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.tab = ttk.Frame(parent)
        self._create_widgets()
        self._load_config()

    def _load_config(self):
        """Ricarica la config da disco e popola le liste."""
        try:
            config_manager.reload_mail()
        except Exception:
            pass
        cfg = config_manager.get_mail_config() or {}
        for lb in (self.daily_listbox, self.monthly_listbox, self.yearly_listbox):
            lb.delete(0, tk.END)
        for r in cfg.get("recipients_daily", []) or []:
            self.daily_listbox.insert(tk.END, r)
        for r in cfg.get("recipients_monthly", []) or []:
            self.monthly_listbox.insert(tk.END, r)
        for r in cfg.get("recipients_yearly", []) or []:
            self.yearly_listbox.insert(tk.END, r)

    def _create_widgets(self):
        tab = self.tab

        ttk.Label(tab, text="Configurazione Destinatari Email",
                  font=("Helvetica", 14, "bold")).pack(pady=10)

        main_frame = ttk.Frame(tab)
        main_frame.pack(pady=10, fill="both", expand=True, padx=20)

        # Report Giornaliero
        frame1 = ttk.LabelFrame(main_frame, text="📧 Report Giornaliero (solo notifica)", padding=10)
        frame1.pack(fill="x", pady=5)
        daily_list_frame = ttk.Frame(frame1)
        daily_list_frame.pack(fill="x", pady=5)
        ttk.Label(daily_list_frame, text="Destinatari attuali:").pack(anchor="w")
        self.daily_listbox = tk.Listbox(daily_list_frame, height=4, width=60)
        self.daily_listbox.pack(fill="x", pady=5)
        add_frame = ttk.Frame(frame1)
        add_frame.pack(fill="x", pady=5)
        self.daily_entry = ttk.Entry(add_frame, width=40)
        self.daily_entry.pack(side="left", padx=5)
        ttk.Button(add_frame, text="➕ Aggiungi",
                   command=lambda: self.add_recipient(self.daily_entry, self.daily_listbox),
                   width=12).pack(side="left", padx=2)
        ttk.Button(add_frame, text="✖️ Rimuovi",
                   command=lambda: self.remove_recipient(self.daily_listbox),
                   width=12).pack(side="left", padx=2)

        # Report Mensile
        frame2 = ttk.LabelFrame(main_frame, text="📊 Report Mensile (con allegati)", padding=10)
        frame2.pack(fill="x", pady=5)
        monthly_list_frame = ttk.Frame(frame2)
        monthly_list_frame.pack(fill="x", pady=5)
        ttk.Label(monthly_list_frame, text="Destinatari attuali:").pack(anchor="w")
        self.monthly_listbox = tk.Listbox(monthly_list_frame, height=4, width=60)
        self.monthly_listbox.pack(fill="x", pady=5)
        add_frame2 = ttk.Frame(frame2)
        add_frame2.pack(fill="x", pady=5)
        self.monthly_entry = ttk.Entry(add_frame2, width=40)
        self.monthly_entry.pack(side="left", padx=5)
        ttk.Button(add_frame2, text="➕ Aggiungi",
                   command=lambda: self.add_recipient(self.monthly_entry, self.monthly_listbox),
                   width=12).pack(side="left", padx=2)
        ttk.Button(add_frame2, text="✖️ Rimuovi",
                   command=lambda: self.remove_recipient(self.monthly_listbox),
                   width=12).pack(side="left", padx=2)

        # Report Annuale
        frame3 = ttk.LabelFrame(main_frame, text="📈 Report Annuale (con allegati)", padding=10)
        frame3.pack(fill="x", pady=5)
        yearly_list_frame = ttk.Frame(frame3)
        yearly_list_frame.pack(fill="x", pady=5)
        ttk.Label(yearly_list_frame, text="Destinatari attuali:").pack(anchor="w")
        self.yearly_listbox = tk.Listbox(yearly_list_frame, height=4, width=60)
        self.yearly_listbox.pack(fill="x", pady=5)
        add_frame3 = ttk.Frame(frame3)
        add_frame3.pack(fill="x", pady=5)
        self.yearly_entry = ttk.Entry(add_frame3, width=40)
        self.yearly_entry.pack(side="left", padx=5)
        ttk.Button(add_frame3, text="➕ Aggiungi",
                   command=lambda: self.add_recipient(self.yearly_entry, self.yearly_listbox),
                   width=12).pack(side="left", padx=2)
        ttk.Button(add_frame3, text="✖️ Rimuovi",
                   command=lambda: self.remove_recipient(self.yearly_listbox),
                   width=12).pack(side="left", padx=2)

        # Pulsante Salva
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="💾 Salva Configurazione",
                   command=self.save_config, width=30).pack()
        ttk.Label(main_frame,
                  text="Le modifiche si applicano anche a scheduler e watchdog al salvataggio",
                  font=("Helvetica", 8), foreground="#7f8c8d").pack(pady=2)

    def add_recipient(self, entry, listbox):
        email = entry.get().strip()
        if email and "@" in email:
            listbox.insert(tk.END, email)
            entry.delete(0, tk.END)
        else:
            messagebox.showwarning("Attenzione", "Inserisci un indirizzo email valido.")

    def remove_recipient(self, listbox):
        selection = listbox.curselection()
        if selection:
            listbox.delete(selection[0])

    def get_list_items(self, listbox):
        return [listbox.get(i) for i in range(listbox.size())]

    def save_config(self):
        try:
            cfg = config_manager.get_mail_config() or {}
            # Aggiorna solo i tre campi gestiti dalla GUI,
            # preservando tutto il resto (sender, password, server, template)
            cfg["recipients_daily"] = self.get_list_items(self.daily_listbox)
            cfg["recipients_monthly"] = self.get_list_items(self.monthly_listbox)
            cfg["recipients_yearly"] = self.get_list_items(self.yearly_listbox)

            if config_manager.save_mail_config(cfg):
                self.app.log_message("✅ Configurazione email salvata")
                try:
                    self.app.on_mail_config_saved()
                except Exception:
                    pass
                messagebox.showinfo("Salvato", "Configurazione email salvata!")
            else:
                self.app.log_message("❌ Errore salvataggio")
                messagebox.showerror("Errore", "Errore durante il salvataggio")
        except Exception as e:
            self.app.log_message(f"❌ Errore: {e}")
            messagebox.showerror("Errore", str(e))