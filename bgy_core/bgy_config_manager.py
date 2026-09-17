"""
bgy_core/bgy_config_manager.py - Gestione centralizzata delle configurazioni JSON.
Versione 2.5.0
- aggiunto reload_mail() per ricaricare solo config_mail.json
"""
import os
import json
import threading
import tempfile

from bgy_core.bgy_logger import get_logger
from bgy_core.bgy_paths import (
    CONFIG_DATA, CONFIG_MAIL, CONFIG_OPENSKY, CONFIG_GITHUB,
    CONFIG_ASSAEROPORTI,
    RULES_AIRLINES, RULES_COUNTRIES, RULES_AIRCRAFT_MODELS, RULES_NOISE_IMPACT,
)

logger = get_logger("ConfigManager")


class ConfigManager:
    """Gestore centralizzato delle configurazioni. Thread-safe in scrittura."""

    def __init__(self):
        self.configs = {}
        self._lock = threading.Lock()
        self.load_all()

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

    def load_all(self):
        self.configs['data'] = self._load_json(CONFIG_DATA, self._default_data())
        self.configs['mail'] = self._load_json(CONFIG_MAIL, self._default_mail())
        self.configs['opensky'] = self._load_json(CONFIG_OPENSKY, self._default_opensky())
        self.configs['github'] = self._load_json(CONFIG_GITHUB, self._default_github())
        self.configs['assaeroporti'] = self._load_json(
            CONFIG_ASSAEROPORTI, self._default_assaeroporti())
        self.configs['airlines'] = self._load_json(RULES_AIRLINES, {})
        self.configs['countries'] = self._load_json(RULES_COUNTRIES, {})
        self.configs['aircraft_models'] = self._load_json(RULES_AIRCRAFT_MODELS, {})
        self.configs['noise_impact'] = self._load_json(RULES_NOISE_IMPACT, {})

    def reload(self):
        self.load_all()
        logger.info("Configurazioni ricaricate")

    def reload_mail(self):
        """Ricarica solo config_mail.json (utile dopo salvataggio dalla GUI)."""
        with self._lock:
            self.configs['mail'] = self._load_json(CONFIG_MAIL, self._default_mail())
        logger.info("Configurazione mail ricaricata")

    def reload_rules(self):
        with self._lock:
            self.configs['airlines'] = self._load_json(RULES_AIRLINES, {})
            self.configs['countries'] = self._load_json(RULES_COUNTRIES, {})
            self.configs['aircraft_models'] = self._load_json(RULES_AIRCRAFT_MODELS, {})
            self.configs['noise_impact'] = self._load_json(RULES_NOISE_IMPACT, {})
        logger.info("Regole ricaricate")

    def _default_data(self):
        return {
            "scan_schedules": ["00:00", "06:00", "12:00", "18:00"],
            "night_scan_interval_minutes": 2,
            "daily_report_time": "06:30",
            "sacbo_night_scans": ["23:00", "02:00", "05:00"],
            "sacbo_night_scan_enabled": True,
            "notifications": {"cooldown_minutes": 30, "enabled": True},
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
                "user_agent": "BGY-Monitoring-Suite/2.5 (info@legambientebergamo.it)",
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

    def _default_assaeroporti(self):
        return {
            "source_url": "https://assaeroporti.com/statistiche/",
            "airport_name": "Bergamo", "airport_code": "BGY",
            "cache_days": 7, "http_timeout": 30, "years": {},
        }

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

    def get_mail_config(self):
        return self.configs.get('mail', self._default_mail())

    def save_mail_config(self, data):
        with self._lock:
            if self._save_json(CONFIG_MAIL, data):
                self.configs['mail'] = data
                return True
            return False

    def get_opensky_config(self):
        return self.configs.get('opensky', self._default_opensky())

    def save_opensky_config(self, data):
        with self._lock:
            if self._save_json(CONFIG_OPENSKY, data):
                self.configs['opensky'] = data
                return True
            return False

    def get_github_config(self):
        return self.configs.get('github', self._default_github())

    def save_github_config(self, data):
        with self._lock:
            if self._save_json(CONFIG_GITHUB, data):
                self.configs['github'] = data
                return True
            return False

    def get_assaeroporti_config(self):
        return self.configs.get('assaeroporti', self._default_assaeroporti())

    def save_assaeroporti_config(self, data):
        with self._lock:
            if self._save_json(CONFIG_ASSAEROPORTI, data):
                self.configs['assaeroporti'] = data
                return True
            return False

    def get_airlines(self):
        return self.configs.get('airlines', {})

    def add_airline(self, prefix, name):
        if not prefix or len(prefix) < 2:
            return False
        with self._lock:
            data = self.configs.get('airlines', {})
            if prefix in data:
                return True
            data[prefix] = name
            if self._save_json(RULES_AIRLINES, data):
                self.configs['airlines'] = data
                logger.info(f"📝 Nuova compagnia aggiunta: {prefix} = {name}")
                return True
            return False

    def save_airlines(self, data):
        with self._lock:
            if self._save_json(RULES_AIRLINES, data):
                self.configs['airlines'] = data
                return True
            return False

    def get_countries(self):
        return self.configs.get('countries', {})

    def add_destination(self, destination, country):
        if not destination or len(destination) < 2:
            return False
        key = destination.strip().upper()
        with self._lock:
            data = self.configs.get('countries', {})
            if key in data:
                return True
            data[key] = country
            if self._save_json(RULES_COUNTRIES, data):
                self.configs['countries'] = data
                logger.info(f"📝 Nuova destinazione aggiunta: {key} = {country}")
                return True
            return False

    def save_countries(self, data):
        with self._lock:
            if self._save_json(RULES_COUNTRIES, data):
                self.configs['countries'] = data
                return True
            return False

    def get_aircraft_models(self):
        return self.configs.get('aircraft_models', {})

    def save_aircraft_models(self, data):
        with self._lock:
            if self._save_json(RULES_AIRCRAFT_MODELS, data):
                self.configs['aircraft_models'] = data
                return True
            return False

    def get_noise_impact(self):
        return self.configs.get('noise_impact', {})

    def save_noise_impact(self, data):
        with self._lock:
            if self._save_json(RULES_NOISE_IMPACT, data):
                self.configs['noise_impact'] = data
                return True
            return False


config_manager = ConfigManager()