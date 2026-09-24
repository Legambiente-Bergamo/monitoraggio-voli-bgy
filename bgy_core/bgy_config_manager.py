"""
bgy_core/bgy_config_manager.py - Gestione centralizzata delle configurazioni.
Versione 3.0.0

Cambio architetturale (F12a):
- I JSON anagrafici (airlines, countries, aircraft_models, noise_impact,
  alert_messages, assaeroporti) NON sono più letti dal filesystem.
  Vengono letti da PostgreSQL tramite bgy_db (lazy import per evitare
  dipendenza circolare).
- I 5 JSON residui (data, mail, opensky, github, database) continuano a
  essere letti/scritti come prima.
- Cache in memoria per evitare query ripetute: la cache viene invalidata
  da reload_rules() o dalle operazioni di scrittura (add_*).
"""
import os
import json
import threading
import tempfile

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import (
    CONFIG_DATA, CONFIG_MAIL, CONFIG_OPENSKY, CONFIG_GITHUB,
    CONFIG_DATABASE,
)

logger = get_logger("ConfigManager")


class ConfigManager:
    """Gestore centralizzato delle configurazioni. Thread-safe in scrittura."""

    def __init__(self):
        self.configs = {}
        self._cache = {}  # Cache anagrafiche lette dal DB
        self._lock = threading.Lock()
        self.load_all()

    # ------------------------------------------------------------------
    # I/O JSON (solo per i 5 file residui)
    # ------------------------------------------------------------------

    def _load_json(self, path, default):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Errore lettura {path}: {e}")
        return default

    def _save_json(self, path, data):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            fd, tmp = tempfile.mkstemp(
                dir=os.path.dirname(path),
                prefix=os.path.basename(path) + ".", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                os.replace(tmp, path)
                return True
            except Exception:
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
                raise
        except Exception as e:
            logger.error(f"Errore salvataggio {path}: {e}")
            return False

    # ------------------------------------------------------------------
    # LOAD / RELOAD
    # ------------------------------------------------------------------

    def load_all(self):
        # 5 JSON residui
        self.configs['data'] = self._load_json(CONFIG_DATA, self._default_data())
        self.configs['mail'] = self._load_json(CONFIG_MAIL, self._default_mail())
        self.configs['opensky'] = self._load_json(CONFIG_OPENSKY, self._default_opensky())
        self.configs['github'] = self._load_json(CONFIG_GITHUB, self._default_github())
        self.configs['database'] = self._load_json(CONFIG_DATABASE, self._default_database())

        # Anagrafiche: la cache viene invalidata
        self._cache = {}

    def reload(self):
        self.load_all()
        logger.info("Configurazioni ricaricate")

    def reload_mail(self):
        with self._lock:
            self.configs['mail'] = self._load_json(CONFIG_MAIL, self._default_mail())
        logger.info("Configurazione mail ricaricata")

    def reload_rules(self):
        """Invalida la cache delle anagrafiche. La prossima lettura rilegge dal DB."""
        with self._lock:
            self._cache = {}
        logger.info("Cache anagrafiche invalidata (lettura dal DB alla prossima richiesta)")

    # ------------------------------------------------------------------
    # DEFAULT DEI 5 JSON RESIDUI
    # ------------------------------------------------------------------

    def _default_data(self):
        return {
            "scan_schedules": ["00:00", "06:00", "12:00", "18:00"],
            "night_scan_interval_minutes": 2,
            "daily_report_time": "06:30",
            "sacbo_night_scans": ["23:00", "02:00", "05:00"],
            "sacbo_night_scan_enabled": True,
            "notifications": {
                "cooldown_minutes": 30,
                "enabled": True,
                "alerts_enabled": True,
                "daily_status_enabled": True,
            },
            "weather": {
                "latitude": 45.6739, "longitude": 9.7042,
                "start_hour": 20, "end_hour": 6,
                "timezone": "Europe/Rome", "http_timeout": 10,
            },
            "scanner_night": {
                "bbox": {"lamin": 45.545, "lamax": 45.805,
                         "lomin": 9.520, "lomax": 9.890},
                "bgy_lat": 45.6739, "bgy_lon": 9.7042,
                "max_distance_km": 15.0,
                "adsb_lol_radius_nm": 10, "adsb_fi_radius_nm": 10,
                "night_start_hour": 23, "night_end_hour": 6,
                "http_timeout": 15,
                "user_agent": "BGY-Monitoring-Suite/2.6 (info@legambientebergamo.it)",
                "phase_thresholds": {
                    "landing_max_distance_km": 5,
                    "landing_max_altitude_ft": 3000,
                    "approach_max_distance_km": 10,
                    "approach_max_altitude_ft": 5000,
                },
                "runway_bearings": {
                    "RWY 28": [250, 300], "RWY 10": [70, 120],
                    "RWY 16": [160, 190], "RWY 34": [340, 10],
                },
            },
            "scanner_day": {
                "urls": [
                    ["https://www.milanbergamoairport.it/it/voli-tempo-reale/#departure", "Decollo"],
                    ["https://www.milanbergamoairport.it/it/voli-tempo-reale/#arrivals", "Atterraggio"],
                ],
                "playwright_timeout_ms": 40000,
                "wait_after_load_ms": 3000,
                "wait_after_scroll_ms": 2000,
                "scroll_pixels": 1500,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
            "report_day": {
                "delay_threshold_min": 15,
                "early_threshold_min": -5,
                "midnight_wrap_min": 1200,
            },
            "report_night": {
                "distance_by_phase_km": {
                    "Atterraggio": 2.0, "Decollo": 2.0,
                    "Avvicinamento": 7.0, "Sorvolo": 12.0,
                },
                "match_threshold_score": 50,
            },
            "logging": {
                "archive_days": 7, "log_prefix": "bgy_app", "level": "INFO",
            },
            "watchdog": {
                "check_interval_sec": 300,
                "radar_stale_min": 30,
                "scheduler_log_stale_min": 15,
                "scheduler_log_window_sec": 300,
                "sacbo_max_age_hours": 7,
                "opensky_error_threshold": 5,
                "opensky_error_window_min": 15,
                "opensky_log_lines": 500,
            },
            "quality_check": {
                "enabled": True,
                "thresholds": {
                    "max_flights_per_night": 40,
                    "min_flights_per_night": 3,
                    "max_cargo_per_night": 15,
                    "max_pax_zero_pct": 10,
                    "max_pax_per_flight": 500,
                    "max_quota_ft": 50000,
                    "max_gap_days": 3,
                },
            },
            "openflights": {
                "enabled": True,
                "url": "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airlines.dat",
                "cache_file": "airlines.dat",
                "update_interval_days": 7,
                "http_timeout": 30,
            },
            "export": {
                "theme": {
                    "primary_color": "1a2a6c",
                    "text_color": "FFFFFF",
                    "border_color": "grey",
                    "alternate_row_color": "f0f4f8",
                },
                "columns": {
                    "daily": ["volo", "callsign", "tipo_movimento", "compagnia_aerea",
                              "destinazione_origine", "orario_schedulato",
                              "orario_effettivo", "minuti_ritardo", "stato_ritardo"],
                    "nightly": ["callsign", "tipo_movimento", "is_scheduled",
                                "compagnia_aerea", "modello_aereo", "destinazione_finale",
                                "orario_schedulato", "timestamp", "pista", "fase_volo",
                                "quota_ft", "distanza_km", "stima_passeggeri",
                                "stima_rumore_db"],
                    "monthly": ["volo", "callsign", "tipo_movimento", "compagnia_aerea",
                                "destinazione_origine", "orario_schedulato",
                                "minuti_ritardo"],
                    "yearly": ["volo", "callsign", "tipo_movimento", "compagnia_aerea",
                               "destinazione_origine", "destinazione_finale",
                               "orario_schedulato", "minuti_ritardo", "stato_ritardo"],
                },
                "max_rows": {"xlsx": 0, "pdf": 50, "docx": 100, "html": 100},
            },
        }

    def _default_mail(self):
        return {
            "smtp_server": "smtp.gmail.com", "smtp_port": 587,
            "sender_email": "", "sender_password": "",
            "sender_name": "Sistema di Monitoraggio Automatico BGY",
            "recipients_daily": [], "recipients_monthly": [], "recipients_yearly": [],
            "subject_prefix": "📊 Report Voli BGY - ",
            "body_template": "Buongiorno,\n\nin allegato i report...",
        }

    def _default_opensky(self):
        return {"opensky_username": "", "opensky_password": ""}

    def _default_github(self):
        return {
            "enabled": True, "repo_url": "", "branch": "main",
            "username": "Legambiente Bergamo",
            "email": "info@legambientebergamo.it",
            "token": "", "commit_prefix": "BGY Sync",
            "push_timeout_seconds": 300, "pull_timeout_seconds": 60,
        }

    def _default_database(self):
        return {
            "enabled": False,
            "host": "localhost",
            "port": 5432,
            "dbname": "bgy_monitoring",
            "user": "bgy_user",
            "password": "",
            "connect_timeout": 10,
            "application_name": "BGY Monitoring Suite",
        }

    def _default_assaeroporti(self):
        """Parte fissa della config Assaeroporti (la parte 'years' arriva dal DB)."""
        return {
            "source_url": "https://assaeroporti.com/statistiche/",
            "airport_name": "Bergamo", "airport_code": "BGY",
            "cache_days": 7, "http_timeout": 30,
            "years": {},
        }

    # ------------------------------------------------------------------
    # ANAGRAFICHE DAL DB (F12a)
    # ------------------------------------------------------------------

    def _db(self):
        """Lazy import di bgy_db per evitare dipendenza circolare."""
        from bgy_core import bgy_db
        return bgy_db

    def get_airlines(self):
        """
        Ritorna un dict con:
          - _iata_to_icao: {iata: icao}
          - _cargo_airlines: {code: name}
          - _charter_airlines: {code: name}
          - altre chiavi piatte: {code: name} (passeggeri)
        """
        if 'airlines' in self._cache:
            return self._cache['airlines']

        result = {"_iata_to_icao": {}, "_cargo_airlines": {}, "_charter_airlines": {}}
        try:
            db = self._db()

            # IATA -> ICAO
            ok, rows = db.execute_query("SELECT iata, icao FROM iata_to_icao")
            if ok and rows:
                result["_iata_to_icao"] = {r[0]: r[1] for r in rows}
            else:
                logger.warning(f"⚠️ get_airlines: iata_to_icao vuoto o errore ({rows})")

            # Compagnie (con flag)
            ok, rows = db.execute_query(
                "SELECT code, name, is_cargo, is_charter FROM airlines"
            )
            if ok and rows:
                for code, name, is_cargo, is_charter in rows:
                    if is_cargo:
                        result["_cargo_airlines"][code] = name
                    elif is_charter:
                        result["_charter_airlines"][code] = name
                    else:
                        result[code] = name
            else:
                logger.warning(f"⚠️ get_airlines: airlines vuoto o errore ({rows})")

        except Exception as e:
            logger.error(f"❌ get_airlines: {e}")

        self._cache['airlines'] = result
        return result

    def get_countries(self):
        """Ritorna {destination: country}."""
        if 'countries' in self._cache:
            return self._cache['countries']

        result = {}
        try:
            db = self._db()
            ok, rows = db.execute_query("SELECT destination, country FROM countries")
            if ok and rows:
                result = {r[0]: r[1] for r in rows}
            else:
                logger.warning(f"⚠️ get_countries: vuoto o errore ({rows})")
        except Exception as e:
            logger.error(f"❌ get_countries: {e}")

        self._cache['countries'] = result
        return result

    def get_aircraft_models(self):
        """
        Ritorna un dict con:
          - _seats: {model: {posti_2classi, posti_max, posti_default}}
          - _load_factors: {_default: 0.85, code: value, ...}
          - altre chiavi piatte: {code: model}
        """
        if 'aircraft_models' in self._cache:
            return self._cache['aircraft_models']

        result = {"_seats": {}, "_load_factors": {"_default": 0.85}}
        try:
            db = self._db()

            # Modelli con capienza
            ok, rows = db.execute_query(
                "SELECT model, seats_2class, seats_max, seats_default FROM aircraft_models"
            )
            if ok and rows:
                for model, s2, smax, sdef in rows:
                    if s2 is not None or smax is not None or sdef is not None:
                        result["_seats"][model] = {
                            "posti_2classi": s2,
                            "posti_max": smax,
                            "posti_default": sdef,
                        }

            # Load factor default
            ok, rows = db.execute_query(
                "SELECT value FROM config_settings WHERE key = 'load_factor_default'"
            )
            if ok and rows:
                try:
                    result["_load_factors"]["_default"] = float(rows[0][0])
                except (ValueError, TypeError):
                    pass

            # Load factors per compagnia
            ok, rows = db.execute_query("SELECT code, load_factor FROM load_factors")
            if ok and rows:
                for code, value in rows:
                    try:
                        result["_load_factors"][code] = float(value)
                    except (ValueError, TypeError):
                        pass

            # Mapping codice -> modello
            ok, rows = db.execute_query("SELECT code, model FROM aircraft_by_code")
            if ok and rows:
                for code, model in rows:
                    if model:
                        result[code] = model

        except Exception as e:
            logger.error(f"❌ get_aircraft_models: {e}")

        self._cache['aircraft_models'] = result
        return result

    def get_noise_impact(self):
        """
        Ritorna un dict con:
          - _stations: {name: {lat, lon}}
          - _curves: {model: {phase: {distanze: [...], valori: [...]}}}
        """
        if 'noise_impact' in self._cache:
            return self._cache['noise_impact']

        result = {"_stations": {}, "_curves": {}}
        try:
            db = self._db()

            # Centraline
            ok, rows = db.execute_query("SELECT name, lat, lon FROM noise_stations")
            if ok and rows:
                for name, lat, lon in rows:
                    result["_stations"][name] = {
                        "lat": float(lat) if lat is not None else None,
                        "lon": float(lon) if lon is not None else None,
                    }

            # Curve NPD
            ok, rows = db.execute_query(
                "SELECT aircraft_model, phase, distance_m, noise_db "
                "FROM noise_curves "
                "ORDER BY aircraft_model, phase, distance_m"
            )
            if ok and rows:
                for model, phase, dist, db_val in rows:
                    if model not in result["_curves"]:
                        result["_curves"][model] = {}
                    if phase not in result["_curves"][model]:
                        result["_curves"][model][phase] = {"distanze": [], "valori": []}
                    result["_curves"][model][phase]["distanze"].append(int(dist))
                    result["_curves"][model][phase]["valori"].append(float(db_val))

        except Exception as e:
            logger.error(f"❌ get_noise_impact: {e}")

        self._cache['noise_impact'] = result
        return result

    def get_alert_messages(self):
        """Ritorna {key: {subject, body}}."""
        if 'alert_messages' in self._cache:
            return self._cache['alert_messages']

        result = {}
        try:
            db = self._db()
            ok, rows = db.execute_query(
                "SELECT key, subject, body FROM alert_messages"
            )
            if ok and rows:
                for key, subject, body in rows:
                    result[key] = {
                        "subject": subject or "",
                        "body": body or "",
                    }
        except Exception as e:
            logger.error(f"❌ get_alert_messages: {e}")

        self._cache['alert_messages'] = result
        return result

    def get_assaeroporti_config(self):
        """
        Ritorna la struttura originale:
        { source_url, airport_name, airport_code, cache_days, http_timeout, years: {...} }
        La parte 'years' arriva dal DB.
        """
        if 'assaeroporti' in self._cache:
            return self._cache['assaeroporti']

        result = dict(self._default_assaeroporti())
        try:
            db = self._db()
            ok, rows = db.execute_query(
                "SELECT year, passengers, movements, cargo_ton, source "
                "FROM assaeroporti_stats ORDER BY year"
            )
            years = {}
            if ok and rows:
                for year, pax, mov, cargo, source in rows:
                    years[str(year)] = {
                        "passeggeri": pax,
                        "movimenti": mov,
                        "cargo_ton": cargo,
                        "fonte": source or "manuale",
                    }
            result["years"] = years
        except Exception as e:
            logger.error(f"❌ get_assaeroporti_config: {e}")

        self._cache['assaeroporti'] = result
        return result

    # ------------------------------------------------------------------
    # SCRITTURA SUL DB (F12a)
    # ------------------------------------------------------------------

    def add_airline(self, prefix, name):
        """
        Aggiunge una compagnia alla tabella airlines.
        Se il codice esiste già, non sovrascrive (come faceva il vecchio JSON).
        """
        if not prefix or len(prefix) < 2:
            return False
        try:
            db = self._db()
            ok, _ = db.execute_query(
                """INSERT INTO airlines (code, name, source)
                   VALUES (%s, %s, 'auto')
                   ON CONFLICT (code) DO NOTHING""",
                (prefix, name),
                fetch=False,
            )
            if ok:
                self._cache.pop('airlines', None)
                logger.info(f"📝 Compagnia aggiunta al DB: {prefix} = {name}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ add_airline({prefix}, {name}): {e}")
            return False

    def add_destination(self, destination, country):
        """Aggiunge una destinazione alla tabella countries."""
        if not destination or len(destination) < 2:
            return False
        key = destination.strip().upper()
        try:
            db = self._db()
            ok, _ = db.execute_query(
                """INSERT INTO countries (destination, country)
                   VALUES (%s, %s)
                   ON CONFLICT (destination) DO NOTHING""",
                (key, country),
                fetch=False,
            )
            if ok:
                self._cache.pop('countries', None)
                logger.info(f"📝 Destinazione aggiunta al DB: {key} = {country}")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ add_destination({key}, {country}): {e}")
            return False

    # ------------------------------------------------------------------
    # SAVE DEPRECATI (i JSON anagrafici non esistono più)
    # ------------------------------------------------------------------

    def save_assaeroporti_config(self, data):
        logger.warning("⚠️ save_assaeroporti_config() deprecato: le stats sono nel DB.")
        return False

    # ------------------------------------------------------------------
    # SEZIONI DI config_data.json (invariate)
    # ------------------------------------------------------------------

    def get_data_config(self):
        return self.configs.get('data', self._default_data())

    def save_data_config(self, data):
        with self._lock:
            if self._save_json(CONFIG_DATA, data):
                self.configs['data'] = data
                return True
            return False

    def _section(self, name):
        cfg = self.get_data_config()
        defaults = self._default_data()
        s = dict(defaults.get(name, {}))
        s.update(cfg.get(name, {}))
        return s

    def get_weather_config(self):
        return self._section("weather")

    def get_scanner_night_config(self):
        return self._section("scanner_night")

    def get_scanner_day_config(self):
        return self._section("scanner_day")

    def get_report_day_config(self):
        return self._section("report_day")

    def get_report_night_config(self):
        return self._section("report_night")

    def get_logging_config(self):
        return self._section("logging")

    def get_watchdog_config(self):
        return self._section("watchdog")

    def get_export_config(self):
        return self._section("export")

    # ------------------------------------------------------------------
    # CONFIGURAZIONI RESIDUE (JSON)
    # ------------------------------------------------------------------

    def get_database_config(self):
        return self.configs.get('database', self._default_database())

    def get_mail_config(self):
        return self.configs.get('mail', self._default_mail())

    def save_mail_config(self, data):
        with self._lock:
            if self._save_json(CONFIG_MAIL, data):
                self.configs['mail'] = data
                return True
            return False

    def get_github_config(self):
        return self.configs.get('github', self._default_github())

config_manager = ConfigManager()