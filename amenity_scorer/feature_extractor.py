"""
feature_extractor.py — Extract 150–400 features from raw POI data.

Covers:
  - Raw counts, densities, and proximities per POI type and radius
  - Category aggregations (healthcare, education, shopping, …)
  - Quality ratios (hospital/clinic, university/school, …)
  - Gravity model accessibility scores
  - Shannon entropy and category balance
  - Spatial clustering (DBSCAN, Nearest-Neighbour Index, Moran's I)
  - Temporal accessibility (opening hours heuristics)
  - Brand / chain presence
  - Multi-radius density gradients
  - Simpson's diversity and Gini coefficient
  - Proximity decay curves
  - Cross-radius gradients and composite scores
"""

import logging
from collections import Counter
from typing import Dict, List, Optional

import numpy as np
from scipy.stats import entropy

try:
    from scipy.spatial import distance_matrix as scipy_distance_matrix
    from sklearn.cluster import DBSCAN

    _SKLEARN = True
except ImportError:
    _SKLEARN = False
    logging.getLogger(__name__).warning(
        "scikit-learn not installed — spatial clustering disabled"
    )

import config
from utils import gini_coefficient, safe_divide

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """
    Extract all features from a list of POI dicts.

    Each POI dict must have at minimum: poi_type (str), distance_km (float).
    Spatial features additionally require: lat (float), lon (float).
    """

    def __init__(self):
        self.radii = config.RADII  # e.g. [500, 1000, 2000]
        self.categories = config.CATEGORIES  # {category: [poi_type, …]}
        self.poi_weights = config.POI_WEIGHTS  # {category: {poi_type: weight}}
        self.premium_brands = config.PREMIUM_BRANDS  # {category: [brand_name, …]}
        self.gradient_radii = config.GRADIENT_RADII  # e.g. [0.5, 1.0, 1.5, 2.0]

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def extract_all(self, lat: float, lon: float, pois: List[Dict]) -> Dict:
        """
        Extract all features for a location.

        Args:
            lat, lon: Location coordinates.
            pois:     Raw POI list from POIFetcher.

        Returns:
            Flat feature dict (str → numeric).
        """
        # Sanitise: require poi_type and distance_km
        pois = [p for p in pois if p.get("poi_type") and "distance_km" in p]

        features: Dict = {"latitude": lat, "longitude": lon, "total_pois": len(pois)}

        features.update(self._raw_poi_features(pois))
        features.update(self._category_features(features, pois))
        features.update(self._quality_features(pois))
        features.update(self._gravity_features(pois))
        features.update(self._diversity_features(pois))
        features.update(self._economic_features(pois))
        features.update(self._cross_radius_features(pois))
        features.update(self._composite_features(features, pois))
        features.update(self._temporal_features(pois))
        features.update(self._brand_features(pois))
        features.update(self._gradient_features(pois))
        features.update(self._advanced_spatial_features(pois))
        features.update(self._advanced_diversity_features(pois))
        features.update(self._proximity_decay_features(pois))

        return features

    def _raw_poi_features(self, pois: List[Dict]) -> Dict:
        """Count, density, and proximity for every POI type found."""
        features: Dict = {}
        poi_types = {p["poi_type"] for p in pois}

        for poi_type in poi_types:
            type_pois = [p for p in pois if p["poi_type"] == poi_type]
            distances = [p["distance_km"] for p in type_pois]

            for radius_m in self.radii:
                r_km = radius_m / 1000
                in_r = [p for p in type_pois if p["distance_km"] <= r_km]
                area = np.pi * r_km**2
                total_in_r = sum(1 for p in pois if p["distance_km"] <= r_km)

                features[f"{poi_type}_count_{radius_m}m"] = len(in_r)
                features[f"{poi_type}_density_{radius_m}m"] = safe_divide(
                    len(in_r), area
                )
                features[f"{poi_type}_pct_{radius_m}m"] = safe_divide(
                    len(in_r) * 100, total_in_r
                )

            features[f"nearest_{poi_type}_km"] = min(distances)
            features[f"avg_dist_{poi_type}_km"] = float(np.mean(distances))

        return features

    def _category_features(self, raw: Dict, pois: List[Dict]) -> Dict:
        """Aggregate counts, densities, and diversity per category."""
        features: Dict = {}
        for cat, types in self.categories.items():
            cat_pois = [p for p in pois if p.get("poi_type") in types]
            features[f"{cat}_total_count"] = len(cat_pois)
            features[f"{cat}_total_density"] = sum(
                raw.get(f"{t}_density_1000m", 0) for t in types
            )
            unique = {p["poi_type"] for p in cat_pois}
            features[f"{cat}_diversity"] = safe_divide(len(unique), len(types))
        return features

    def _quality_features(self, pois: List[Dict]) -> Dict:
        """Premium-to-basic ratios for key categories."""

        def _count_types(type_list: List[str]) -> int:
            return sum(1 for p in pois if p.get("poi_type") in type_list)

        return {
            "health_quality_ratio": safe_divide(
                _count_types(config.PREMIUM_POIS["healthcare"]),
                _count_types(config.BASIC_POIS["healthcare"]) + 1,
            ),
            "education_quality_ratio": safe_divide(
                _count_types(config.PREMIUM_POIS["education"]),
                _count_types(config.BASIC_POIS["education"]) + 1,
            ),
            "retail_sophistication": safe_divide(
                _count_types(config.PREMIUM_POIS["shopping"]),
                _count_types(config.BASIC_POIS["shopping"]) + 1,
            ),
            "transport_quality": safe_divide(
                _count_types(config.PREMIUM_POIS["transport"]),
                _count_types(config.BASIC_POIS["transport"]) + 1,
            ),
        }

    def _gravity_features(self, pois: List[Dict]) -> Dict:
        """Weighted inverse-square accessibility score per category."""
        features: Dict = {}
        for cat, types in self.categories.items():
            score = 0.0
            for p in pois:
                if p.get("poi_type") in types:
                    w = self.poi_weights.get(cat, {}).get(p["poi_type"], 1.0)
                    d = max(p["distance_km"], 0.1)
                    score += w / (d**2)
            features[f"gravity_{cat}"] = score
        return features

    def _diversity_features(self, pois: List[Dict]) -> Dict:
        features: Dict = {}
        types = [p["poi_type"] for p in pois if p.get("poi_type")]

        if types:
            counts = np.array(list(Counter(types).values()), dtype=float)
            probs = counts / counts.sum()
            features["amenity_entropy"] = float(entropy(probs))
        else:
            features["amenity_entropy"] = 0.0

        features["unique_amenity_types"] = len(set(types))

        cat_counts = [
            sum(1 for p in pois if p.get("poi_type") in t)
            for t in self.categories.values()
        ]
        total = sum(cat_counts)
        if total > 0:
            cat_probs = np.array(cat_counts, dtype=float) / total
            features["category_balance"] = float(entropy(cat_probs))
        else:
            features["category_balance"] = 0.0

        return features

    def _economic_features(self, pois: List[Dict]) -> Dict:
        """Estimate economic activity proxies from POI density within 1km."""

        def _density(types, r=1.0):
            # Use the correct area for the given radius
            area = np.pi * r**2
            return safe_divide(
                sum(
                    1
                    for p in pois
                    if p.get("poi_type") in types and p["distance_km"] <= r
                ),
                area,
            )

        emp_density = _density(config.CATEGORIES["employment"])
        cons_density = _density(
            config.CATEGORIES["shopping"] + config.CATEGORIES["food"]
        )
        prem_pct = safe_divide(
            sum(1 for p in pois if p.get("poi_type") in config.PREMIUM_POIS["premium"]),
            len(pois),
        )

        return {
            "employment_density": emp_density,
            "consumption_intensity": cons_density,
            "premium_presence": prem_pct,
            "income_proxy_score": emp_density * 0.4
            + cons_density * 0.3
            + prem_pct * 100 * 0.3,
        }

    def _cross_radius_features(self, pois: List[Dict]) -> Dict:
        def _density(r_km):
            return safe_divide(
                sum(1 for p in pois if p["distance_km"] <= r_km),
                np.pi * r_km**2,
            )

        d500, d1000, d2000 = _density(0.5), _density(1.0), _density(2.0)

        def _grad(outer, inner):
            if inner > 0:
                return safe_divide(outer, inner)
            return 1.0  # Neutral if inner is 0 (prevents spurious sprawl detection)

        return {
            "density_gradient_500_1000": _grad(d1000, d500),
            "density_gradient_1000_2000": _grad(d2000, d1000),
            "overall_density_gradient": _grad(d2000, d500),
        }

    def _composite_features(self, features: Dict, pois: List[Dict]) -> Dict:
        d500 = safe_divide(
            sum(1 for p in pois if p["distance_km"] <= 0.5), np.pi * 0.25
        )
        d2000 = safe_divide(
            sum(1 for p in pois if p["distance_km"] <= 2.0), np.pi * 4.0
        )

        essential = ["supermarket", "pharmacy", "clinic", "bank", "atm"]
        available = sum(1 for e in essential if features.get(f"{e}_count_1000m", 0) > 0)

        all_types = {t for types in self.categories.values() for t in types}
        covered = sum(1 for t in all_types if features.get(f"{t}_count_1000m", 0) > 0)

        return {
            "centrality_score": safe_divide(d500, d2000),
            "self_sufficiency": safe_divide(available, len(essential)),
            "service_completeness": safe_divide(covered, len(all_types)),
        }

    def _temporal_features(self, pois: List[Dict]) -> Dict:
        """Opening-hours heuristics (24/7, weekend, evening).

        IMPORTANT: Only POIs with an *explicit* opening_hours tag are counted
        toward the weekend/evening metrics. POIs with no tag are excluded so
        the metrics reflect actual data rather than inflating to ~100% due to
        missing tags (the majority of OSM POIs have no opening_hours).
        A separate coverage key reports what fraction of POIs have any tag.
        """
        features: Dict = {}

        def _temporal(subset):
            if not subset:
                return {
                    "pct_24_7": 0.0,
                    "weekend_availability": 0.0,
                    "evening_availability": 0.0,
                    "hours_coverage_pct": 0.0,
                }
            tagged = [p for p in subset if p.get("opening_hours")]
            n_tagged = len(tagged)
            coverage = n_tagged / len(subset) * 100
            if n_tagged == 0:
                return {
                    "pct_24_7": 0.0,
                    "weekend_availability": 0.0,
                    "evening_availability": 0.0,
                    "hours_coverage_pct": coverage,
                }
            always = weekend = evening = 0
            for p in tagged:
                oh = p["opening_hours"]
                if oh == "24/7":
                    always += 1
                if "24/7" in oh or any(x in oh for x in ("Mo-Su", "Sa", "Su")):
                    weekend += 1
                if "24/7" in oh or any(x in oh for x in ("20:", "21:", "22:")):
                    evening += 1
            return {
                "pct_24_7": always / n_tagged * 100,
                "weekend_availability": weekend / n_tagged * 100,
                "evening_availability": evening / n_tagged * 100,
                "hours_coverage_pct": coverage,
            }

        global_t = _temporal(pois)
        features.update({f"global_{k}": v for k, v in global_t.items()})

        for cat, types in self.categories.items():
            cat_pois = [p for p in pois if p.get("poi_type") in types]
            if cat_pois:
                t = _temporal(cat_pois)
                features[f"{cat}_pct_24_7"] = t["pct_24_7"]
                features[f"{cat}_weekend_availability"] = t["weekend_availability"]
                features[f"{cat}_evening_availability"] = t["evening_availability"]
                features[f"{cat}_hours_coverage_pct"] = t["hours_coverage_pct"]

        return features

    def _brand_features(self, pois: List[Dict]) -> Dict:
        features: Dict = {}

        def _brand_stats(subset, brand_list):
            if not subset:
                return {
                    "premium_brand_count": 0,
                    "premium_brand_pct": 0.0,
                    "brand_diversity": 0.0,
                    "chain_presence_pct": 0.0,
                }
            n = len(subset)
            premium = 0
            for p in subset:
                text = " ".join(
                    [p.get("name", ""), p.get("brand", ""), p.get("operator", "")]
                ).lower()
                if any(b.lower() in text for b in brand_list):
                    premium += 1
            brands = [
                p.get("brand") or p.get("operator")
                for p in subset
                if p.get("brand") or p.get("operator")
            ]
            return {
                "premium_brand_count": premium,
                "premium_brand_pct": premium / n * 100,
                "brand_diversity": (
                    safe_divide(len(set(brands)), len(brands)) if brands else 0.0
                ),
                "chain_presence_pct": len(brands) / n * 100,
            }

        all_brands = [b for bl in self.premium_brands.values() for b in bl]
        g = _brand_stats(pois, all_brands)
        features.update({f"global_{k}": v for k, v in g.items()})

        for cat, types in self.categories.items():
            cat_pois = [p for p in pois if p.get("poi_type") in types]
            if cat_pois:
                b = _brand_stats(cat_pois, self.premium_brands.get(cat, all_brands))
                features[f"{cat}_premium_brand_count"] = b["premium_brand_count"]
                features[f"{cat}_premium_brand_pct"] = b["premium_brand_pct"]
                features[f"{cat}_brand_diversity"] = b["brand_diversity"]

        return features

    def _gradient_features(self, pois: List[Dict]) -> Dict:
        features: Dict = {}
        for cat, types in self.categories.items():
            densities = []
            for r in self.gradient_radii:
                cnt = sum(
                    1
                    for p in pois
                    if p.get("poi_type") in types and p.get("distance_km", 999) <= r
                )
                densities.append(safe_divide(cnt, np.pi * r**2))

            if len(densities) < 2:
                features[f"{cat}_density_gradient"] = 0.0
                features[f"{cat}_density_monotonic"] = 0.0
                continue

            grads = [densities[i + 1] - densities[i] for i in range(len(densities) - 1)]
            features[f"{cat}_density_gradient"] = float(np.mean(grads))
            features[f"{cat}_density_monotonic"] = (
                1.0 if all(g <= 0 for g in grads) else 0.0
            )
            features[f"{cat}_density_pattern"] = self._classify_density_pattern(grads)

            mean_d = np.mean(densities)
            if mean_d > 0:
                features[f"{cat}_density_stability_cv"] = max(
                    0.0, 100 * (1 - np.std(densities) / mean_d)
                )
            else:
                features[f"{cat}_density_stability_cv"] = 0.0

        return features

    @staticmethod
    def _classify_density_pattern(grads: List[float]) -> str:
        """Classify the spatial density gradient pattern.

        Gradients are density[r+1] - density[r]. Since density naturally
        decreases outward, negative gradients indicate normal outward decay.
          uniform   — density roughly constant across all radii (<0.5 change)
          core      — density drops steeply at first then flattens (dense core, sparse fringe)
          isolated  — single sharp concentration, then near-zero outward
          sprawl    — density increases or stays flat as radius grows (no clear centre)
        """
        if not grads:
            return "unknown"
        if all(abs(g) < 0.5 for g in grads):
            return "uniform"
        # All gradients strongly negative — density falling consistently outward
        if all(g < -0.5 for g in grads):
            return "core"
        # First gradient is large negative, last flattens — concentrated core then fringe
        if len(grads) >= 2 and grads[0] < -2 and grads[-1] > -0.5:
            return "isolated"
        # Density not decreasing monotonically — no clear focal point
        return "sprawl"

    def _advanced_spatial_features(self, pois: List[Dict]) -> Dict:
        base = {
            "global_dbscan_n_clusters": 0,
            "global_dbscan_cluster_score": 0.0,
            "global_nearest_neighbor_index": 0.0,
            "global_hotspot_intensity": 0.0,
            "global_morans_i": 0.0,
            "global_distance_gini": 0.0,
        }
        if not _SKLEARN or len(pois) < 3:
            return base

        coords = np.array(
            [[p["lat"], p["lon"]] for p in pois if "lat" in p and "lon" in p]
        )
        if len(coords) < 3:
            return base

        # Convert degree coords to km for correct Euclidean distance at India's latitudes.
        # At ~20°N: 1° lat ≈ 111.32 km, 1° lon ≈ 111.32 × cos(20°) ≈ 104.6 km.
        mean_lat_r = np.radians(coords[:, 0].mean())
        scale = np.array([111.32, 111.32 * np.cos(mean_lat_r)])
        coords_km = coords * scale

        labels = (
            DBSCAN(
                eps=config.SPATIAL_CLUSTERING_EPS_KM,  # km-space, not degrees
                min_samples=config.SPATIAL_CLUSTERING_MIN_SAMPLES,
            )
            .fit(coords_km)
            .labels_
        )

        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        cluster_score = safe_divide(n_clusters * 100, len(coords_km))

        # Nearest-Neighbour Index — computed in km-space
        dm = scipy_distance_matrix(coords_km, coords_km)
        np.fill_diagonal(dm, np.inf)
        avg_nn = float(np.mean(np.min(dm, axis=1)))
        area_km2 = np.pi * 2.0**2  # 2km radius catchment in km²
        expected_nn = 0.5 / np.sqrt(safe_divide(len(coords_km), area_km2))
        nni = safe_divide(avg_nn, expected_nn, default=1.0)

        # Hotspot intensity
        if n_clusters > 0:
            sizes = [list(labels).count(i) for i in set(labels) if i != -1]
            hotspot = safe_divide(max(sizes) * 100, len(coords_km))
        else:
            hotspot = 0.0

        result = {
            "global_dbscan_n_clusters": n_clusters,
            "global_dbscan_cluster_score": min(100.0, cluster_score),
            "global_nearest_neighbor_index": nni,
            "global_hotspot_intensity": hotspot,
            "global_morans_i": self._morans_i(coords_km),
            "global_distance_gini": float(
                gini_coefficient(np.array([p["distance_km"] for p in pois]))
            ),
        }

        # Per-category DBSCAN, hotspot, AND per-category NNI
        for cat, types in self.categories.items():
            cat_pois = [p for p in pois if p.get("poi_type") in types]
            if len(cat_pois) >= 3:
                cat_coords = np.array(
                    [[p["lat"], p["lon"]] for p in cat_pois if "lat" in p]
                )
                if len(cat_coords) >= 3:
                    # Scale to km-space for this category
                    cat_coords_km = cat_coords * scale
                    cat_labels = (
                        DBSCAN(
                            eps=config.SPATIAL_CLUSTERING_EPS_KM,  # km-space
                            min_samples=config.SPATIAL_CLUSTERING_MIN_SAMPLES,
                        )
                        .fit(cat_coords_km)
                        .labels_
                    )
                    n_c = len(set(cat_labels)) - (1 if -1 in cat_labels else 0)
                    result[f"{cat}_dbscan_n_clusters"] = n_c
                    result[f"{cat}_dbscan_cluster_score"] = min(
                        100.0, safe_divide(n_c * 100, len(cat_coords_km))
                    )
                    if n_c > 0:
                        s = [
                            list(cat_labels).count(i)
                            for i in set(cat_labels)
                            if i != -1
                        ]
                        result[f"{cat}_hotspot_intensity"] = safe_divide(
                            max(s) * 100, len(cat_coords_km)
                        )
                    else:
                        result[f"{cat}_hotspot_intensity"] = 0.0
                    # Per-category NNI (km-space)
                    cat_dm = scipy_distance_matrix(cat_coords_km, cat_coords_km)
                    np.fill_diagonal(cat_dm, np.inf)
                    cat_avg_nn = float(np.mean(np.min(cat_dm, axis=1)))
                    cat_area_km2 = np.pi * 2.0**2
                    cat_expected_nn = 0.5 / np.sqrt(
                        safe_divide(len(cat_coords_km), cat_area_km2)
                    )
                    result[f"{cat}_nearest_neighbor_index"] = safe_divide(
                        cat_avg_nn, cat_expected_nn, default=1.0
                    )

        return result

    @staticmethod
    def _morans_i(coords: np.ndarray) -> float:
        """
        Moran's I spatial autocorrelation (-1 dispersed, 0 random, +1 clustered).

        Uses inverse-distance row-standardised weights and distance-from-centroid
        as the attribute variable.
        """
        if len(coords) < 4:
            return 0.0
        try:
            dm = scipy_distance_matrix(coords, coords).astype(float)
            # Avoid division by zero on diagonal or duplicate points
            with np.errstate(divide="ignore", invalid="ignore"):
                W = 1.0 / dm
            W[np.isinf(W)] = 0.0
            np.fill_diagonal(W, 0.0)  # No self-influence
            row_sums = W.sum(axis=1, keepdims=True)
            row_sums[row_sums == 0] = 1.0
            W /= row_sums

            centroid = coords.mean(axis=0)
            x = np.array([np.linalg.norm(c - centroid) for c in coords])
            n, xbar = len(x), x.mean()
            z = x - xbar
            numerator = float(np.dot(z, W @ z))
            denom = float(np.dot(z, z))
            W_sum = float(W.sum())
            if denom == 0 or W_sum == 0:
                return 0.0
            return float(np.clip((n / W_sum) * (numerator / denom), -1.0, 1.0))
        except Exception:
            return 0.0

    def _advanced_diversity_features(self, pois: List[Dict]) -> Dict:
        types = [p["poi_type"] for p in pois if p.get("poi_type")]
        if not types:
            return {
                "global_simpson_diversity": 0.0,
                "global_gini_coefficient": 0.0,
                "global_category_balance_gini": 0.0,
            }

        counts = np.array(list(Counter(types).values()), dtype=float)
        n = counts.sum()
        simpson = float(1 - np.sum((counts / n) ** 2)) * 100

        cat_counts = np.array(
            [
                sum(1 for p in pois if p.get("poi_type") in t)
                for t in self.categories.values()
            ],
            dtype=float,
        )
        cat_gini = (
            gini_coefficient(cat_counts[cat_counts > 0])
            if cat_counts.sum() > 0
            else 0.0
        )

        return {
            "global_simpson_diversity": simpson,
            "global_gini_coefficient": float(gini_coefficient(counts)),
            "global_category_balance_gini": (1 - cat_gini) * 100,
        }

    def _proximity_decay_features(self, pois: List[Dict]) -> Dict:
        base = {
            "global_distance_p25": 0.0,
            "global_distance_median": 0.0,
            "global_distance_p75": 0.0,
            "global_distance_p90": 0.0,
            "global_poi_concentration_500m": 0.0,
            "global_poi_concentration_1000m": 0.0,
            "global_distance_variance": 0.0,
            "global_distance_skewness": 0.0,
        }
        if not pois:
            return base

        d = np.array([p["distance_km"] for p in pois if "distance_km" in p])
        if len(d) == 0:
            return base

        std = float(np.std(d))
        skew = float(np.mean(((d - d.mean()) / std) ** 3)) if std > 0 else 0.0

        result = {
            "global_distance_p25": float(np.percentile(d, 25)),
            "global_distance_median": float(np.percentile(d, 50)),
            "global_distance_p75": float(np.percentile(d, 75)),
            "global_distance_p90": float(np.percentile(d, 90)),
            "global_poi_concentration_500m": float(np.mean(d <= 0.5) * 100),
            "global_poi_concentration_1000m": float(np.mean(d <= 1.0) * 100),
            "global_distance_variance": float(np.var(d)),
            "global_distance_skewness": skew,
        }

        for cat, types in self.categories.items():
            cat_d = np.array(
                [
                    p["distance_km"]
                    for p in pois
                    if p.get("poi_type") in types and "distance_km" in p
                ]
            )
            if len(cat_d) > 0:
                result[f"{cat}_distance_median"] = float(np.median(cat_d))
                result[f"{cat}_poi_concentration_500m"] = float(
                    np.mean(cat_d <= 0.5) * 100
                )
                result[f"{cat}_distance_variance"] = float(np.var(cat_d))

        return result
