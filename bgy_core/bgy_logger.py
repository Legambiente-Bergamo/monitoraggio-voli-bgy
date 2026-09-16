"""
bgy_core/bgy_logger.py - Modulo di Logging centralizzato con log giornaliero.
Versione 2.5.0
- archive_days, log_prefix e level da config_data.json (sezione "logging")
- fallback ai default se la config non è ancora caricata (bootstrap)
"""
import os
import logging
import shutil
from datetime import datetime, timedelta

from bgy_core.bgy_paths import LOGS_DIR

# Default (usati solo se config_manager non è ancora disponibile)
_DEFAULT_ARCHIVE_DAYS = 7
_DEFAULT_LOG_PREFIX = "bgy_app"
_DEFAULT_LEVEL = "INFO"

ARCHIVE_DIR = os.path.join(LOGS_DIR, "bgy_archive")


def _get_logging_cfg():
    """Legge la config logging. Fallback ai default in bootstrap."""
    try:
        from bgy_core.bgy_config_manager import config_manager
        cfg = config_manager.get_logging_config()
        return (
            int(cfg.get("archive_days", _DEFAULT_ARCHIVE_DAYS)),
            cfg.get("log_prefix", _DEFAULT_LOG_PREFIX),
            cfg.get("level", _DEFAULT_LEVEL),
        )
    except Exception:
        return _DEFAULT_ARCHIVE_DAYS, _DEFAULT_LOG_PREFIX, _DEFAULT_LEVEL


def _get_today_log_path():
    archive_days, prefix, _ = _get_logging_cfg()
    date_str = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(LOGS_DIR, f"{prefix}_{date_str}.log")


def _archive_old_logs():
    archive_days, prefix, _ = _get_logging_cfg()
    try:
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        threshold = datetime.now() - timedelta(days=archive_days)

        for f in os.listdir(LOGS_DIR):
            if not f.startswith(prefix + "_") or not f.endswith(".log"):
                continue
            filepath = os.path.join(LOGS_DIR, f)
            if not os.path.isfile(filepath):
                continue
            try:
                date_str = f.replace(prefix + "_", "").replace(".log", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                file_date = datetime.fromtimestamp(os.path.getmtime(filepath))

            if file_date < threshold:
                dest = os.path.join(ARCHIVE_DIR, f)
                if os.path.exists(dest):
                    os.remove(dest)
                shutil.move(filepath, dest)
    except Exception as e:
        print(f"[Logger] Errore archiviazione: {e}")


class DailyFileHandler(logging.FileHandler):
    """FileHandler che cambia automaticamente file al cambio di data."""

    def __init__(self, log_dir, prefix=None, encoding="utf-8"):
        _, cfg_prefix, _ = _get_logging_cfg()
        self.log_dir = log_dir
        self.prefix = prefix or cfg_prefix
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        filename = os.path.join(log_dir, f"{self.prefix}_{self.current_date}.log")
        super().__init__(filename, encoding=encoding, mode="a")

    def emit(self, record):
        try:
            new_date = datetime.now().strftime("%Y-%m-%d")
            if new_date != self.current_date:
                self.current_date = new_date
                new_filename = os.path.join(self.log_dir, f"{self.prefix}_{new_date}.log")
                if self.stream:
                    self.stream.close()
                self.baseFilename = os.path.abspath(new_filename)
                self.stream = self._open()
                _archive_old_logs()
        except Exception:
            pass
        super().emit(record)


def get_logger(name="BGY_App"):
    """Restituisce un logger configurato con log giornaliero."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    _archive_old_logs()

    _, _, level_name = _get_logging_cfg()
    level = getattr(logging, level_name.upper(), logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        fh = DailyFileHandler(LOGS_DIR, encoding="utf-8")
        fh.setLevel(level)

        ch = logging.StreamHandler()
        ch.setLevel(level)

        formatter = logging.Formatter('%(asctime)s - [%(name)s] - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger