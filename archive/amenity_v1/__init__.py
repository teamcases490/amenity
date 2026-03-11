"""
Dynamic Amenity Feature Extraction System v2.0
===============================================

A production-ready system for extracting amenity features from OpenStreetMap data.
"""

__version__ = "2.0.0"

# Allow imports from package
from .poi_fetcher import POIFetcher
from .feature_extractor import FeatureExtractor
from .category_scorer import CategoryScorer
from .amenity_calculator import AmenityCalculator
from .utils import haversine_distance, setup_logging

__all__ = [
    'POIFetcher',
    'FeatureExtractor',
    'CategoryScorer',
    'AmenityCalculator',
    'haversine_distance',
    'setup_logging'
]
