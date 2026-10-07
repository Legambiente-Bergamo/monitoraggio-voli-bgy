"""
bgy_gui/bgy_gui_sync_backup.py - Tab "Sync & Backup".
Versione 1.0.0

Mostra lo stato di:
  - GitHub sync (in_sync / ahead / behind / diverged)
  - Backup DB (Google Drive)
  - Backup locale (HD esterno, placeholder INFRA-03)

Permette di forzare manualmente:
  - Sync GitHub
  - Backup DB
  - Backup locale (non disponibile finché INFRA-03 non configura il path)

Usa bgy_tools.verify_sync per i check e le azioni.

Novità v1.0.0 (INFRA-02, 07/10/2026):
- Prima versione.
"""
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime


class SyncBackupTab:
    def __init__(self, parent, app):
        self.app = app
        self.root = app.root
        self.tab = ttk.Frame(parent)
        self._busy = False
        self._build_ui()
        # Check automatico all'apertura (dopo che la finestra è disegnata)
        self.root.after(800, self._refresh_status_sync)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        # --- Titolo ---
        header = ttk.Frame(self.tab)
        header.pack(fill="x", padx=10, pady=(10, 0))
        ttk.Label(
            header,
            text="📊 Sync & Backup",
            font=("Helvetica", 14, "bold"),
        ).pack(side="left")
        ttk.Label(
            header,
            text="Stato e azioni manuali per GitHub, backup DB e backup locale",
            font=("Helvetica", 9),
            foreground="#7f8c8d",
        ).pack(side="left", padx=(10, 0))

        # --- Stato attuale ---
        status_frame = ttk.LabelFrame(self.tab, text="Stato attuale", padding=10)
        status_frame.pack(fill="both", expand=True, padx=10, pady=(10, 5))

        self.last_check_label = ttk.Label(
            status_frame,
            text="Ultimo check: --",
            font=("Helvetica", 9, "italic"),
            foreground="#7f8c8d",
        )
        self.last_check_label.pack(anchor="w", pady=(0, 5))

        text_container = ttk.Frame(status_frame)
        text_container.pack(fill="both", expand=True)

        self.status_text = tk.Text(
            text_container,
            wrap="word",
            font=("Consolas", 10),
            bg="#f8f9fa",
            fg="#2c3e50",
            borderwidth=1,
            relief="solid",
            height=14,
            state="disabled",
        )
        status_scroll = ttk.Scrollbar(
            text_container, orient="vertical", command=self.status_text.yview
        )
        self.status_text.configure(yscrollcommand=status_scroll.set)
        self.status_text.pack(side="left", fill="both", expand=True)
        status_scroll.pack(side="right", fill="y")

        # --- Azioni ---
        actions_frame = ttk.LabelFrame(self.tab, text="Azioni manuali", padding=10)
        actions_frame.pack(fill="x", padx=10, pady=5)

        btn_style = {"width": 22, "padding": (4, 6)}

        self.btn_refresh = ttk.Button(
            actions_frame,
            text="🔍  Verifica ora",
            command=self._refresh_status_sync,
            **btn_style,
        )
        self.btn_refresh.pack(side="left", padx=(0, 6))

        self.btn_sync = ttk.Button(
            actions_frame,
            text="📤  Sync GitHub",
            command=self._force_sync_sync,
            **btn_style,
        )
        self.btn_sync.pack(side="left", padx=6)

        self.btn_backup_db = ttk.Button(
            actions_frame,
            text="🗄️  Backup DB",
            command=self._force_backup_db_sync,
            **btn_style,
        )
        self.btn_backup_db.pack(side="left", padx=6)

        self.btn_backup_local = ttk.Button(
            actions_frame,
            text="💾  Backup locale",
            command=self._force_backup_local_sync,
            state="disabled",
            **btn_style,
        )
        self.btn_backup_local.pack(side="left", padx=6)

        ttk.Label(
            actions_frame,
            text="(Backup locale: INFRA-03, non configurato)",
            font=("Helvetica", 8, "italic"),
            foreground="#95a5a6",
        ).pack(side="left", padx=(10, 0))

        # --- Stato operazione corrente ---
        self.op_status_label = ttk.Label(
            self.tab,
            text="💤 In attesa",
            font=("Helvetica", 10),
            foreground="#95a5a6",
        )
        self.op_status_label.pack(anchor="w", padx=14, pady=(6, 2))

        # --- Log attività del tab ---
        log_frame = ttk.LabelFrame(self.tab, text="Attività della sessione", padding=6)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        log_container = ttk.Frame(log_frame)
        log_container.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            log_container,
            wrap="word",
            font=("Consolas", 9),
            bg="#ffffff",
            fg="#2c3e50",
            borderwidth=1,
            relief="solid",
            height=7,
            state="disabled",
        )
        log_scroll = ttk.Scrollbar(
            log_container, orient="vertical", command=self.log_text.yview
        )
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

    # ------------------------------------------------------------------
    # LOG INTERNO DEL TAB
    # ------------------------------------------------------------------

    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # STATO UI
    # ------------------------------------------------------------------

    def _set_busy(self, busy, label=""):
        self._busy = busy
        state = "disabled" if busy else "normal"
        for btn in (self.btn_refresh, self.btn_sync, self.btn_backup_db):
            try:
                btn.configure(state=state)
            except Exception:
                pass
        # btn_backup_local resta sempre disabilitato finché INFRA-03

        if busy:
            self.op_status_label.configure(
                text=f"⏳ {label}...", foreground="#f39c12"
            )
        else:
            self.op_status_label.configure(
                text="💤 In attesa", foreground="#95a5a6"
            )

    def _write_status_text(self, text):
        self.status_text.configure(state="normal")
        self.status_text.delete("1.0", "end")
        self.status_text.insert("1.0", text)
        self.status_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # WORKER ASYNC
    # ------------------------------------------------------------------

    def _run_async(self, func, label, on_done):
        if self._busy:
            messagebox.showwarning(
                "Attenzione", "Un'operazione è già in corso."
            )
            return
        self._set_busy(True, label)

        def worker():
            try:
                result = func()
                self.root.after(0, lambda: on_done(result, None))
            except Exception as e:
                err = e
                self.root.after(0, lambda: on_done(None, err))

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # AZIONI
    # ------------------------------------------------------------------

    def _refresh_status_sync(self):
        """Check sincrono veloce (non blocca, ~1-2s)."""
        self._run_async(
            self._do_check_all,
            "Verifica stato",
            self._on_refresh_done,
        )

    def _do_check_all(self):
        from bgy_tools.verify_sync import check_all, format_text
        result = check_all()
        text = format_text(result)
        return {"result": result, "text": text}

    def _on_refresh_done(self, payload, error):
        self._set_busy(False)
        if error is not None:
            self._log(f"❌ Verifica fallita: {error}")
            self._write_status_text(f"❌ Errore durante la verifica:\n\n{error}")
            messagebox.showerror("Errore", f"Verifica fallita:\n\n{error}")
            return
        result = payload["result"]
        self._write_status_text(payload["text"])
        self.last_check_label.configure(
            text=f"Ultimo check: {result.get('checked_at', '?')}"
        )
        status = "✅ OK" if result.get("overall_ok") else "⚠️ problemi"
        self._log(f"Verifica completata: {status}")

    def _force_sync_sync(self):
        self._run_async(
            self._do_force_sync,
            "Sync GitHub",
            self._on_force_sync_done,
        )

    def _do_force_sync(self):
        from bgy_tools.verify_sync import force_sync_github
        ok, msg = force_sync_github()
        return {"ok": ok, "msg": msg}

    def _on_force_sync_done(self, payload, error):
        self._set_busy(False)
        if error is not None:
            self._log(f"❌ Sync GitHub eccezione: {error}")
            messagebox.showerror("Errore", f"Sync GitHub fallito:\n\n{error}")
            return
        ok = payload["ok"]
        msg = payload["msg"]
        icon = "✅" if ok else "❌"
        self._log(f"{icon} Sync GitHub: {msg}")
        if ok:
            messagebox.showinfo("Sync GitHub", f"✅ {msg}")
        else:
            messagebox.showerror("Sync GitHub", f"❌ {msg}")
        # Rileggi lo stato dopo il sync
        self.root.after(500, self._refresh_status_sync)

    def _force_backup_db_sync(self):
        confirm = messagebox.askyesno(
            "Conferma",
            "Eseguire il backup DB ora?\n\n"
            "Il backup richiede 10-60 secondi e viene caricato su Google Drive.",
        )
        if not confirm:
            self._log("⏭️ Backup DB annullato dall'utente")
            return
        self._run_async(
            self._do_force_backup_db,
            "Backup DB",
            self._on_force_backup_db_done,
        )

    def _do_force_backup_db(self):
        from bgy_tools.verify_sync import force_backup_db
        ok, msg = force_backup_db()
        return {"ok": ok, "msg": msg}

    def _on_force_backup_db_done(self, payload, error):
        self._set_busy(False)
        if error is not None:
            self._log(f"❌ Backup DB eccezione: {error}")
            messagebox.showerror("Errore", f"Backup DB fallito:\n\n{error}")
            return
        ok = payload["ok"]
        msg = payload["msg"]
        icon = "✅" if ok else "❌"
        self._log(f"{icon} Backup DB: {msg}")
        if ok:
            messagebox.showinfo("Backup DB", f"✅ {msg}")
        else:
            messagebox.showerror("Backup DB", f"❌ {msg}")
        self.root.after(500, self._refresh_status_sync)

    def _force_backup_local_sync(self):
        """Non disponibile finché INFRA-03 non configura il path."""
        messagebox.showinfo(
            "Backup locale",
            "Il backup locale su HD esterno sarà disponibile "
            "dopo l'attivazione di INFRA-03.\n\n"
            "Per abilitarlo, aggiungere in config_data.json:\n\n"
            '  "backup_local": {\n'
            '    "enabled": true,\n'
            '    "path": "E:\\\\BGY_Backup",\n'
            '    "max_age_hours": 48\n'
            "  }",
        )