"""
core/bgy_retry.py - Decorator per retry automatico su fallimenti API.
"""
import time
import functools
from core.bgy_logger import get_logger

logger = get_logger("Retry")


def retry_on_failure(max_retries=3, delay=1.0, backoff=2.0):
    """
    Decorator per retry automatico su fallimento di chiamate API.
    
    Args:
        max_retries: Numero massimo di tentativi
        delay: Ritardo iniziale in secondi
        backoff: Moltiplicatore del ritardo (backoff esponenziale)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_retries:
                        logger.warning(
                            f"Tentativo {attempt+1}/{max_retries} fallito per {func.__name__}: {str(e)[:100]}. "
                            f"Riprovo tra {current_delay:.1f}s"
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"Tutti i {max_retries+1} tentativi falliti per {func.__name__}: {str(e)[:200]}")
                        raise
            return None
        return wrapper
    return decorator