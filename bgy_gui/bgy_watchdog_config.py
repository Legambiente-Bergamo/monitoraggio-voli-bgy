"""
bgy_gui/bgy_watchdog_config.py - Tab GUI per il watchdog.
"""
import os
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime

from core.bgy_paths import LOGS_DIR, CONFIG_DATA
from core import get_logger

logger = get_logger("WatchdogTab")

STATE_FILE = os.path.join(LOGS_DIR, "watchdog_state.json")


class WatchdogConfigTab:
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.tab = ttk.Frame(parent)
        self._create_widgets()
        self._load_cooldown()
        self._update_loop()

    def _create_widgets(self):
        tab = self.tab

        ttk.Label(tab, text="Watchdog - Controllo Anomalie",
                  font=("Helvetica", 14, "bold")).pack(pady=10)

        # --- Stato watchdog ---
        status_frame = ttk.LabelFrame(tab, text="📊 Stato Watchdog", padding=10)
        status_frame.pack(fill="x", padx=20, pady=5)

        self.status_label = ttk.Label(status_frame, text="⏳ Inizializzazione...",
                                       font=("Helvetica", 12, "bold"))
        self.status_label.pack(anchor="w")

        self.next_check_label = ttk.Label(status_frame, text="Prossimo check: --:--",
                                           font=("Helvetica", 10), foreground="#7f8c8d")
        self.next_check_label.pack(anchor="w", pady=2)

        self.last_check_label = ttk.Label(status_frame, text="Ultimo check: mai",
                                           font=("Helvetica", 10), foreground="#7f8c8d")
        self.last_check_label.pack(anchor="w", pady=2)

        # --- Cooldown ---
        cd_frame = ttk.LabelFrame(tab, text="⚙️ Configurazione Cooldown Notifiche", padding=10)
        cd_frame.pack(fill="x", padx=20, pady=5)

        row = ttk.Frame(cd_frame)
        row.pack(fill="x")
        ttk.Label(row, text="Cooldown tra notifiche (minuti):").pack(side="left", padx=5)
        self.cooldown_var = tk.StringVar(value="30")
        ttk.Entry(row, textvariable=self.cooldown_var, width=8).pack(side="left", padx=5)
        ttk.Button(row, text="💾 Salva", command=self._save_cooldown).pack(side="left", padx=5)

        row2 = ttk.Frame(cd_frame)
        row2.pack(fill="x", pady=5)
        ttk.Label(row2, text="Cooldown attivi:", foreground="#7f8c8d").pack(side="left", padx=5)
        self.cooldown_active_label = ttk.Label(row2, text="Nessuno",
                                                foreground="#7f8c8d",
                                                font=("Courier", 9))
        self.cooldown_active_label.pack(side="left", padx=5)

        # --- Azioni ---
        action_frame = ttk.Frame(tab)
        action_frame.pack(pady=10)
        ttk.Button(action_frame, text="🔍 Esegui Check Ora",
                   command=self._run_manual_check, width=25).pack(side="left", padx=5)
        ttk.Button(action_frame, text="🗑️ Reset Cooldown",
                   command=self._reset_cooldown, width=25).pack(side="left", padx=5)

        # --- Log dettagliato ---
        log_frame = ttk.LabelFrame(tab, text="📋 Ultimi Check", padding=10)
        log_frame.pack(fill="both", expand=True, padx=20, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=12,
                                                    font=("Courier", 9),
                                                    bg="#f8f9fa", fg="#2c3e50",
                                                    relief="sunken", wrap="word")
        self.log_text.pack(fill="both", expand=True)
        self.log_text.config(state="disabled")

    # -------------------------------------------------------------------------
    # AZIONI
    # -------------------------------------------------------------------------

    def _load_cooldown(self):
        try:
            with open(CONFIG_DATA, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cd = cfg.get("notifications", {}).get("cooldown_minutes", 30)
            self.cooldown_var.set(str(cd))
        except Exception:
            self.cooldown_var.set("30")

    def _save_cooldown(self):
        try:
            cd = int(self.cooldown_var.get())
            if cd < 1 or cd > 1440:
                messagebox.showerror("Errore", "Cooldown deve essere tra 1 e 1440 minuti")
                return
            with open(CONFIG_DATA, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg.setdefault("notifications", {})["cooldown_minutes"] = cd
            with open(CONFIG_DATA, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
            self.app.log_message(f"✅ Cooldown salvato: {cd} minuti")
            messagebox.showinfo("Salvato", f"Cooldown aggiornato a {cd} minuti")
        except ValueError:
            messagebox.showerror("Errore", "Inserisci un numero valido")
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def _run_manual_check(self):
        """Esegue un check manuale in un thread separato."""
        self.app.log_message("🔍 Check manuale richiesto...")

        def worker():
            try:
                import bgy_watchdog
                results = bgy_watchdog.run_check(manual=True)
                ok_count = sum(1 for r in results.values() if r.get("ok"))
                total = len(results)
                self.app.log_message(f"✅ Check manuale completato ({ok_count}/{total} OK)")
            except Exception as e:
                self.app.log_message(f"❌ Errore check manuale: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _reset_cooldown(self):
        try:
            from core.bgy_notifier import reset_cooldown
            reset_cooldown()
            self.app.log_message("🗑️ Cooldown notifiche resettato")
            messagebox.showinfo("OK", "Cooldown resettato: le prossime notifiche saranno inviate subito")
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    # -------------------------------------------------------------------------
    # REFRESH LOOP
    # -------------------------------------------------------------------------

    def _update_loop(self):
        try:
            self._refresh_state()
            self._refresh_cooldowns()
        except Exception as e:
            logger.error(f"Errore refresh state: {e}")
        self.parent.after(2000, self._update_loop)

    def _refresh_state(self):
        if not os.path.exists(STATE_FILE):
            self.status_label.config(text="⚠️ Watchdog non attivo", foreground="#e74c3c")
            self.next_check_label.config(text="Prossimo check: --:--")
            return

        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)

            results = state.get("results", {})
            all_ok = all(r.get("ok", False) for r in results.values())

            if all_ok:
                self.status_label.config(text="✅ Tutti i controlli OK", foreground="#27ae60")
            else:
                bad = [k for k, r in results.items() if not r.get("ok")]
                self.status_label.config(
                    text=f"⚠️ Problemi: {', '.join(bad)}",
                    foreground="#e74c3c"
                )

            last = state.get("last_check")
            if last:
                try:
                    dt = datetime.fromisoformat(last)
                    self.last_check_label.config(
                        text=f"Ultimo check: {dt.strftime('%d/%m/%Y %H:%M:%S')}"
                    )
                except Exception:
                    pass

            nxt = state.get("next_check")
            if nxt:
                try:
                    dt = datetime.fromisoformat(nxt)
                    now = datetime.now()
                    if dt > now:
                        remaining = int((dt - now).total_seconds())
                        m, s = divmod(remaining, 60)
                        self.next_check_label.config(
                            text=f"Prossimo check tra: {m:02d}:{s:02d} "
                                 f"(alle {dt.strftime('%H:%M:%S')})"
                        )
                    else:
                        self.next_check_label.config(text="Check in corso...")
                except Exception:
                    pass

            # Log dettagliato
            self.log_text.config(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.insert("end", f"Ultimo check: {last}\n")
            self.log_text.insert("end", f"Manuale: {state.get('manual', False)}\n")
            self.log_text.insert("end", "-" * 55 + "\n")
            for name, r in results.items():
                icon = "✅" if r.get("ok") else "❌"
                self.log_text.insert("end", f"{icon} {name}: {r.get('msg')}\n")
            self.log_text.config(state="disabled")

        except Exception as e:
            logger.error(f"Errore parsing state: {e}")

    def _refresh_cooldowns(self):
        try:
            from core.bgy_notifier import get_active_cooldowns, get_cooldown_minutes
            data = get_active_cooldowns()
            if not data:
                self.cooldown_active_label.config(text="Nessuno", foreground="#7f8c8d")
                return
            cd_min = get_cooldown_minutes()
            parts = []
            now = datetime.now()
            for key, ts in data.items():
                try:
                    last = datetime.fromisoformat(ts)
                    remaining = cd_min - int((now - last).total_seconds() / 60)
                    if remaining > 0:
                        parts.append(f"{key} ({remaining}min)")
                except Exception:
                    pass
            if parts:
                self.cooldown_active_label.config(
                    text=", ".join(parts), foreground="#e67e22"
                )
            else:
                self.cooldown_active_label.config(text="Nessuno", foreground="#7f8c8d")
        except Exception:
            pass