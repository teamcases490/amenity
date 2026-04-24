"""
amenity_scorer
==============
India-calibrated amenity scoring system using OpenStreetMap POI data.

Public API:
    AmenityPipeline  — end-to-end pipeline (fetch → score → index)
    AmenityCalculator — final index + classification
    CategoryScorer   — per-category 6-component scoring
"""

from .amenity_calculator import AmenityCalculator
from .category_scorer import CategoryScorer
from .main import AmenityPipeline

__version__ = "2.0.0"
__all__ = ["AmenityPipeline", "AmenityCalculator", "CategoryScorer"]
