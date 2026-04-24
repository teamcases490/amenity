"""
local_feature_computer.py — Given a list of POIs (with lat/lon) and a list of
                             sample points inside a pincode polygon, compute all
                             features for EACH sample point using pure numpy math
                             (no additional API calls), then aggregate across points.

This replaces the API-per-point approach with O(n_pois × n_points) distance math,
which takes milliseconds even for 1000 POIs × 16 sample points.
"""

import sys
import os
import math
from typing import Dict, List, Tuple

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'amenity_scorer'))
import config
from utils import safe_divide

# ── Module-level singleton (instantiated once, reused for every sample point) ─
from feature_extractor import FeatureExtractor as _FeatureExtractor
_extractor = _FeatureExtractor()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_features_for_point(
    sample_lat: float,
    sample_lon: float,
    pois: List[Dict],
    max_radius_km: float = 2.0,
) -> Dict:
    """
    Compute all amenity features for a single sample point, given a pre-fetched
    list of POIs (already in the polygon's bbox area).

    POIs outside max_radius_km from this sample point are excluded BEFORE feature
    extraction — this mimics the centroid pipeline's radius filter.

    Returns a feature dict (same schema as FeatureExtractor.extract_all).
    """
    if not pois:
        return _empty_features(sample_lat, sample_lon)

    # Compute distances from this sample point to every POI
    relevant_pois = _attach_distances(sample_lat, sample_lon, pois, max_radius_km)

    if not relevant_pois:
        return _empty_features(sample_lat, sample_lon)

    # Now reuse the existing FeatureExtractor — module-level singleton
    return _extractor.extract_all(sample_lat, sample_lon, relevant_pois)


def aggregate_point_features(per_point_features: List[Dict]) -> Dict:
    """
    Aggregate feature dicts from multiple sample points into ONE representative
    feature dict per pincode.

    Aggregation strategy:
      - For scalar features: mean, max, std are computed
      - Final dict uses MEAN as the primary value (best for scoring)
      - Also includes _max and _std suffixed versions for ML models

    Returns a single merged feature dict.
    """
    if not per_point_features:
        return {}

    if len(per_point_features) == 1:
        return per_point_features[0]

    # Collect all numeric keys
    all_keys = set()
    for f in per_point_features:
        all_keys.update(k for k, v in f.items() if isinstance(v, (int, float)))

    merged = {}
    for key in all_keys:
        values = [f.get(key, 0.0) for f in per_point_features]
        arr = np.array(values, dtype=float)
        merged[key] = float(np.mean(arr))           # Primary — used by scorer
        merged[f"{key}_max"] = float(np.max(arr))
        merged[f"{key}_std"] = float(np.std(arr))

    # Preserve non-numeric keys from first point (lat, lon, etc.)
    first = per_point_features[0]
    for k, v in first.items():
        if not isinstance(v, (int, float)):
            merged[k] = v

    return merged


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _attach_distances(
    lat: float, lon: float,
    pois: List[Dict],
    max_radius_km: float,
) -> List[Dict]:
    """
    Return a copy of each POI with distance_km set from (lat, lon) to the POI.
    Filters to only POIs within max_radius_km.
    """
    relevant = []
    for poi in pois:
        dist = _haversine(lat, lon, poi["lat"], poi["lon"])
        if dist <= max_radius_km:
            relevant.append({**poi, "distance_km": dist})
    return relevant


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    rl = math.radians
    dlat = rl(lat2 - lat1)
    dlon = rl(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rl(lat1)) * math.cos(rl(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _empty_features(lat: float, lon: float) -> Dict:
    return {"latitude": lat, "longitude": lon, "total_pois": 0}
