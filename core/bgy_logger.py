"""
core/bgy_logger.py - Modulo di Logging centralizzato con log giornaliero.
- Ogni giorno crea un file bgy_app_YYYY-MM-DD.log
- I log più vecchi di 7 giorni vengono spostati in logs/archive/
"""
import os
import logging
import shutil
from datetime import datetime, timedelta
from core.bgy_paths import LOGS_DIR

ARCHIVE_DIR = os.path.join(LOGS_DIR, "archive")
ARCHIVE_DAYS = 7


def _get_today_log_path():
    """Restituisce il percorso del log di oggi."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(LOGS_DIR, f"bgy_app_{date_str}.log")


def _archive_old_logs():
    """Sposta i log più vecchi di ARCHIVE_DAYS giorni in logs/archive/."""
    try:
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        threshold = datetime.now() - timedelta(days=ARCHIVE_DAYS)

        for f in os.listdir(LOGS_DIR):
            if not f.startswith("bgy_app_") or not f.endswith(".log"):
                continue
            filepath = os.path.join(LOGS_DIR, f)
            if not os.path.isfile(filepath):
                continue

            # Estrai data dal nome: bgy_app_YYYY-MM-DD.log
            try:
                date_str = f.replace("bgy_app_", "").replace(".log", "")
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

    def __init__(self, log_dir, prefix="bgy_app", encoding="utf-8"):
        self.log_dir = log_dir
        self.prefix = prefix
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        filename = os.path.join(log_dir, f"{prefix}_{self.current_date}.log")
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

    # Archivia i log vecchi all'avvio
    _archive_old_logs()

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        fh = DailyFileHandler(LOGS_DIR, prefix="bgy_app", encoding="utf-8")
        fh.setLevel(logging.INFO)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        formatter = logging.Formatter('%(asctime)s - [%(name)s] - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        logger.addHandler(fh)
        logger.addHandler(ch)

    return logger