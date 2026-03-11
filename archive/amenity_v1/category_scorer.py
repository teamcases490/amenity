"""
Category Scorer
===============

Scores categories using 6 components:
1. Density (25%)
2. Proximity (20%)
3. Quality (20%)
4. Accessibility (15%)
5. Spatial (10%)
6. Economic (10%)
"""

import numpy as np
from typing import Dict, List
import logging

import amenity_v1.config
from amenity_v1.utils import haversine_distance

# Setup logging
logger = logging.getLogger(__name__)


class CategoryScorer:
    """Score categories using 6-component methodology."""
    
    def __init__(self):
        self.density_thresholds = config.DENSITY_THRESHOLDS
        self.categories = config.CATEGORIES
        self.component_weights = config.COMPONENT_WEIGHTS
    
    def calculate_category_score(self, category: str, features: Dict, pois: List[Dict]) -> Dict:
        """
        Calculate comprehensive category score with proper 6-component implementation.
        
        Args:
            category: Category name (e.g., 'healthcare')
            features: Extracted features dictionary
            pois: List of POI dictionaries
        
        Returns:
            Dictionary with 'score' and 'components' breakdown
        """
        # Input validation
        try:
            self._validate_inputs(category, features, pois)
        except ValueError as e:
            logger.error(f"Input validation failed for {category}: {e}")
            return {'score': 0.0, 'components': self._get_zero_components()}
        
        components = {}
        
        # Get category POIs
        try:
            category_pois = [p for p in pois if p.get('poi_type') in self.categories.get(category, [])]
        except Exception as e:
            logger.error(f"Error filtering category POIs for {category}: {e}")
            category_pois = []
        
        # Get ALL categorized POIs (for economic component denominator)
        try:
            all_categorized_pois = [
                p for p in pois 
                if any(p.get('poi_type') in cat_types for cat_types in self.categories.values())
            ]
        except Exception as e:
            logger.error(f"Error filtering all categorized POIs: {e}")
            all_categorized_pois = []
        
        # ===== COMPONENT 1: DENSITY (25%) =====
        components['density'] = self._calculate_density_component(category, features, category_pois)
        
        # ===== COMPONENT 2: PROXIMITY (20%) =====
        components['proximity'] = self._calculate_proximity_component(category_pois, category)
        
        # ===== COMPONENT 3: QUALITY (20%) =====
        components['quality'] = self._calculate_quality_component(category, features, category_pois)
        
        # ===== COMPONENT 4: ACCESSIBILITY (15%) =====
        components['accessibility'] = self._calculate_accessibility_component(category, features, category_pois)
        
        # ===== COMPONENT 5: SPATIAL (10%) =====
        components['spatial'] = self._calculate_spatial_component(category_pois, category, features)
        
        # ===== COMPONENT 6: ECONOMIC (10%) =====
        components['economic'] = self._calculate_economic_component(category_pois, all_categorized_pois, category)
        
        # **CRITICAL FIX**: Cap all components at 100 BEFORE calculating weighted score
        for key in components:
            components[key] = min(100, components[key])
        
        # DEBUG: Assert component ranges (helps catch calculation errors early)
        for comp_name, comp_value in components.items():
            assert 0 <= comp_value <= 100, f"{category} - {comp_name} out of range: {comp_value:.2f}"
        
        # Weighted combination (now using capped components)
        score = (
            components['density'] * self.component_weights['density'] +
            components['proximity'] * self.component_weights['proximity'] +
            components['quality'] * self.component_weights['quality'] +
            components['accessibility'] * self.component_weights['accessibility'] +
            components['spatial'] * self.component_weights['spatial'] +
            components['economic'] * self.component_weights['economic']
        )
        
        # ===== FIX: Dominance Penalty (Anti-Sprawl) =====
        # Penalize mono-use areas ONLY for large, diverse categories.
        # Skip for naturally single-type categories (civic, finance, premium).
        SKIP_DOMINANCE = {'civic', 'finance', 'premium'}
        if category not in SKIP_DOMINANCE and len(category_pois) >= 10:
            from collections import Counter
            poi_types = [p.get('poi_type') for p in category_pois if p.get('poi_type')]
            category_type_count = len(self.categories.get(category, []))
            if poi_types and category_type_count > 3:
                type_counts = Counter(poi_types)
                max_share = max(type_counts.values()) / len(poi_types)
                # If one POI type dominates > 50%, apply a soft penalty.
                # 50% share -> 0% penalty (multiplier 1.0)
                # 100% share -> 20% penalty (multiplier 0.8)
                if max_share > 0.5:
                    dominance_penalty = 1.0 - (max_share - 0.5) * 0.4
                    score *= dominance_penalty
        
        # Cap final score at 100
        score = min(100, score)
        
        return {
            'score': round(score, 1),
            'components': {k: round(v, 1) for k, v in components.items()}
        }
    
    def _calculate_density_component(self, category: str, features: Dict, category_pois: List[Dict]) -> float:
        """
        Component 1: Density (25%)
        Sub-components:
        - Raw density with log scaling (50%)
        - Relative density (30%)
        - Density stability (20%)
        
        IMPROVED: Uses logarithmic scaling above threshold to preserve variance
        """
        # Sub-component 1.1: Raw density with LOG SCALING (category-specific)
        density_key = f'{category}_total_density'
        density = features.get(density_key, 0)
        threshold = self.density_thresholds.get(category, 5.0)
        density_raw = self._calculate_density_score_log(density, threshold, category)
        
        # Sub-component 1.2: Relative density (% of total POIs)
        total_density = features.get('total_poi_density_1000m', 0)
        if total_density > 0:
            density_relative = (density / total_density) * config.RELATIVE_DENSITY_SCALE
            density_relative = min(density_relative, 100)
        else:
            density_relative = 0
        
        # Sub-component 1.3: Density stability (cross-radius consistency)
        # FIX: Calculate 2000m density correctly from raw features
        category_types = self.categories.get(category, [])
        density_2000 = sum(
            features.get(f'{pt}_density_2000m', 0) 
            for pt in category_types
        )
        
        if density > 0 and density_2000 > 0:
            # Stability = 1 - (relative difference)
            max_density = max(density, density_2000)
            stability = 1 - min(abs(density_2000 - density) / max_density, 1.0)
            density_stability = max(0, stability * 100)
        else:
            density_stability = 0  # FIX: Return 0 instead of 50 when no data (was causing 2.5 floor)
        
        # Weighted combination
        return (
            0.50 * density_raw +
            0.30 * density_relative +
            0.20 * density_stability
        )
    
    def _calculate_density_score_log(self, density: float, threshold: float, category: str = None) -> float:
        """
        Logarithmic density scoring with category-specific normalization.
        
        Linear below threshold (0-50), logarithmic above (50-100).
        
        Args:
            density: Category density (POIs/km²)
            threshold: Category-specific threshold
            category: Category name for specific normalization
        
        Returns:
            Score 0-100
        """
        if density <= 0:
            return 0
        
        ratio = density / threshold
        
        if ratio <= 1.0:
            # Linear below threshold: 0-50 range
            score = ratio * 50
        else:
            # Logarithmic above threshold: 50-100 range
            # Use category-specific normalization if available
            if category and category in config.CATEGORY_DENSITY_LOG_NORMALIZATION:
                log_norm = config.CATEGORY_DENSITY_LOG_NORMALIZATION[category]
            else:
                log_norm = config.DENSITY_LOG_NORMALIZATION
            
            score = 50 + 50 * np.log1p(ratio - 1) / np.log1p(log_norm)
        
        return min(score, 100)
    
    def _calculate_proximity_component(self, category_pois: List[Dict], category: str = None) -> float:
        """
        Component 2: Proximity (20%)
        Sub-components:
        - Nearest distance with exponential decay (70%)
        - Average distance (30%)
        
        IMPROVED: Uses exponential decay for smooth continuous scoring
        """
        if not category_pois:
            return 0
        
        # Sub-component 2.1: Nearest distance with EXPONENTIAL DECAY (category-specific)
        nearest_dist = min(p['distance_km'] for p in category_pois)
        proximity_nearest = self._calculate_proximity_score_exponential(nearest_dist, category)
        
        # Sub-component 2.2: Average distance with EXPONENTIAL DECAY
        avg_dist = np.mean([p['distance_km'] for p in category_pois])
        # Exponential decay with gentler 2km decay rate
        proximity_avg = 100 * np.exp(-avg_dist / config.PROXIMITY_DECAY_RATE_AVERAGE_KM)
        
        # Weighted combination
        return (
            0.70 * proximity_nearest +
            0.30 * proximity_avg
        )
    
    def _calculate_proximity_score_exponential(self, distance_km: float, category: str = None) -> float:
        """
        Exponential proximity decay with category-specific decay rates.
        
        Based on bid-rent theory (Alonso 1964): value decays exponentially with distance.
        
        Args:
            distance_km: Distance in kilometers
            category: Category name for specific decay rate
        
        Returns:
            Score 0-100
        """
        if distance_km <= 0.01:
            return 100
        
        # Use category-specific decay rate if available
        if category and category in config.CATEGORY_PROXIMITY_DECAY_RATES:
            decay_rate = config.CATEGORY_PROXIMITY_DECAY_RATES[category]
        else:
            decay_rate = config.PROXIMITY_DECAY_RATE_KM
        
        score = 100 * np.exp(-distance_km / decay_rate)
        
        return score
    
    def _calculate_quality_component(self, category: str, features: Dict, category_pois: List[Dict]) -> float:
        """
        Component 3: Quality (20%) - FIXED
        Use tiered quality ratios (premium/basic) for ALL categories.
        
        FIXED: No more diversity fallback! All categories use premium/basic ratio.
        """
        # Define premium and basic POI types for each category
        premium_types = {
            'healthcare': ['hospital'],
            'education': ['university', 'college'],
            'shopping': ['mall', 'department_store'],
            'transport': ['railway_station', 'subway_entrance', 'bus_station'],
            'food': ['restaurant', 'cafe'],
            'essential': ['supermarket', 'pharmacy', 'hospital'],
            'civic': ['government', 'embassy', 'townhall'],
            'cultural': ['museum', 'theatre', 'art_gallery', 'cinema'],
            'premium': ['spa', 'fitness_centre', 'golf_course'],
            'employment': ['building_commercial', 'building_office', 'office_company', 'office_government'],
            'finance': ['bank']
        }
        
        basic_types = {
            'healthcare': ['clinic', 'doctors', 'dentist'],
            'education': ['school', 'kindergarten'],
            'shopping': ['convenience', 'supermarket', 'marketplace'],
            'transport': ['bus_stop', 'taxi'],
            'food': ['fast_food', 'food_court'],
            'essential': ['convenience', 'general'],
            'civic': ['post_office', 'community_centre'],
            'cultural': ['place_of_worship', 'library'],
            'premium': ['beauty', 'hairdresser'],
            'employment': ['office_yes'],
            'finance': ['atm', 'bureau_de_change']
        }
        
        # Get premium and basic counts
        premium_list = premium_types.get(category, [])
        basic_list = basic_types.get(category, [])

        premium = sum(1 for p in category_pois if p.get('poi_type') in premium_list)
        basic = sum(1 for p in category_pois if p.get('poi_type') in basic_list)

        # Edge case: category has POIs but none match premium/basic lists.
        # Return a baseline score (30) to avoid unfairly zeroing out categories
        # like 'employment' or 'civic' whose POI types are mostly office/building tags.
        if premium == 0 and basic == 0 and category_pois:
            return 30.0

        # Calculate quality score using tiered ratio
        quality_score = self._calculate_quality_score_tiered(premium, basic, category)

        return quality_score
    
    def _calculate_quality_score_tiered(self, premium_count: int, basic_count: int, category: str) -> float:
        """
        Tiered quality scoring with category-specific thresholds.
        
        Tiers:
        - 0-20: No premium services
        - 20-50: Basic tier (some premium)
        - 50-75: Good tier (balanced mix)
        - 75-90: Excellent tier (premium dominant)
        - 90-100: Premium tier (ultra-premium)
        
        Args:
            premium_count: Count of premium POIs (hospitals, universities, malls, metro)
            basic_count: Count of basic POIs (clinics, schools, shops, bus stops)
            category: Category name for threshold lookup
        
        Returns:
            Score 0-100
        """
        if premium_count == 0:
            return 20 if basic_count > 0 else 0
        
        ratio = premium_count / (basic_count + 1)
        
        # Get category-specific thresholds
        thresholds = config.QUALITY_THRESHOLDS.get(category, config.QUALITY_THRESHOLDS['default'])
        t_low = thresholds['low']
        t_mid = thresholds['mid']
        t_high = thresholds['high']
        
        if ratio < t_low:
            # Basic tier: 20-50
            score = 20 + (ratio / t_low) * 30
        elif ratio < t_mid:
            # Good tier: 50-75
            score = 50 + ((ratio - t_low) / (t_mid - t_low)) * 25
        elif ratio < t_high:
            # Excellent tier: 75-90
            score = 75 + ((ratio - t_mid) / (t_high - t_mid)) * 15
        else:
            # Premium tier: 90-100 (logarithmic growth)
            score = 90 + min(10, np.log1p(ratio - t_high) * 5)
        
        return score
    
    def _calculate_accessibility_component(self, category: str, features: Dict, category_pois: List[Dict]) -> float:
        """
        Component 4: Accessibility (15%)
        Sub-components:
        - Gravity score with log scaling (70%)
        - Service completeness (30%)
        
        IMPROVED: Uses log scaling for gravity to handle wide range (0.1-100+)
        """
        # Sub-component 4.1: Gravity score with LOG SCALING
        gravity_key = f'gravity_{category}'
        gravity = features.get(gravity_key, 0)
        gravity_score = self._calculate_gravity_score_log(gravity)
        
        # Sub-component 4.2: Service completeness
        # (What % of category types are available?)
        category_types = self.categories.get(category, [])
        if category_types:
            available_types = set(p['poi_type'] for p in category_pois)
            completeness_score = (len(available_types) / len(category_types)) * 100
        else:
            completeness_score = 0
        
        # Weighted combination
        return (
            0.70 * gravity_score +
            0.30 * completeness_score
        )
    
    def _calculate_gravity_score_log(self, gravity: float) -> float:
        """
        Convert gravity to 0-100 score using SQRT SCALING - FIXED.
        
        FIXED: Changed from log to sqrt scaling to reduce ceiling effect.
        
        Args:
            gravity: Gravity score (typically 0.1 to 100+)
        
        Returns:
            Score 0-100
        """
        if gravity <= 0:
            return 0
        
        # FIXED: Use sqrt scaling instead of log (less aggressive)
        # gravity=1 → sqrt(1) * 10 = 10
        # gravity=10 → sqrt(10) * 10 = 32
        # gravity=50 → sqrt(50) * 10 = 71
        # gravity=100 → sqrt(100) * 10 = 100
        score = min(100, np.sqrt(gravity) * 10)
        
        return score
    
    def _calculate_spatial_component(self, category_pois: List[Dict], category: str, features: Dict) -> float:
        """
        Component 5: Spatial (10%)
        ENHANCED: Uses NNI, Moran's I, DBSCAN clustering, and hotspot detection
        
        Sub-components:
        - Nearest Neighbor Index (30%) - Clustering metric
        - Moran's I (25%) - Spatial autocorrelation
        - DBSCAN cluster score (25%) - Cluster detection
        - Hotspot intensity (20%) - Largest cluster
        """
        if len(category_pois) < 3:
            # Not enough POIs to compute meaningful spatial metrics.
            # Return neutral 50 (not 0) so lack of data doesn't unfairly penalize.
            return 50.0
        
        try:
            # Sub-component 5.1: Nearest Neighbor Index (30%)
            # NNI: <1 = clustered (good for urban), 1 = random, >1 = dispersed
            nni_key = f'{category}_nearest_neighbor_index'
            nni = features.get(nni_key, 1.0)
            
            # Normalize NNI to 0-100 score
            # Optimal NNI for urban areas: 0.5-1.0 (moderate clustering)
            # Too clustered (<0.5) = sprawl/malls
            # Too dispersed (>1.5) = sparse
            if nni < 0.5:
                nni_score = 50 + (nni / 0.5) * 50  # 0-100 for 0-0.5
            elif nni <= 1.0:
                nni_score = 100  # Optimal range
            elif nni <= 1.5:
                nni_score = 100 - ((nni - 1.0) / 0.5) * 50  # 100-50 for 1.0-1.5
            else:
                nni_score = max(0, 50 - (nni - 1.5) * 20)  # <50 for >1.5
            
            # Sub-component 5.2: Moran's I (25%)
            # Moran's I: -1 to +1 (we normalize to 0-100)
            morans_key = f'{category}_morans_i'
            morans_i = features.get(morans_key, 0.0)
            
            # Normalize Moran's I to 0-100
            # Positive values (clustered) are good for urban areas
            morans_score = (morans_i + 1) / 2 * 100  # -1→0, 0→50, +1→100
            
            # Sub-component 5.3: DBSCAN cluster score (25%)
            dbscan_score_key = f'{category}_dbscan_cluster_score'
            dbscan_score = features.get(dbscan_score_key, 0)
            
            # Sub-component 5.4: Hotspot intensity (20%)
            hotspot_key = f'{category}_hotspot_intensity'
            hotspot_score = features.get(hotspot_key, 0)
            
            # Weighted combination
            return (
                0.30 * nni_score +
                0.25 * morans_score +
                0.25 * dbscan_score +
                0.20 * hotspot_score
            )
        
        except Exception as e:
            logger.error(f"Error calculating spatial component for {category}: {e}")
            return 0
    
    def _calculate_economic_component(self, category_pois: List[Dict], all_categorized_pois: List[Dict], category: str) -> float:
        """
        Component 6: Economic (10%)
        Category intensity (% of total CATEGORIZED POIs) vs India-calibrated target.

        Uses a shifted sigmoid so that:
          - ratio = 1.0 (exactly at target) → ~75 score  (good)
          - ratio = 0.5 (half of target)    → ~40 score  (below average)
          - ratio = 2.0 (double target)     → ~95 score  (excellent)
          - ratio = 0.0 (none)              →   0 score

        Target percentages come from config.ECONOMIC_TARGET_PCT (India-calibrated).

        Args:
            category_pois: POIs in this category
            all_categorized_pois: All categorized POIs
            category: Category name for threshold lookup

        Returns:
            Economic score (0-100)
        """
        total_categorized = len(all_categorized_pois)
        if total_categorized == 0 or len(category_pois) == 0:
            return 0

        category_pct = (len(category_pois) / total_categorized) * 100

        # Use India-calibrated targets from config (not hardcoded here)
        target = config.ECONOMIC_TARGET_PCT.get(category, 10)

        if target <= 0:
            return 0

        ratio = category_pct / target

        # Shifted sigmoid: midpoint=0.7 so ratio=1.0 → ~75 score
        # steepness=3.5 gives smooth transition without hard clipping
        steepness = 3.5
        midpoint = 0.7

        score = 100 / (1 + np.exp(-steepness * (ratio - midpoint)))

        return min(100, max(0, score))
    
    def _validate_inputs(self, category: str, features: Dict, pois: List[Dict]) -> None:
        """
        Validate inputs to prevent errors.
        
        Args:
            category: Category name
            features: Features dictionary
            pois: List of POIs
        
        Raises:
            ValueError: If inputs are invalid
        """
        if not category:
            raise ValueError("Category cannot be empty")
        
        if features is None:
            raise ValueError("Features cannot be None")
        
        if not isinstance(features, dict):
            raise ValueError(f"Features must be dict, got {type(features)}")
        
        if pois is None:
            raise ValueError("POIs cannot be None")
        
        if not isinstance(pois, list):
            raise ValueError(f"POIs must be list, got {type(pois)}")
        
        # Validate POI structure
        for i, poi in enumerate(pois[:10]):  # Check first 10
            if not isinstance(poi, dict):
                raise ValueError(f"POI {i} must be dict, got {type(poi)}")
            
            if 'distance_km' not in poi:
                logger.warning(f"POI {i} missing 'distance_km', may cause issues")
    
    def _get_zero_components(self) -> Dict:
        """
        Return zero scores for all components.
        
        Returns:
            Dict with all components set to 0
        """
        return {
            'density': 0.0,
            'proximity': 0.0,
            'quality': 0.0,
            'accessibility': 0.0,
            'spatial': 0.0,
            'economic': 0.0
        }
    
    def _safe_divide(self, numerator: float, denominator: float, default: float = 0.0) -> float:
        """
        Safe division with default value.
        
        Args:
            numerator: Numerator
            denominator: Denominator
            default: Default value if division fails
        
        Returns:
            Result of division or default
        """
        try:
            if denominator == 0:
                return default
            result = numerator / denominator
            if not np.isfinite(result):
                logger.warning(f"Non-finite division result: {numerator}/{denominator}")
                return default
            return result
        except Exception as e:
            logger.error(f"Division error: {e}")
            return default
    
    def _safe_log(self, value: float, min_value: float = 0.01) -> float:
        """
        Safe logarithm with minimum value to prevent log(0).
        
        Args:
            value: Value to take log of
            min_value: Minimum value (prevents log(0))
        
        Returns:
            Logarithm or 0 if invalid
        """
        try:
            safe_value = max(value, min_value)
            result = np.log10(safe_value)
            if not np.isfinite(result):
                logger.warning(f"Non-finite log result for value: {value}")
                return np.log10(min_value)
            return result
        except Exception as e:
            logger.error(f"Log error for value {value}: {e}")
            return np.log10(min_value)

