"""
bgy_gui/bgy_gui_airlines.py - Tab GUI per correggere le compagnie placeholder.
Versione 1.0.0

Mostra le compagnie con nome placeholder ("Compagnia XXX") presenti nella
tabella airlines e permette di assegnare loro un nome corretto.

Opzionalmente propaga la correzione alle righe già presenti in
nightly_reports.
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

from bgy_core import get_logger, bgy_db

logger = get_logger("GUI_Airlines")


# Placeholder considerati "da risolvere"
PLACEHOLDER_PREFIX = "Compagnia "


class AirlinesTab:
    """Tab per la risoluzione delle compagnie placeholder."""

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.tab = ttk.Frame(parent)
        self._create_widgets()
        self.refresh()

    # -------------------------------------------------------------------------
    # UI
    # -------------------------------------------------------------------------

    def _create_widgets(self):
        tab = self.tab

        ttk.Label(tab, text="🏢 Compagnie da Risolvere",
                  font=("Helvetica", 14, "bold")).pack(pady=10)

        # --- Istruzioni ---
        info = ttk.LabelFrame(tab, text="ℹ️ Informazioni", padding=10)
        info.pack(fill="x", padx=20, pady=5)

        ttk.Label(
            info,
            text=("Queste compagnie non sono state riconosciute automaticamente\n"
                  "e hanno un nome placeholder. Puoi assegnare il nome corretto\n"
                  "manualmente. La correzione verrà salvata nel database."),
            justify="left", foreground="#555"
        ).pack(anchor="w")

        # --- Filtri ---
        filters = ttk.LabelFrame(tab, text="🔍 Filtri", padding=10)
        filters.pack(fill="x", padx=20, pady=5)

        row = ttk.Frame(filters)
        row.pack(fill="x")

        ttk.Label(row, text="Ricerca:").pack(side="left", padx=5)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(row, textvariable=self.search_var, width=20)
        self.search_entry.pack(side="left", padx=5)
        self.search_entry.bind("<Return>", lambda e: self.refresh())

        ttk.Button(row, text="Cerca", command=self.refresh).pack(side="left", padx=2)
        ttk.Button(row, text="Reset", command=self._reset_search).pack(side="left", padx=2)

        self.count_label = ttk.Label(row, text="", font=("Helvetica", 9),
                                      foreground="#7f8c8d")
        self.count_label.pack(side="left", padx=15)

        # --- Tabella ---
        table_frame = ttk.LabelFrame(tab, text="📋 Compagnie placeholder", padding=5)
        table_frame.pack(fill="both", expand=True, padx=20, pady=5)

        cols = ("code", "name", "occurrences", "source", "is_cargo", "is_charter")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings",
                                  height=15, selectmode="browse")
        self.tree.heading("code", text="Codice")
        self.tree.heading("name", text="Nome attuale")
        self.tree.heading("occurrences", text="Occorrenze")
        self.tree.heading("source", text="Fonte")
        self.tree.heading("is_cargo", text="Cargo")
        self.tree.heading("is_charter", text="Charter")

        self.tree.column("code", width=80, anchor="center")
        self.tree.column("name", width=280)
        self.tree.column("occurrences", width=90, anchor="center")
        self.tree.column("source", width=100, anchor="center")
        self.tree.column("is_cargo", width=60, anchor="center")
        self.tree.column("is_charter", width=60, anchor="center")

        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        # Doppio click = modifica
        self.tree.bind("<Double-1>", lambda e: self._edit_selected())

        # --- Azioni ---
        actions = ttk.Frame(tab)
        actions.pack(fill="x", padx=20, pady=10)

        ttk.Button(actions, text="✏️ Modifica selezionata",
                   command=self._edit_selected).pack(side="left", padx=3)
        ttk.Button(actions, text="🗑️ Elimina placeholder",
                   command=self._delete_selected).pack(side="left", padx=3)
        ttk.Button(actions, text="🔄 Aggiorna",
                   command=self.refresh).pack(side="left", padx=3)

        # --- Status ---
        self.status_label = ttk.Label(tab, text="💤 Pronto",
                                       font=("Helvetica", 9), foreground="#7f8c8d")
        self.status_label.pack(pady=5)

    # -------------------------------------------------------------------------
    # CARICAMENTO
    # -------------------------------------------------------------------------

    def refresh(self):
        """Ricarica la lista delle compagnie placeholder dal DB."""
        # Pulisci la tabella
        for item in self.tree.get_children():
            self.tree.delete(item)

        search = self.search_var.get().strip()

        # Query: placeholders + conteggio occorrenze in nightly_reports
        sql = """
            SELECT a.code, a.name, a.source, a.is_cargo, a.is_charter,
                   (SELECT COUNT(*) FROM nightly_reports nr
                    WHERE nr.compagnia_aerea = a.name) AS occ
            FROM airlines a
            WHERE a.name LIKE %s
        """
        params = [f"{PLACEHOLDER_PREFIX}%"]

        if search:
            sql += " AND (a.code ILIKE %s OR a.name ILIKE %s)"
            params.append(f"%{search}%")
            params.append(f"%{search}%")

        sql += " ORDER BY occ DESC, a.code ASC"

        ok, rows = bgy_db.execute_query(sql, tuple(params))
        if not ok:
            self._set_status(f"❌ Errore query: {str(rows)[:60]}", "#e74c3c")
            return

        total_occ = 0
        for r in rows or []:
            code, name, source, is_cargo, is_charter, occ = r
            self.tree.insert("", "end", values=(
                code,
                name,
                occ,
                source or "auto",
                "✅" if is_cargo else "",
                "✅" if is_charter else "",
            ))
            total_occ += occ

        self.count_label.config(
            text=f"{len(rows)} compagnie, {total_occ} occorrenze totali"
        )
        self._set_status(f"✅ Caricate {len(rows)} compagnie placeholder",
                          "#27ae60")

    def _reset_search(self):
        self.search_var.set("")
        self.refresh()

    # -------------------------------------------------------------------------
    # AZIONI
    # -------------------------------------------------------------------------

    def _get_selected(self):
        sel = self.tree.selection()
        if not sel:
            return None
        values = self.tree.item(sel[0], "values")
        return {
            "code": values[0],
            "name": values[1],
            "occurrences": int(values[2]),
            "source": values[3],
        }

    def _edit_selected(self):
        info = self._get_selected()
        if not info:
            messagebox.showwarning("Attenzione", "Seleziona una compagnia dalla tabella.")
            return

        code = info["code"]
        old_name = info["name"]
        occ = info["occurrences"]

        # Dialog per nuovo nome
        new_name = simpledialog.askstring(
            "Modifica compagnia",
            f"Codice: {code}\n"
            f"Nome attuale: {old_name}\n"
            f"Occorrenze: {occ}\n\n"
            f"Inserisci il nome corretto:",
            initialvalue=old_name,
            parent=self.tab,
        )

        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name or new_name == old_name:
            return

        # Chiedi se propagare a nightly_reports
        propagate = False
        if occ > 0:
            propagate = messagebox.askyesno(
                "Propagazione",
                f"Aggiornare anche {occ} righe in nightly_reports?\n\n"
                f"Se 'No', il nome verrà aggiornato solo nella tabella airlines\n"
                f"(utile per le future importazioni).",
                parent=self.tab,
            )

        # 1. Aggiorna airlines
        ok, err = bgy_db.execute_query(
            """UPDATE airlines
               SET name = %s, source = 'manual', updated_at = NOW()
               WHERE code = %s""",
            (new_name, code),
            fetch=False,
        )
        if not ok:
            messagebox.showerror("Errore", f"Impossibile aggiornare airlines:\n{err}")
            return

        # 2. Propaga a nightly_reports
        if propagate:
            ok, err = bgy_db.execute_query(
                """UPDATE nightly_reports
                   SET compagnia_aerea = %s
                   WHERE compagnia_aerea = %s""",
                (new_name, old_name),
                fetch=False,
            )
            if not ok:
                messagebox.showerror(
                    "Errore",
                    f"airlines aggiornata, ma propagate a nightly_reports fallita:\n{err}"
                )
                return

        logger.info(f"Compagnia aggiornata: {code} | {old_name} → {new_name} "
                    f"(propagate={propagate})")
        self._set_status(f"✅ {code}: {old_name} → {new_name}", "#27ae60")
        self.refresh()

    def _delete_selected(self):
        info = self._get_selected()
        if not info:
            messagebox.showwarning("Attenzione", "Seleziona una compagnia dalla tabella.")
            return

        if not messagebox.askyesno(
            "Conferma",
            f"Eliminare '{info['name']}' (codice {info['code']}) dalla tabella airlines?\n\n"
            f"Le eventuali {info['occurrences']} righe in nightly_reports NON "
            f"verranno toccate."
        ):
            return

        ok, err = bgy_db.execute_query(
            "DELETE FROM airlines WHERE code = %s",
            (info["code"],),
            fetch=False,
        )
        if not ok:
            messagebox.showerror("Errore", f"Impossibile eliminare:\n{err}")
            return

        logger.info(f"Compagnia eliminata: {info['code']} ({info['name']})")
        self._set_status(f"🗑️ {info['code']} eliminata", "#27ae60")
        self.refresh()

    # -------------------------------------------------------------------------
    # UTILITY
    # -------------------------------------------------------------------------

    def _set_status(self, text, color="#7f8c8d"):
        self.status_label.config(text=text, foreground=color)