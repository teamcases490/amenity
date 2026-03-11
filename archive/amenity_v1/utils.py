"""
Utility Functions
=================

Common utility functions used across the system.
"""

import time
import hashlib
import numpy as np
from datetime import datetime, timedelta


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safe division with configurable default value.
    
    Args:
        numerator: Numerator value
        denominator: Denominator value
        default: Value to return if division fails (default: 0.0)
    
    Returns:
        Result of division or default value
    
    Examples:
        >>> safe_divide(10, 2)
        5.0
        >>> safe_divide(10, 0)
        0.0
        >>> safe_divide(10, 0, default=1.0)
        1.0
    """
    if denominator == 0:
        return default
    try:
        result = numerator / denominator
        # Check for NaN or infinity
        if not (result == result and abs(result) != float('inf')):
            return default
        return result
    except (ZeroDivisionError, OverflowError, ValueError):
        return default


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points in kilometers using Haversine formula.
    
    Uses arctan2 instead of arcsin for better numerical stability.
    
    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates
    
    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth radius in km
    
    lat1_rad, lon1_rad = np.radians(lat1), np.radians(lon1)
    lat2_rad, lon2_rad = np.radians(lat2), np.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
    
    # Use arctan2 for better numerical stability (instead of arcsin)
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    
    return R * c


def generate_cache_key(lat: float, lon: float, radius_km: float) -> str:
    """
    Generate MD5 hash for cache key.
    
    Args:
        lat: Latitude
        lon: Longitude
        radius_km: Radius in kilometers
    
    Returns:
        MD5 hash string
    """
    # Round to 4 decimal places (~11m precision) to prevent cache misses
    lat_rounded = round(lat, 4)
    lon_rounded = round(lon, 4)
    key_str = f"{lat_rounded}_{lon_rounded}_{radius_km}"
    return hashlib.md5(key_str.encode()).hexdigest()


class RateLimiter:
    """
    Simple rate limiter for API calls.
    
    Ensures minimum time between requests to respect API rate limits.
    """
    
    def __init__(self, requests_per_second: float):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_second: Maximum requests per second
        """
        self.min_interval = 1.0 / requests_per_second
        self.last_request = 0.0
    
    def wait(self):
        """Wait if necessary to respect rate limit."""
        elapsed = time.time() - self.last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request = time.time()


def setup_logging():
    """
    Configure logging for the system.
    
    Returns:
        Logger instance
    """
    import logging
    from pathlib import Path
    
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"amenity_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger('amenity_system')
