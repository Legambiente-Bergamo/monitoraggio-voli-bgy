"""
bgy_gui/bgy_gui_charts.py - Tab GUI per anteprima grafici.
Versione 2.5.2

Legge i dati dal DB, applica filtri movimento/tipo volo, genera i grafici
con bgy_core.bgy_charts e li mostra in un canvas Tkinter.
Permette l'export PNG.

Fix v2.5.2: la toolbar non viene più duplicata ad ogni generazione.
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, date, timedelta

import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from bgy_core import get_logger, bgy_db
from bgy_core.bgy_charts import CHART_FUNCTIONS
from bgy_core.bgy_update_rules import get_airline, get_country
from bgy_core.bgy_dates import (
    format_gui_date, format_gui_month, format_gui_year,
    parse_gui_date, parse_gui_month, parse_gui_year,
)

logger = get_logger("GUI_Charts")


class ChartsTab:
    """Tab per la visualizzazione dei grafici con dati dal DB."""

    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.tab = ttk.Frame(parent)
        self.current_figure = None
        self.current_toolbar = None
        self.canvas = None
        self._create_widgets()
        self._check_db()

    # -------------------------------------------------------------------------
    # COSTRUZIONE INTERFACCIA
    # -------------------------------------------------------------------------

    def _create_widgets(self):
        tab = self.tab

        ttk.Label(tab, text="Anteprima Grafici",
                  font=("Helvetica", 14, "bold")).pack(pady=10)

        # --- Frame superiore: controlli ---
        controls = ttk.LabelFrame(tab, text="🔍 Selezione dati", padding=10)
        controls.pack(fill="x", padx=20, pady=5)

        # Riga 1: tipo periodo + periodo
        row1 = ttk.Frame(controls)
        row1.pack(fill="x", pady=2)

        ttk.Label(row1, text="Tipo periodo:").pack(side="left", padx=5)
        self.period_type = tk.StringVar(value="month")
        ttk.Radiobutton(row1, text="Giorno", variable=self.period_type,
                        value="day", command=self._on_period_type_change).pack(side="left", padx=5)
        ttk.Radiobutton(row1, text="Mese", variable=self.period_type,
                        value="month", command=self._on_period_type_change).pack(side="left", padx=5)
        ttk.Radiobutton(row1, text="Anno", variable=self.period_type,
                        value="year", command=self._on_period_type_change).pack(side="left", padx=5)

        # Riga 2: valore periodo
        row2 = ttk.Frame(controls)
        row2.pack(fill="x", pady=2)

        ttk.Label(row2, text="Periodo:").pack(side="left", padx=5)
        self.period_entry = ttk.Entry(row2, width=15)
        self.period_entry.pack(side="left", padx=5)

        ttk.Button(row2, text="📅 Oggi", command=self._set_today).pack(side="left", padx=2)
        ttk.Button(row2, text="📅 Mese corrente", command=self._set_current_month).pack(side="left", padx=2)
        ttk.Button(row2, text="📅 Anno corrente", command=self._set_current_year).pack(side="left", padx=2)

        self.period_hint = ttk.Label(row2, text="(formato MM/AAAA)",
                                      font=("Helvetica", 8), foreground="#7f8c8d")
        self.period_hint.pack(side="left", padx=5)

        # Riga 3: tipo report + grafico
        row3 = ttk.Frame(controls)
        row3.pack(fill="x", pady=2)

        ttk.Label(row3, text="Tipo report:").pack(side="left", padx=5)
        self.report_type = tk.StringVar(value="daily")
        ttk.Radiobutton(row3, text="Diurno", variable=self.report_type,
                        value="daily",
                        command=self._on_report_type_change).pack(side="left", padx=5)
        ttk.Radiobutton(row3, text="Notturno", variable=self.report_type,
                        value="nightly",
                        command=self._on_report_type_change).pack(side="left", padx=5)

        ttk.Label(row3, text="   Grafico:").pack(side="left", padx=5)
        self.chart_key = tk.StringVar(value="movimenti")
        self.chart_combo = ttk.Combobox(row3, textvariable=self.chart_key,
                                         values=list(CHART_FUNCTIONS.keys()),
                                         state="readonly", width=15)
        self.chart_combo.pack(side="left", padx=5)

        # Riga 4: tipo movimento
        row4 = ttk.Frame(controls)
        row4.pack(fill="x", pady=2)

        ttk.Label(row4, text="Tipo movimento:").pack(side="left", padx=5)
        self.movement_filter = tk.StringVar(value="all")
        ttk.Radiobutton(row4, text="Totali", variable=self.movement_filter,
                        value="all").pack(side="left", padx=5)
        ttk.Radiobutton(row4, text="Decolli", variable=self.movement_filter,
                        value="departures").pack(side="left", padx=5)
        ttk.Radiobutton(row4, text="Atterraggi", variable=self.movement_filter,
                        value="arrivals").pack(side="left", padx=5)

        # Riga 5: tipo volo (solo notturno)
        row5 = ttk.Frame(controls)
        row5.pack(fill="x", pady=2)

        self.flight_type_label = ttk.Label(row5, text="Tipo volo:")
        self.flight_type_label.pack(side="left", padx=5)

        self.flight_type_filter = tk.StringVar(value="all")
        self.rb_ft_all = ttk.Radiobutton(row5, text="Tutti",
                                          variable=self.flight_type_filter,
                                          value="all")
        self.rb_ft_all.pack(side="left", padx=5)
        self.rb_ft_pax = ttk.Radiobutton(row5, text="Passeggeri",
                                          variable=self.flight_type_filter,
                                          value="pax")
        self.rb_ft_pax.pack(side="left", padx=5)
        self.rb_ft_cargo = ttk.Radiobutton(row5, text="Cargo",
                                            variable=self.flight_type_filter,
                                            value="cargo")
        self.rb_ft_cargo.pack(side="left", padx=5)

        self.flight_type_hint = ttk.Label(
            row5, text="(disponibile solo per notturno)",
            font=("Helvetica", 8), foreground="#7f8c8d")
        self.flight_type_hint.pack(side="left", padx=5)

        # Riga 6: pulsanti
        row6 = ttk.Frame(controls)
        row6.pack(fill="x", pady=5)

        ttk.Button(row6, text="📈 Genera grafico",
                   command=self._generate_chart).pack(side="left", padx=5)
        ttk.Button(row6, text="💾 Salva come PNG",
                   command=self._save_png).pack(side="left", padx=5)
        ttk.Button(row6, text="🖼️ Apri anteprima",
                   command=self._open_preview).pack(side="left", padx=5)

        # --- Frame centrale: canvas ---
        canvas_frame = ttk.LabelFrame(tab, text="📊 Grafico", padding=10)
        canvas_frame.pack(fill="both", expand=True, padx=20, pady=5)

        self.canvas_container = ttk.Frame(canvas_frame)
        self.canvas_container.pack(fill="both", expand=True)

        self.placeholder = ttk.Label(
            self.canvas_container,
            text="Seleziona i parametri e clicca '📈 Genera grafico'",
            font=("Helvetica", 11), foreground="#7f8c8d")
        self.placeholder.pack(expand=True)

        # --- Frame inferiore: stato ---
        status_frame = ttk.Frame(tab)
        status_frame.pack(fill="x", padx=20, pady=5)

        self.status_label = ttk.Label(status_frame, text="💤 Pronto",
                                       font=("Helvetica", 9), foreground="#7f8c8d")
        self.status_label.pack(side="left")

        # Inizializza lo stato dei radio button
        self._on_period_type_change()
        self._on_report_type_change()

    # -------------------------------------------------------------------------
    # CAMBIO TIPO PERIODO / REPORT
    # -------------------------------------------------------------------------

    def _on_period_type_change(self):
        ptype = self.period_type.get()
        if ptype == "day":
            self.period_hint.config(text="(formato GG/MM/AAAA)")
            self.period_entry.delete(0, tk.END)
            self.period_entry.insert(0, format_gui_date(date.today()))
        elif ptype == "month":
            self.period_hint.config(text="(formato MM/AAAA)")
            self.period_entry.delete(0, tk.END)
            self.period_entry.insert(0, format_gui_month(date.today()))
        else:
            self.period_hint.config(text="(formato AAAA)")
            self.period_entry.delete(0, tk.END)
            self.period_entry.insert(0, format_gui_year(date.today()))

    def _on_report_type_change(self):
        is_nightly = self.report_type.get() == "nightly"
        state = "normal" if is_nightly else "disabled"
        self.rb_ft_all.config(state=state)
        self.rb_ft_pax.config(state=state)
        self.rb_ft_cargo.config(state=state)
        if not is_nightly:
            self.flight_type_filter.set("all")

    def _set_today(self):
        self.period_type.set("day")
        self._on_period_type_change()

    def _set_current_month(self):
        self.period_type.set("month")
        self._on_period_type_change()

    def _set_current_year(self):
        self.period_type.set("year")
        self._on_period_type_change()

    # -------------------------------------------------------------------------
    # VERIFICA DB
    # -------------------------------------------------------------------------

    def _check_db(self):
        if not bgy_db.is_enabled():
            self._set_status("⚠️ Database non abilitato in config_database.json",
                              "#e67e22")
            return
        ok, msg = bgy_db.test_connection()
        if ok:
            self._set_status("✅ Database connesso", "#27ae60")
        else:
            self._set_status(f"❌ Database non raggiungibile: {msg[:60]}",
                              "#e74c3c")

    # -------------------------------------------------------------------------
    # PARSING PERIODO
    # -------------------------------------------------------------------------

    def _parse_period(self):
        ptype = self.period_type.get()
        raw = self.period_entry.get().strip()
        if not raw:
            return None, None, None

        if ptype == "day":
            d = parse_gui_date(raw)
            if not d:
                return None, None, None
            return d, d, d.strftime("%d/%m/%Y")

        if ptype == "month":
            ym = parse_gui_month(raw)
            if not ym:
                return None, None, None
            y, m = ym
            start = date(y, m, 1)
            if m == 12:
                end = date(y + 1, 1, 1) - timedelta(days=1)
            else:
                end = date(y, m + 1, 1) - timedelta(days=1)
            return start, end, f"{m:02d}/{y}"

        if ptype == "year":
            y = parse_gui_year(raw)
            if not y:
                return None, None, None
            return date(y, 1, 1), date(y, 12, 31), str(y)

        return None, None, None

    # -------------------------------------------------------------------------
    # CARICAMENTO DATI
    # -------------------------------------------------------------------------

    def _load_dataframe(self, date_start, date_end, report_type):
        table = "v_daily_report" if report_type == "daily" else "nightly_reports"

        if report_type == "daily":
            sql = (
                f"SELECT data_riferimento, callsign_volo, tipo_movimento, "
                f"destinazione_origine, orario_schedulato, orario_effettivo, "
                f"stato_volo "
                f"FROM {table} "
                f"WHERE data_riferimento BETWEEN %s AND %s"
            )
            cols = ["data_riferimento", "callsign_volo", "tipo_movimento",
                    "destinazione_origine", "orario_schedulato",
                    "orario_effettivo", "stato_volo"]
        else:
            sql = (
                f"SELECT data_riferimento, callsign, tipo_movimento, "
                f"destinazione_finale, orario_schedulato, timestamp, "
                f"pista, fase_volo, stima_passeggeri, stima_rumore_db, "
                f"compagnia_aerea, is_scheduled "
                f"FROM {table} "
                f"WHERE data_riferimento BETWEEN %s AND %s"
            )
            cols = ["data_riferimento", "callsign", "tipo_movimento",
                    "destinazione_finale", "orario_schedulato", "timestamp",
                    "pista", "fase_volo", "stima_passeggeri",
                    "stima_rumore_db", "compagnia_aerea", "is_scheduled"]

        ok, rows = bgy_db.execute_query(sql, (date_start, date_end))
        if not ok:
            logger.error(f"Errore query grafico: {rows}")
            return None
        if not rows:
            return None

        import pandas as pd
        df = pd.DataFrame(rows, columns=cols)
        df['data_report'] = pd.to_datetime(df['data_riferimento'])

        # Arricchimento per daily (compagnia calcolata dal callsign)
        if report_type == "daily":
            df['compagnia_aerea'] = df['callsign_volo'].apply(
                lambda x: get_airline(x) if x else "N/D")

        return df

    # -------------------------------------------------------------------------
    # GENERAZIONE GRAFICO
    # -------------------------------------------------------------------------

    def _generate_chart(self):
        date_start, date_end, label = self._parse_period()
        if not date_start:
            messagebox.showwarning("Attenzione",
                                    "Periodo non valido. Controlla il formato.")
            return

        chart_key = self.chart_key.get()
        if chart_key not in CHART_FUNCTIONS:
            messagebox.showerror("Errore", "Grafico non riconosciuto")
            return

        report_type = self.report_type.get()
        movement_filter = self.movement_filter.get()
        flight_type_filter = self.flight_type_filter.get()

        self._set_status("⏳ Caricamento dati dal DB...", "#f39c12")
        self.tab.update_idletasks()

        df = self._load_dataframe(date_start, date_end, report_type)
        if df is None or df.empty:
            self._set_status(f"⚠️ Nessun dato nel periodo {label}", "#e67e22")
            messagebox.showinfo("Nessun dato",
                                 f"Nessun dato disponibile per il periodo {label}.")
            return

        self._set_status("⏳ Generazione grafico...", "#f39c12")
        self.tab.update_idletasks()

        chart_func = CHART_FUNCTIONS[chart_key]['func']
        try:
            fig = chart_func(df, year_month=label, report_type=report_type,
                             movement_filter=movement_filter,
                             flight_type_filter=flight_type_filter)
        except Exception as e:
            logger.error(f"Errore generazione grafico: {e}")
            self._set_status(f"❌ Errore: {str(e)[:60]}", "#e74c3c")
            messagebox.showerror("Errore", f"Errore nella generazione:\n{e}")
            return

        if fig is None:
            self._set_status("⚠️ Dati insufficienti per il grafico", "#e67e22")
            messagebox.showinfo("Dati insufficienti",
                                 "Il grafico non può essere generato con i dati disponibili.")
            return

        self._clear_canvas()

        self.canvas = FigureCanvasTkAgg(fig, master=self.canvas_container)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self.current_toolbar = NavigationToolbar2Tk(self.canvas, self.canvas_container)
        self.current_toolbar.update()
        self.current_toolbar.pack(side="bottom", fill="x")

        self.current_figure = fig
        self._set_status(f"✅ Grafico generato ({len(df)} righe, periodo {label})",
                          "#27ae60")

    def _clear_canvas(self):
        """Rimuove canvas, toolbar e figura precedenti."""
        if self.current_toolbar is not None:
            try:
                self.current_toolbar.destroy()
            except Exception:
                pass
            self.current_toolbar = None
        if self.canvas is not None:
            try:
                self.canvas.get_tk_widget().destroy()
            except Exception:
                pass
            self.canvas = None
        if self.current_figure is not None:
            try:
                import matplotlib.pyplot as plt
                plt.close(self.current_figure)
            except Exception:
                pass
            self.current_figure = None
        try:
            self.placeholder.pack_forget()
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # SALVATAGGIO
    # -------------------------------------------------------------------------

    def _save_png(self):
        if self.current_figure is None:
            messagebox.showwarning("Attenzione", "Nessun grafico da salvare")
            return

        default_name = (f"grafico_{self.chart_key.get()}_"
                        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=default_name,
            filetypes=[("PNG", "*.png"), ("Tutti i file", "*.*")],
            title="Salva grafico come PNG"
        )
        if not path:
            return

        try:
            self.current_figure.savefig(path, dpi=150, bbox_inches='tight',
                                         facecolor='white')
            self._set_status(f"✅ Salvato: {os.path.basename(path)}", "#27ae60")
            messagebox.showinfo("Salvato", f"Grafico salvato in:\n{path}")
        except Exception as e:
            logger.error(f"Errore salvataggio PNG: {e}")
            messagebox.showerror("Errore", f"Impossibile salvare:\n{e}")

    def _open_preview(self):
        if self.current_figure is None:
            messagebox.showwarning("Attenzione", "Nessun grafico da visualizzare")
            return
        try:
            import tempfile
            import webbrowser
            tmp_dir = tempfile.gettempdir()
            path = os.path.join(
                tmp_dir,
                f"bgy_chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            self.current_figure.savefig(path, dpi=150, bbox_inches='tight',
                                         facecolor='white')
            webbrowser.open(f"file:///{path.replace(os.sep, '/')}")
            self._set_status(f"✅ Anteprima aperta: {os.path.basename(path)}",
                              "#27ae60")
        except Exception as e:
            logger.error(f"Errore apertura anteprima: {e}")
            messagebox.showerror("Errore", f"Impossibile aprire l'anteprima:\n{e}")

    # -------------------------------------------------------------------------
    # UTILITY
    # -------------------------------------------------------------------------

    def _set_status(self, text, color="#7f8c8d"):
        self.status_label.config(text=text, foreground=color)