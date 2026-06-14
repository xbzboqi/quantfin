"""Utility functions: logging, retry, trading calendar."""

import functools
import logging
import time
from datetime import date, datetime, timedelta
from typing import Callable, TypeVar

F = TypeVar("F", bound=Callable)


def setup_logger(name: str = "quantfin", level: int = logging.INFO) -> logging.Logger:
    """Create a simple console logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
        ))
        logger.addHandler(h)
    logger.setLevel(level)
    return logger


def retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    logger: logging.Logger | None = None,
) -> Callable:
    """Decorator: retry a function on specified exceptions with exponential backoff."""
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            _delay = delay
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_retries:
                        if logger:
                            logger.warning(
                                "%s failed (attempt %d/%d): %s. "
                                "Retrying in %.1fs...",
                                fn.__name__, attempt + 1, max_retries + 1, e, _delay,
                            )
                        time.sleep(_delay)
                        _delay *= backoff
            raise last_exc  # type: ignore[misc]
        return wrapper  # type: ignore[return-value]
    return decorator


def is_trading_day(d: date | None = None) -> bool:
    """Heuristic: trading days are weekdays excluding some Chinese holidays.

    Note: This is a simplified check. For production accuracy,
    AKShare's tool_trade_date_hist_sina() should be used.
    """
    if d is None:
        d = date.today()
    # Weekend
    if d.weekday() >= 5:
        return False
    # Simple hardcoded holiday list (extend as needed)
    holidays = {
        date(2026, 1, 1), date(2026, 1, 2),    # New Year
        date(2026, 1, 28), date(2026, 1, 29), date(2026, 1, 30),
        date(2026, 1, 31), date(2026, 2, 1), date(2026, 2, 2), date(2026, 2, 3),
        date(2026, 5, 1), date(2026, 5, 2), date(2026, 5, 3), date(2026, 5, 4),
        date(2026, 5, 5), date(2026, 5, 6),     # Labor Day
        date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3),
        date(2026, 10, 4), date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7),
    }
    if d in holidays:
        return False
    return True


def today_str(fmt: str = "%Y-%m-%d") -> str:
    return datetime.now().strftime(fmt)
