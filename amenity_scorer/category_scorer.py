"""
category_scorer.py — Score each amenity category on 6 components.

Components and weights (configurable in config.COMPONENT_WEIGHTS):
  1. Density      (25%) — POI count relative to urban benchmarks
  2. Proximity    (20%) — Distance to nearest POIs
  3. Quality      (20%) — Premium-to-basic POI ratio
  4. Accessibility(15%) — Gravity-model weighted access score
  5. Spatial      (10%) — Clustering and distribution
  6. Economic     (10%) — Category share vs India-calibrated target
"""

import logging
from collections import Counter
from typing import Dict, List, Tuple

import config
import numpy as np
from utils import safe_divide

logger = logging.getLogger(__name__)

# Categories that are naturally mono-type — skip dominance penalty
_SKIP_DOMINANCE = frozenset({"civic", "finance", "premium"})

# Max fractional penalty at full POI-type dominance (share=100% → ×0.8 reduction)
_DOMINANCE_PENALTY_MULTIPLIER = 0.4


class CategoryScorer:
    """
    Calculate a 0–100 score for each amenity category.

    Usage:
        scorer = CategoryScorer()
        result = scorer.score("healthcare", features, pois)
        # result = {"score": 72.4, "components": {...}}
    """

    def __init__(self):
        self.categories = config.CATEGORIES
        self.poi_weights = config.POI_WEIGHTS
        self.density_thresholds = config.DENSITY_THRESHOLDS
        self.component_weights = config.COMPONENT_WEIGHTS

    def score(self, category: str, features: Dict, pois: List[Dict]) -> Dict:
        """
        Score a single category.

        Args:
            category: Category name (must be a key in config.CATEGORIES).
            features: Feature dict from FeatureExtractor.
            pois:     Full POI list (all categories).

        Returns:
            {"score": float, "components": {component: float}}
        """
        if category not in self.categories:
            logger.warning(f"Unknown category: {category}")
            return {"score": 0.0, "components": {}}

        cat_pois = [p for p in pois if p.get("poi_type") in self.categories[category]]

        components = {
            "density": self._density(cat_pois, category),
            "proximity": self._proximity(cat_pois, category),
            "quality": self._quality(cat_pois, category),
            "accessibility": self._accessibility(cat_pois, category),
            "spatial": self._spatial(cat_pois, category, features),
            "economic": self._economic(cat_pois, pois, category),
        }

        raw_score = sum(
            components[c] * self.component_weights.get(c, 0) for c in components
        )

        # Soft dominance penalty: only for large, diverse categories
        if (
            category not in _SKIP_DOMINANCE
            and len(cat_pois) >= 10
            and len(self.categories.get(category, [])) > 3
        ):
            types = [p["poi_type"] for p in cat_pois if p.get("poi_type")]
            if types:
                max_share = max(Counter(types).values()) / len(types)
                if max_share > 0.5:
                    # Linear penalty: 50% share → ×1.0, 100% share → ×0.8
                    raw_score *= 1.0 - (max_share - 0.5) * _DOMINANCE_PENALTY_MULTIPLIER

        return {
            "score": round(float(np.clip(raw_score, 0, 100)), 2),
            "components": {k: round(float(v), 2) for k, v in components.items()},
        }

    def _density(self, cat_pois: List[Dict], category: str) -> float:
        """
        Score based on POI count relative to India-calibrated urban benchmarks.

        DENSITY_THRESHOLDS stores a single float per category representing the
        "good" benchmark (POIs per km² in a typical urban area). We derive
        excellent/fair from it and use a log-saturating curve.
        """
        # Multi-Radius Weighted Density Score
        # 500m (50%) -> Walkable / Immediate
        # 1km  (30%) -> Neighborhood / Short Drive
        # 2km  (20%) -> Catchment / Regional

        radii_weights = [(0.5, 0.5), (1.0, 0.3), (2.0, 0.2)]
        final_score = 0.0

        benchmark = self.density_thresholds.get(category, 2.0)  # POIs/km²

        for r_km, weight in radii_weights:
            count = sum(1 for p in cat_pois if p.get("distance_km", 9999) <= r_km)
            area_km2 = np.pi * r_km**2

            good = max(1, benchmark * area_km2)
            excellent = good * 2.5
            fair = good * 0.4

            if count == 0:
                r_score = 0.0
            elif count >= excellent:
                r_score = 100.0
            elif count >= good:
                r_score = 70.0 + 30.0 * (count - good) / (excellent - good)
            elif count >= fair:
                r_score = 40.0 + 30.0 * (count - fair) / (good - fair)
            else:
                r_score = max(0.0, 40.0 * count / max(fair, 1))

            final_score += r_score * weight

        return final_score

    def _proximity(self, cat_pois: List[Dict], category: str) -> float:
        """
        70/30 blend of nearest-POI score and average-distance score.

        Nearest-POI (70%): steep decay — dictates urgent / immediate accessibility.
          lambda=1.5 → 0.1km=86, 0.5km=47, 1.0km=22, 2.0km=5
        Average-distance (30%): uses only the 5 nearest POIs.
          Averaging all POIs within 2km biases the score toward the circle edge;
          restricting to the closest few better represents real user access.
        """
        if not cat_pois:
            return 0.0
        decay = config.CATEGORY_PROXIMITY_DECAY_RATES.get(category, 1.5)
        sorted_dists = sorted(p.get("distance_km", 9999) for p in cat_pois)
        nearest_km = sorted_dists[0]
        closest_5 = sorted_dists[:5]
        avg_km = sum(closest_5) / len(closest_5)
        s_min = 100.0 * np.exp(-decay * nearest_km)
        s_avg = 100.0 * np.exp(-(decay / 1.5) * avg_km)  # softer decay for average
        return float(0.70 * s_min + 0.30 * s_avg)

    # Premium and basic POI types per category (Centralized in config)
    _PREMIUM = config.PREMIUM_POIS
    _BASIC = config.BASIC_POIS

    def _quality(self, cat_pois: List[Dict], category: str) -> float:
        """Quality score based on premium-to-basic POI ratio.

        Requires a minimum of 3 matched POIs to produce a reliable ratio.
        With fewer, the score is scaled down to reflect insufficient data.
        """
        if not cat_pois:
            return 0.0

        premium_types = self._PREMIUM.get(category, [])
        basic_types = self._BASIC.get(category, [])
        premium = sum(1 for p in cat_pois if p.get("poi_type") in premium_types)
        basic = sum(1 for p in cat_pois if p.get("poi_type") in basic_types)

        if premium == 0 and basic == 0:
            return 0.0

        relevant_total = premium + basic
        if relevant_total == 0:
            return 0.0

        premium_ratio = safe_divide(premium, relevant_total)
        basic_ratio = safe_divide(basic, relevant_total)
        raw = float(
            np.clip(premium_ratio * 100 * 1.5 + basic_ratio * 100 * 0.5, 0, 100)
        )

        # Scale down when we have too few POIs for a reliable ratio.
        # 1 POI → 33%, 2 POIs → 66%, >=3 POIs → full score.
        # This prevents a single high-weight POI from dominating the category.
        if relevant_total < 3:
            raw *= relevant_total / 3.0

        return raw

    def _accessibility(self, cat_pois: List[Dict], category: str) -> float:
        """Gravity-model score: Σ weight / distance².

        Normalised to 100 so scores span the full 0–100 range:
          10 POIs at 0.5km weight=1  → Σ = 10/0.25 = 40  → score = 40
          10 POIs at 0.1km weight=1  → Σ = 10/0.01 = 1000 → score = 100 (capped)
          5  POIs at 0.3km weight=1.5 → Σ = 5*1.5/0.09 ≈ 83 → score = 83
        """
        if not cat_pois:
            return 0.0
        weights = self.poi_weights.get(category, {})
        score = sum(
            weights.get(p.get("poi_type", ""), 1.0)
            / max(p.get("distance_km", 9999), 0.1) ** 2
            for p in cat_pois
        )
        return float(np.clip(score / 100.0 * 100, 0, 100))

    def _spatial(self, cat_pois: List[Dict], category: str, features: Dict) -> float:
        """
        Spatial distribution quality.

        Returns 0 when fewer than 3 POIs — 1 or 2 isolated POIs give no
        meaningful spatial signal and should not contribute to the score.
        """
        if not cat_pois:
            return 0.0
        if len(cat_pois) < 3:
            return 0.0

        try:
            # Use category-specific NNI where available, fall back to global NNI.
            # Global NNI is used as fallback since per-category NNI is only computed
            # for categories with 3+ POIs (see _advanced_spatial_features).
            global_nni = features.get("global_nearest_neighbor_index", 1.0)
            nni = features.get(f"{category}_nearest_neighbor_index", global_nni)

            # Piecewise NNI score:
            # Optimal walkable range 0.5–1.0 scores 100.
            # Score drops for over-clustering (NNI < 0.5) or sprawl (NNI > 1.0).
            if nni < 0.5:
                nni_score = 50.0 + (nni / 0.5) * 50.0  # 0→50, 0.5→100
            elif nni <= 1.0:
                nni_score = 100.0  # optimal range
            elif nni <= 1.5:
                nni_score = 100.0 - ((nni - 1.0) / 0.5) * 50.0  # 1.0→100, 1.5→50
            else:
                nni_score = max(0.0, 50.0 - (nni - 1.5) * 20.0)  # >1.5 → sprawl
            nni_score = float(np.clip(nni_score, 0, 100))

            # Sub-component B: Hotspot intensity (Category specific)
            hotspot = features.get(f"{category}_hotspot_intensity", 0.0)
            hotspot_score = float(np.clip(hotspot, 0, 100))

            # 70% Hotspot (Local signal) + 30% NNI (Global signal)
            return 0.7 * hotspot_score + 0.3 * nni_score

        except Exception as exc:
            logger.debug(f"Spatial component fallback for {category}: {exc}")
            return 0.0

    def _economic(
        self, cat_pois: List[Dict], all_pois: List[Dict], category: str
    ) -> float:
        """
        Category share of total POIs vs India-calibrated target.

        Sigmoid centred at ratio=1.0 (at target) → 50 score.
          ratio = 0.5 → ~18   (below target)
          ratio = 1.0 → ~50   (at target)
          ratio = 2.0 → ~82   (double target)

        Minimum 3 POIs required for a stable economic signal. Fewer POIs
        are penalised because a single POI can artificially hit any target%.
        """
        if not cat_pois or not all_pois:
            return 0.0

        # Low confidence guard: 1-2 POIs cannot give a reliable economic signal
        n = len(cat_pois)
        if n < 3:
            confidence = n / 3.0  # 1 POI → 33%, 2 POIs → 66%
        else:
            confidence = 1.0

        category_pct = safe_divide(len(cat_pois) * 100, len(all_pois))
        target = config.ECONOMIC_TARGET_PCT.get(category, 10)
        ratio = safe_divide(category_pct, target)

        raw = float(np.clip(100 / (1 + np.exp(-4.0 * (ratio - 1.0))), 0, 100))
        return raw * confidence
