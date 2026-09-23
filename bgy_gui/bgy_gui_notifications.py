"""
bgy_gui/bgy_gui_notifications.py - Tab GUI per la gestione delle notifiche.
Versione 1.0.0

Permette di:
- Attivare/disattivare le notifiche email (master switch)
- Attivare/disattivare allarmi watchdog e email di stato giornaliero
- Modificare il cooldown tra notifiche
- Resettare i cooldown attivi
- Inviare un'email di test
- Visualizzare i cooldown attivi
"""
import os
import json
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from bgy_core import get_logger, config_manager
from bgy_core.bgy_paths import CONFIG_DIR
from bgy_core.bgy_mailer import (
    get_notifications_state,
    get_active_cooldowns,
    reset_cooldown,
    send_test_email,
)

logger = get_logger("GUI_Notifications")

CONFIG_DATA_FILE = os.path.join(CONFIG_DIR, "config_data.json")


class NotificationsTab:
    """Tab per la gestione delle notifiche email."""

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.tab = ttk.Frame(parent)

        state = get_notifications_state()
        self.master_var = tk.BooleanVar(value=state["enabled"])
        self.alerts_var = tk.BooleanVar(value=state["alerts_enabled"])
        self.daily_var = tk.BooleanVar(value=state["daily_status_enabled"])
        self.cooldown_var = tk.IntVar(value=state["cooldown_minutes"])

        self._create_widgets()
        self._update_status()

    # -------------------------------------------------------------------------
    # UI
    # -------------------------------------------------------------------------

    def _create_widgets(self):
        tab = self.tab

        ttk.Label(tab, text="🔔 Gestione Notifiche Email",
                  font=("Helvetica", 14, "bold")).pack(pady=10)

        # --- Master switch ---
        master_frame = ttk.LabelFrame(tab, text="🔌 Stato Generale", padding=15)
        master_frame.pack(fill="x", padx=20, pady=5)

        self.master_check = ttk.Checkbutton(
            master_frame,
            text="Notifiche email ATTIVE (master switch)",
            variable=self.master_var,
            command=self._on_master_change,
        )
        self.master_check.pack(anchor="w")

        self.master_hint = ttk.Label(
            master_frame,
            text="Se disattivato, NESSUNA email verrà inviata (allarmi e stato).",
            font=("Helvetica", 8), foreground="#7f8c8d")
        self.master_hint.pack(anchor="w", pady=(2, 0))

        # --- Sotto-interruttori ---
        sub_frame = ttk.LabelFrame(tab, text="📋 Categorie di Notifica", padding=15)
        sub_frame.pack(fill="x", padx=20, pady=5)

        self.alerts_check = ttk.Checkbutton(
            sub_frame,
            text="🚨 Allarmi watchdog (radar mancante, OpenSky, scheduler, ...)",
            variable=self.alerts_var,
        )
        self.alerts_check.pack(anchor="w", pady=2)

        self.daily_check = ttk.Checkbutton(
            sub_frame,
            text="📅 Email di stato giornaliero (06:30)",
            variable=self.daily_var,
        )
        self.daily_check.pack(anchor="w", pady=2)

        # --- Cooldown ---
        cooldown_frame = ttk.LabelFrame(tab, text="⏱️ Cooldown", padding=15)
        cooldown_frame.pack(fill="x", padx=20, pady=5)

        row = ttk.Frame(cooldown_frame)
        row.pack(fill="x")
        ttk.Label(row, text="Intervallo minimo tra due notifiche (min):").pack(side="left")
        self.cooldown_spin = ttk.Spinbox(row, from_=1, to=1440, width=6,
                                          textvariable=self.cooldown_var)
        self.cooldown_spin.pack(side="left", padx=10)

        # --- Azioni ---
        action_frame = ttk.LabelFrame(tab, text="🛠️ Azioni", padding=15)
        action_frame.pack(fill="x", padx=20, pady=5)

        btn_row1 = ttk.Frame(action_frame)
        btn_row1.pack(fill="x", pady=3)

        ttk.Button(btn_row1, text="💾 Salva impostazioni",
                   command=self._on_save).pack(side="left", padx=3)
        ttk.Button(btn_row1, text="📧 Invia email di test",
                   command=self._on_test_email).pack(side="left", padx=3)

        btn_row2 = ttk.Frame(action_frame)
        btn_row2.pack(fill="x", pady=3)

        ttk.Button(btn_row2, text="🗑️ Reset cooldown attivi",
                   command=self._on_reset_cooldown).pack(side="left", padx=3)
        ttk.Button(btn_row2, text="🔄 Ricarica stato",
                   command=self._on_reload).pack(side="left", padx=3)

        # --- Cooldown attivi ---
        cd_frame = ttk.LabelFrame(tab, text="⏳ Cooldown attivi", padding=10)
        cd_frame.pack(fill="both", expand=True, padx=20, pady=5)

        cols = ("chiave", "ultima_notifica", "minuti_rimanenti")
        self.cd_tree = ttk.Treeview(cd_frame, columns=cols, show="headings",
                                     height=6)
        self.cd_tree.heading("chiave", text="Chiave")
        self.cd_tree.heading("ultima_notifica", text="Ultima notifica")
        self.cd_tree.heading("minuti_rimanenti", text="Minuti rimanenti")
        self.cd_tree.column("chiave", width=250)
        self.cd_tree.column("ultima_notifica", width=180)
        self.cd_tree.column("minuti_rimanenti", width=120, anchor="center")
        self.cd_tree.pack(fill="both", expand=True)

        # --- Stato ---
        self.status_label = ttk.Label(tab, text="", font=("Helvetica", 9),
                                       foreground="#7f8c8d")
        self.status_label.pack(pady=5)

        # Applica lo stato iniziale (abilita/disabilita)
        self._on_master_change()

    # -------------------------------------------------------------------------
    # CALLBACK
    # -------------------------------------------------------------------------

    def _on_master_change(self):
        """Abilita/disabilita i sotto-checkbox in base al master."""
        state = "normal" if self.master_var.get() else "disabled"
        self.alerts_check.config(state=state)
        self.daily_check.config(state=state)

    def _on_save(self):
        """Salva la configurazione su config_data.json."""
        try:
            # Backup in memoria
            cfg = config_manager.get_data_config()
            if "notifications" not in cfg:
                cfg["notifications"] = {}
            cfg["notifications"]["enabled"] = bool(self.master_var.get())
            cfg["notifications"]["alerts_enabled"] = bool(self.alerts_var.get())
            cfg["notifications"]["daily_status_enabled"] = bool(self.daily_var.get())
            cfg["notifications"]["cooldown_minutes"] = int(self.cooldown_var.get())

            # Salva su file (con fallback se config_manager non ha il metodo)
            saved = False
            if hasattr(config_manager, "save_data_config"):
                try:
                    config_manager.save_data_config(cfg)
                    saved = True
                except Exception as e:
                    logger.warning(f"save_data_config fallito: {e}")
            if not saved and hasattr(config_manager, "update_data_config"):
                try:
                    config_manager.update_data_config(cfg)
                    saved = True
                except Exception as e:
                    logger.warning(f"update_data_config fallito: {e}")
            if not saved:
                # Fallback: scrittura diretta
                with open(CONFIG_DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=4, ensure_ascii=False)
                logger.info("config_data.json salvato direttamente")

            # Ricarica il config_manager
            try:
                config_manager.reload()
            except Exception:
                pass

            self._set_status("✅ Impostazioni salvate", "#27ae60")
            logger.info(
                f"Notifiche: master={self.master_var.get()}, "
                f"alerts={self.alerts_var.get()}, "
                f"daily={self.daily_var.get()}, "
                f"cooldown={self.cooldown_var.get()} min"
            )
            messagebox.showinfo("Salvato",
                                 "Le impostazioni delle notifiche sono state salvate.\n\n"
                                 "Le modifiche sono già attive per scheduler e watchdog.")
            self._update_status()
        except Exception as e:
            logger.error(f"Errore salvataggio notifiche: {e}")
            messagebox.showerror("Errore", f"Impossibile salvare:\n{e}")

    def _on_test_email(self):
        """Invia un'email di test."""
        if not messagebox.askyesno("Conferma",
                                     "Inviare un'email di test?\n\n"
                                     "Verrà ignorato lo stato dei flag."):
            return
        self._set_status("⏳ Invio email di test...", "#f39c12")
        self.tab.update_idletasks()
        ok, msg = send_test_email()
        if ok:
            self._set_status(f"✅ {msg}", "#27ae60")
            messagebox.showinfo("OK", msg)
        else:
            self._set_status(f"❌ {msg}", "#e74c3c")
            messagebox.showerror("Errore", msg)

    def _on_reset_cooldown(self):
        """Resetta i cooldown."""
        if not messagebox.askyesno("Conferma",
                                     "Resettare tutti i cooldown?\n\n"
                                     "Le notifiche silenziate potranno essere inviate subito."):
            return
        if reset_cooldown():
            self._set_status("✅ Cooldown resettati", "#27ae60")
            self._refresh_cooldowns()
        else:
            self._set_status("❌ Errore reset cooldown", "#e74c3c")

    def _on_reload(self):
        """Ricarica lo stato dal config."""
        state = get_notifications_state()
        self.master_var.set(state["enabled"])
        self.alerts_var.set(state["alerts_enabled"])
        self.daily_var.set(state["daily_status_enabled"])
        self.cooldown_var.set(state["cooldown_minutes"])
        self._on_master_change()
        self._update_status()
        self._refresh_cooldowns()
        self._set_status("🔄 Stato ricaricato", "#27ae60")

    # -------------------------------------------------------------------------
    # UTILITY
    # -------------------------------------------------------------------------

    def _update_status(self):
        """Aggiorna l'etichetta di stato con riepilogo."""
        state = get_notifications_state()
        if state["enabled"]:
            parts = []
            if state["alerts_enabled"]:
                parts.append("🚨 Allarmi ON")
            else:
                parts.append("🚨 Allarmi OFF")
            if state["daily_status_enabled"]:
                parts.append("📅 Stato ON")
            else:
                parts.append("📅 Stato OFF")
            txt = f"🔔 Notifiche ATTIVE — {' | '.join(parts)}"
            color = "#27ae60"
        else:
            txt = "🔕 Notifiche DISATTIVATE (nessuna email verrà inviata)"
            color = "#e74c3c"
        self.status_label.config(text=txt, foreground=color)
        self._refresh_cooldowns()

    def _refresh_cooldowns(self):
        """Aggiorna la tabella dei cooldown attivi."""
        for item in self.cd_tree.get_children():
            self.cd_tree.delete(item)
        try:
            cd = get_active_cooldowns()
            cooldown_min = get_notifications_state()["cooldown_minutes"]
            now = datetime.now()
            for key, last_iso in sorted(cd.items()):
                try:
                    last = datetime.fromisoformat(last_iso)
                    elapsed = (now - last).total_seconds() / 60
                    remaining = max(0, cooldown_min - elapsed)
                    self.cd_tree.insert("", "end", values=(
                        key,
                        last.strftime("%d/%m %H:%M:%S"),
                        f"{remaining:.0f} min",
                    ))
                except Exception:
                    self.cd_tree.insert("", "end", values=(key, last_iso, "?"))
        except Exception as e:
            logger.warning(f"Errore refresh cooldown: {e}")

    def _set_status(self, text, color="#7f8c8d"):
        self.status_label.config(text=text, foreground=color)