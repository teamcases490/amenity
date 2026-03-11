"""
utils.py — Shared utility functions.
"""

import time
import hashlib
import logging
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Union


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divide two numbers, returning `default` on zero/invalid denominator."""
    if denominator == 0:
        return default
    try:
        result = numerator / denominator
        if not (result == result) or abs(result) == float("inf"):
            return default
        return result
    except (ZeroDivisionError, OverflowError, ValueError):
        return default


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance between two points (Haversine formula).

    Uses arctan2 for better numerical stability near the poles.
    Returns distance in kilometres.
    """
    R = 6371.0
    lat1_r, lon1_r = np.radians(lat1), np.radians(lon1)
    lat2_r, lon2_r = np.radians(lat2), np.radians(lon2)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def gini_coefficient(values: np.ndarray) -> float:
    """
    Gini coefficient of an array (0 = perfect equality, 1 = maximum inequality).

    Uses the standard sorted-array formula.
    """
    if len(values) < 2 or values.sum() == 0:
        return 0.0
    # Ensure no negative values (Gini undefined for negative inputs)
    values = np.maximum(values, 0)
    sorted_v = np.sort(values)
    n = len(sorted_v)
    idx = np.arange(1, n + 1)
    return float(max(0.0, (2 * np.sum(idx * sorted_v)) / (n * sorted_v.sum()) - (n + 1) / n))


def cache_key(lat: float, lon: float, radius_km: float) -> str:
    """MD5 cache key for a (lat, lon, radius) triple (rounded to ~11 m precision)."""
    key = f"{round(lat, 4)}_{round(lon, 4)}_{radius_km}"
    return hashlib.md5(key.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Enforces a minimum inter-request interval for API calls."""

    def __init__(self, requests_per_second: float):
        self._interval = 1.0 / requests_per_second
        self._last = 0.0

    def wait(self) -> None:
        elapsed = time.time() - self._last
        if elapsed < self._interval:
            time.sleep(self._interval - elapsed)
        self._last = time.time()


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(name: str = "amenity_scorer", log_dir: Union[str, Path, None] = None) -> logging.Logger:
    """
    Configure file + console logging.

    Log files are written to `log_dir/amenity_YYYYMMDD.log`.
    Defaults to the project-root logs/ directory (config.LOG_DIR).
    Returns the named logger.
    """
    if log_dir is None:
        try:
            import config as _cfg  # lazy import to avoid circular deps
            log_dir = _cfg.LOG_DIR
        except Exception:
            log_dir = "logs"
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    log_file = log_path / f"amenity_{datetime.now().strftime('%Y%m%d')}.log"

    fmt = "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger(name)
