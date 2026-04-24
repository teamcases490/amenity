"""
amenity_calculator.py — Compute the final Amenity Index (0–100).

Aggregates weighted category scores and applies four additive penalties:
  1. Data quality  — penalises sparse OSM coverage
  2. Type Gini     — penalises unequal category distribution
  3. Diversity     — penalises low Simpson's diversity
  4. Missing essentials — penalises absence of critical categories

Classification thresholds (India-calibrated):
  Metro  ≥ 60
  Urban  ≥ 30
  Rural  < 30
"""

import logging
from typing import Dict, Optional

import config
import numpy as np

logger = logging.getLogger(__name__)

# Minimum score a category must achieve to be considered "present"
_ESSENTIAL_THRESHOLD = 10.0
_ESSENTIAL_CATEGORIES = frozenset({"healthcare", "essential", "transport"})


class AmenityCalculator:
    """
    Compute the final Amenity Index from per-category scores.

    Usage:
        calc = AmenityCalculator()
        result = calc.calculate(category_scores, total_pois=120, features=features)
    """

    def calculate(
        self,
        category_scores: Dict[str, Dict],
        total_pois: int = 0,
        features: Optional[Dict] = None,
    ) -> Dict:
        """
        Compute Amenity Index and classification.

        Args:
            category_scores: {category: {"score": float, "components": {...}}}
            total_pois:      Total POI count (for data quality penalty).
            features:        Feature dict (for Gini / Simpson penalties).

        Returns:
            {
                "amenity_index":  float,   # 0–100
                "classification": str,     # Metro / Urban / Rural
                "data_quality":   str,     # High / Medium / Low / Zero
                "penalties":      dict,    # breakdown of applied penalties
                "weighted_score": float,   # pre-penalty score
            }
        """
        features = features or {}

        # 1. Zero-POI guard
        # If no POIs were fetched (API failure / truly empty area),
        # return 0 immediately rather than a spurious floor score.
        if total_pois == 0:
            return {
                "amenity_index": 0.0,
                "classification": "Rural",
                "data_quality": "Zero",
                "penalties": {},
                "weighted_score": 0.0,
            }

        # 2. Weighted base score
        weighted = sum(
            category_scores.get(cat, {}).get("score", 0.0) * weight
            for cat, weight in config.CATEGORY_WEIGHTS.items()
        )

        # 3. Penalties (additive, capped at 50% total)
        penalties: Dict[str, float] = {}

        # Data quality
        thresholds = config.DATA_QUALITY_POI_THRESHOLDS
        pen_map = config.DATA_QUALITY_PENALTIES
        if total_pois < thresholds["very_sparse"]:
            penalties["data_quality"] = pen_map["very_sparse"]
        elif total_pois < thresholds["sparse"]:
            penalties["data_quality"] = pen_map["sparse"]
        elif total_pois < thresholds["moderate"]:
            penalties["data_quality"] = pen_map["moderate"]
        else:
            penalties["data_quality"] = 0.0

        # Type Gini — continuous linear penalty: P = G × 0.15
        gini = features.get("global_gini_coefficient", 0.0)
        penalties["type_gini"] = float(np.clip(gini * 0.15, 0.0, 0.15))

        # Simpson's diversity — continuous linear penalty: P = (1−D)×0.10
        simpson = features.get("global_simpson_diversity", 100.0)
        penalties["diversity"] = float(np.clip((1 - simpson / 100.0) * 0.10, 0.0, 0.10))

        # Missing essential categories: 3%/missing, cap 9%
        missing = sum(
            1
            for cat in _ESSENTIAL_CATEGORIES
            if category_scores.get(cat, {}).get("score", 0.0) < _ESSENTIAL_THRESHOLD
        )
        penalties["missing_essentials"] = min(missing * 0.03, 0.09)

        total_penalty = min(sum(penalties.values()), 0.50)
        amenity_index = float(np.clip(weighted * (1 - total_penalty), 0, 100))

        return {
            "amenity_index": round(amenity_index, 2),
            "classification": self._classify(amenity_index),
            "data_quality": self._data_quality_label(total_pois),
            "penalties": {k: round(v, 4) for k, v in penalties.items()},
            "weighted_score": round(weighted, 2),
        }

    @staticmethod
    def _classify(score: float) -> str:
        if score >= 60:
            return "Metro"
        if score >= 30:
            return "Urban"
        return "Rural"

    @staticmethod
    def _data_quality_label(total_pois: int) -> str:
        """Labels aligned with DATA_QUALITY_POI_THRESHOLDS (5, 20, 40)."""
        if total_pois == 0:
            return "Zero"
        if total_pois < 5:
            return "Very Low"
        if total_pois < 20:
            return "Low"
        if total_pois < 40:
            return "Medium"
        return "High"
