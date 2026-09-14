"""
core/bgy_config_manager.py - Gestione centralizzata delle configurazioni JSON.
"""
import os
import json
from core.bgy_paths import (
    CONFIG_DATA, CONFIG_MAIL, CONFIG_OPENSKY,
    RULES_AIRLINES, RULES_COUNTRIES, RULES_AIRCRAFT_MODELS, RULES_NOISE_IMPACT
)
from core.bgy_logger import get_logger

logger = get_logger("ConfigManager")


class ConfigManager:
    """Gestore centralizzato delle configurazioni."""
    
    def __init__(self):
        self.configs = {}
        self.load_all()
    
    def load_all(self):
        """Carica tutti i file di configurazione."""
        self.configs['data'] = self._load_json(CONFIG_DATA, self._default_data())
        self.configs['mail'] = self._load_json(CONFIG_MAIL, self._default_mail())
        self.configs['opensky'] = self._load_json(CONFIG_OPENSKY, self._default_opensky())
        self.configs['airlines'] = self._load_json(RULES_AIRLINES, {})
        self.configs['countries'] = self._load_json(RULES_COUNTRIES, {})
        self.configs['aircraft_models'] = self._load_json(RULES_AIRCRAFT_MODELS, {})
        self.configs['noise_impact'] = self._load_json(RULES_NOISE_IMPACT, {})
    
    def _load_json(self, path, default):
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Errore lettura {path}: {e}")
        return default
    
    def _save_json(self, path, data):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Errore salvataggio {path}: {e}")
            return False
    
    def _default_data(self):
        return {
            "scan_schedules": ["00:00", "06:00", "12:00", "18:00"],
            "night_scan_interval_minutes": 2,
            "daily_report_time": "06:15",
            "sacbo_night_scans": ["23:00", "02:00", "05:00"],
            "sacbo_night_scan_enabled": True
        }
    
    def _default_mail(self):
        return {
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "sender_email": "",
            "sender_password": "",
            "sender_name": "Sistema di Monitoraggio Automatico BGY",
            "recipients_daily": [],
            "recipients_monthly": [],
            "recipients_yearly": [],
            "subject_prefix": "📊 Report Voli BGY - ",
            "body_template": "Buongiorno,\n\nin allegato i report..."
        }
    
    def _default_opensky(self):
        return {
            "opensky_username": "",
            "opensky_password": ""
        }
    
    def get_data_config(self):
        return self.configs.get('data', self._default_data())
    
    def save_data_config(self, data):
        if self._save_json(CONFIG_DATA, data):
            self.configs['data'] = data
            return True
        return False
    
    def get_mail_config(self):
        return self.configs.get('mail', self._default_mail())
    
    def save_mail_config(self, data):
        if self._save_json(CONFIG_MAIL, data):
            self.configs['mail'] = data
            return True
        return False
    
    def get_opensky_config(self):
        return self.configs.get('opensky', self._default_opensky())
    
    def save_opensky_config(self, data):
        if self._save_json(CONFIG_OPENSKY, data):
            self.configs['opensky'] = data
            return True
        return False
    
    def get_airlines(self):
        return self.configs.get('airlines', {})
    
    def get_countries(self):
        return self.configs.get('countries', {})
    
    def get_aircraft_models(self):
        return self.configs.get('aircraft_models', {})
    
    def get_noise_impact(self):
        return self.configs.get('noise_impact', {})
    
    def save_airlines(self, data):
        return self._save_json(RULES_AIRLINES, data)
    
    def save_countries(self, data):
        return self._save_json(RULES_COUNTRIES, data)
    
    def save_aircraft_models(self, data):
        return self._save_json(RULES_AIRCRAFT_MODELS, data)
    
    def save_noise_impact(self, data):
        return self._save_json(RULES_NOISE_IMPACT, data)
    
    def reload(self):
        self.load_all()
        logger.info("Configurazioni ricaricate")


config_manager = ConfigManager()