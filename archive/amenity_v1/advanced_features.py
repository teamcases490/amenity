"""
Advanced Feature Extraction
============================

Additional features for enhanced scoring:
- Temporal accessibility (opening hours)
- Multi-radius density gradients
- Brand/chain presence
- Advanced spatial clustering
"""

import numpy as np
from typing import Dict, List
from collections import Counter
import logging

try:
    from sklearn.cluster import DBSCAN
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning("scikit-learn not available, advanced spatial features disabled")

import amenity_v1.config

logger = logging.getLogger(__name__)


class AdvancedFeatureExtractor:
    """Extract advanced features from POI data."""
    
    def __init__(self):
        self.premium_brands = config.PREMIUM_BRANDS
        self.gradient_radii = config.GRADIENT_RADII
    
    def extract_temporal_features(self, pois: List[Dict]) -> Dict:
        """
        Extract temporal accessibility features from opening hours.
        
        Args:
            pois: List of POI dictionaries
        
        Returns:
            Dict of temporal features
        """
        if not pois:
            return {
                'pct_24_7': 0.0,
                'weekend_availability': 0.0,
                'evening_availability': 0.0
            }
        
        try:
            # Count 24/7 POIs
            always_open = sum(1 for p in pois if p.get('opening_hours') == '24/7')
            pct_24_7 = (always_open / len(pois)) * 100
            
            # For now, use simple heuristics (full opening_hours parsing would require additional library)
            # Weekend availability: assume POIs without hours are open, or have "Mo-Su" pattern
            weekend_open = 0
            evening_open = 0
            
            for poi in pois:
                oh = poi.get('opening_hours', '')
                
                # Weekend check
                if not oh or '24/7' in oh or 'Mo-Su' in oh or 'Sa' in oh or 'Su' in oh:
                    weekend_open += 1
                
                # Evening check (simple heuristic)
                if not oh or '24/7' in oh or '20:' in oh or '21:' in oh or '22:' in oh:
                    evening_open += 1
            
            weekend_availability = (weekend_open / len(pois)) * 100
            evening_availability = (evening_open / len(pois)) * 100
            
            return {
                'pct_24_7': pct_24_7,
                'weekend_availability': weekend_availability,
                'evening_availability': evening_availability
            }
        
        except Exception as e:
            logger.error(f"Error extracting temporal features: {e}")
            return {
                'pct_24_7': 0.0,
                'weekend_availability': 50.0,  # Default assume some availability
                'evening_availability': 50.0
            }
    
    def extract_brand_features(self, pois: List[Dict], category: str = None) -> Dict:
        """
        Extract brand/chain presence features.
        
        Args:
            pois: List of POI dictionaries
            category: Optional category to filter brands
        
        Returns:
            Dict of brand features
        """
        if not pois:
            return {
                'premium_brand_count': 0,
                'premium_brand_pct': 0.0,
                'brand_diversity': 0.0,
                'chain_presence_pct': 0.0
            }
        
        try:
            # Get relevant premium brands for category
            if category and category in self.premium_brands:
                premium_list = self.premium_brands[category]
            else:
                # Use all premium brands
                premium_list = []
                for brands in self.premium_brands.values():
                    premium_list.extend(brands)
            
            # Count premium brands
            premium_count = 0
            for poi in pois:
                name = poi.get('name', '').lower()
                brand = poi.get('brand', '').lower()
                operator = poi.get('operator', '').lower()
                
                # Check if any premium brand matches
                for premium in premium_list:
                    if premium.lower() in name or premium.lower() in brand or premium.lower() in operator:
                        premium_count += 1
                        break
            
            premium_brand_pct = (premium_count / len(pois)) * 100
            
            # Brand diversity
            brands = [p.get('brand', p.get('operator', '')) for p in pois if p.get('brand') or p.get('operator')]
            if brands:
                unique_brands = len(set(brands))
                brand_diversity = unique_brands / len(brands)
            else:
                brand_diversity = 0.0
            
            # Chain presence (has brand or operator field)
            chain_count = sum(1 for p in pois if p.get('brand') or p.get('operator'))
            chain_presence_pct = (chain_count / len(pois)) * 100
            
            return {
                'premium_brand_count': premium_count,
                'premium_brand_pct': premium_brand_pct,
                'brand_diversity': brand_diversity,
                'chain_presence_pct': chain_presence_pct
            }
        
        except Exception as e:
            logger.error(f"Error extracting brand features: {e}")
            return {
                'premium_brand_count': 0,
                'premium_brand_pct': 0.0,
                'brand_diversity': 0.0,
                'chain_presence_pct': 0.0
            }
    
    def extract_density_gradients(self, pois: List[Dict], category_types: List[str]) -> Dict:
        """
        Extract multi-radius density gradient features.
        
        Args:
            pois: List of POI dictionaries
            category_types: List of POI types for this category
        
        Returns:
            Dict of gradient features
        """
        if not pois:
            return {
                'density_gradient_mean': 0.0,
                'density_concavity': 0.0,
                'density_monotonic': False,
                'density_stability_cv': 0.0,
                'density_pattern': 'unknown'
            }
        
        try:
            # Calculate densities at each radius
            densities = []
            for r in self.gradient_radii:
                count = sum(1 for p in pois if p.get('distance_km', 999) <= r and p.get('poi_type') in category_types)
                density = count / (np.pi * r**2) if r > 0 else 0
                densities.append(density)
            
            if len(densities) < 2:
                return {
                    'density_gradient_mean': 0.0,
                    'density_concavity': 0.0,
                    'density_monotonic': False,
                    'density_stability_cv': 0.0,
                    'density_pattern': 'insufficient_data'
                }
            
            # First derivative (gradient)
            gradients = [densities[i+1] - densities[i] for i in range(len(densities)-1)]
            
            # Second derivative (concavity)
            if len(gradients) >= 2:
                concavity = [gradients[i+1] - gradients[i] for i in range(len(gradients)-1)]
                concavity_mean = np.mean(concavity)
            else:
                concavity_mean = 0.0
            
            # Monotonicity (should decrease outward for natural urban pattern)
            is_monotonic = all(g <= 0 for g in gradients)
            
            # Stability (coefficient of variation)
            if np.mean(densities) > 0:
                cv = np.std(densities) / np.mean(densities)
                stability_cv = max(0, 100 * (1 - cv))
            else:
                stability_cv = 0.0
            
            # Classify pattern
            pattern = self._classify_density_pattern(gradients)
            
            return {
                'density_gradient_mean': np.mean(gradients) if gradients else 0.0,
                'density_concavity': concavity_mean,
                'density_monotonic': is_monotonic,
                'density_stability_cv': stability_cv,
                'density_pattern': pattern
            }
        
        except Exception as e:
            logger.error(f"Error extracting density gradients: {e}")
            return {
                'density_gradient_mean': 0.0,
                'density_concavity': 0.0,
                'density_monotonic': False,
                'density_stability_cv': 0.0,
                'density_pattern': 'error'
            }
    
    def _classify_density_pattern(self, gradients: List[float]) -> str:
        """
        Classify urban density pattern from gradients.
        
        Args:
            gradients: List of density gradients
        
        Returns:
            Pattern classification string
        """
        if not gradients:
            return 'unknown'
        
        try:
            # Uniform: all gradients near zero
            if all(abs(g) < 0.5 for g in gradients):
                return 'uniform'
            
            # Core: steep initial drop, gradual later
            if len(gradients) >= 2 and gradients[0] < -2 and gradients[-1] > -0.5:
                return 'core'
            
            # Isolated: very steep drop
            if gradients[0] < -5:
                return 'isolated'
            
            # Sprawl: irregular pattern
            return 'sprawl'
        
        except Exception as e:
            logger.error(f"Error classifying pattern: {e}")
            return 'unknown'
    
    def extract_advanced_spatial_features(self, pois: List[Dict]) -> Dict:
        """
        Extract advanced spatial clustering features using DBSCAN.
        
        Args:
            pois: List of POI dictionaries
        
        Returns:
            Dict of spatial features
        """
        if not pois or len(pois) < 3:
            return {
                'dbscan_n_clusters': 0,
                'dbscan_cluster_score': 0.0,
                'nearest_neighbor_index': 0.0,
                'hotspot_intensity': 0.0
            }
        
        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn not available, returning default spatial features")
            return {
                'dbscan_n_clusters': 0,
                'dbscan_cluster_score': 0.0,
                'nearest_neighbor_index': 0.0,
                'hotspot_intensity': 0.0
            }
        
        try:
            # Prepare coordinates
            coords = np.array([[p['lat'], p['lon']] for p in pois if 'lat' in p and 'lon' in p])
            
            if len(coords) < 3:
                return {
                    'dbscan_n_clusters': 0,
                    'dbscan_cluster_score': 0.0,
                    'nearest_neighbor_index': 0.0,
                    'hotspot_intensity': 0.0
                }
            
            # DBSCAN clustering
            clustering = DBSCAN(
                eps=config.SPATIAL_CLUSTERING_EPS,
                min_samples=config.SPATIAL_CLUSTERING_MIN_SAMPLES
            ).fit(coords)
            
            labels = clustering.labels_
            n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
            n_noise = list(labels).count(-1)
            
            # Cluster score (higher = more clustered)
            if len(coords) > 0:
                cluster_score = (n_clusters / len(coords)) * 100
            else:
                cluster_score = 0.0
            
            # Nearest Neighbor Index (NNI)
            # Calculate average nearest neighbor distance
            from scipy.spatial import distance_matrix
            if len(coords) >= 2:
                dist_matrix = distance_matrix(coords, coords)
                np.fill_diagonal(dist_matrix, np.inf)  # Ignore self-distance
                nearest_distances = np.min(dist_matrix, axis=1)
                avg_nearest = np.mean(nearest_distances)
                
                # Expected distance for random distribution
                area = np.pi * 2**2  # Assuming 2km radius
                expected_dist = 0.5 / np.sqrt(len(coords) / area)
                
                # NNI = observed / expected (1 = random, <1 = clustered, >1 = dispersed)
                nni = avg_nearest / expected_dist if expected_dist > 0 else 1.0
            else:
                nni = 1.0
            
            # Hotspot intensity (largest cluster size as % of total)
            if n_clusters > 0:
                cluster_sizes = [list(labels).count(i) for i in set(labels) if i != -1]
                max_cluster_size = max(cluster_sizes) if cluster_sizes else 0
                hotspot_intensity = (max_cluster_size / len(coords)) * 100
            else:
                hotspot_intensity = 0.0
            
            return {
                'dbscan_n_clusters': n_clusters,
                'dbscan_cluster_score': min(100, cluster_score),
                'nearest_neighbor_index': nni,
                'hotspot_intensity': hotspot_intensity,
                'morans_i': self._calculate_morans_i(coords)
            }
        
        except Exception as e:
            logger.error(f"Error extracting advanced spatial features: {e}")
            return {
                'dbscan_n_clusters': 0,
                'dbscan_cluster_score': 0.0,
                'nearest_neighbor_index': 0.0,
                'hotspot_intensity': 0.0,
                'morans_i': 0.0
            }
    
    def _calculate_morans_i(self, coords: np.ndarray) -> float:
        """
        Calculate Moran's I spatial autocorrelation index.
        
        Moran's I ranges from -1 to +1:
        - +1: Perfect positive autocorrelation (clustered)
        - 0: Random spatial pattern
        - -1: Perfect negative autocorrelation (dispersed)
        
        Args:
            coords: Nx2 array of coordinates
        
        Returns:
            Moran's I value (-1 to +1)
        """
        try:
            if len(coords) < 4:
                return 0.0
            
            from scipy.spatial import distance_matrix
            
            # Create spatial weights matrix (inverse distance)
            dist_matrix = distance_matrix(coords, coords)
            np.fill_diagonal(dist_matrix, 1)  # Avoid division by zero
            
            # Inverse distance weights (closer = higher weight)
            weights = 1 / dist_matrix
            np.fill_diagonal(weights, 0)  # No self-weight
            
            # Normalize weights (row-standardization)
            row_sums = weights.sum(axis=1, keepdims=True)
            row_sums[row_sums == 0] = 1  # Avoid division by zero
            weights = weights / row_sums
            
            # Use distance from centroid as the attribute
            centroid = coords.mean(axis=0)
            values = np.array([np.linalg.norm(coord - centroid) for coord in coords])
            
            # Calculate Moran's I
            n = len(values)
            mean_val = values.mean()
            
            # Numerator: sum of weighted cross-products
            numerator = 0
            for i in range(n):
                for j in range(n):
                    numerator += weights[i, j] * (values[i] - mean_val) * (values[j] - mean_val)
            
            # Denominator: variance * sum of weights
            variance = ((values - mean_val) ** 2).sum()
            sum_weights = weights.sum()
            
            if variance == 0 or sum_weights == 0:
                return 0.0
            
            morans_i = (n / sum_weights) * (numerator / variance)
            
            # Clip to valid range
            return max(-1.0, min(1.0, morans_i))
            
        except Exception as e:
            logger.error(f"Error calculating Moran's I: {e}")
            return 0.0
    
    def extract_advanced_diversity_features(self, pois: List[Dict], categories: Dict) -> Dict:
        """
        Extract advanced diversity metrics: Simpson's index and Gini coefficient.
        
        Args:
            pois: List of POI dictionaries
            categories: Category mapping dictionary
        
        Returns:
            Dict of advanced diversity features
        """
        if not pois:
            return {
                'simpson_diversity': 0.0,
                'gini_coefficient': 0.0,
                'category_balance_gini': 0.0
            }
        
        try:
            # Get POI type counts
            poi_types = [p.get('poi_type') for p in pois if p.get('poi_type')]
            if not poi_types:
                return {
                    'simpson_diversity': 0.0,
                    'gini_coefficient': 0.0,
                    'category_balance_gini': 0.0
                }
            
            type_counts = Counter(poi_types)
            n = len(poi_types)
            
            # Simpson's Diversity Index: D = 1 - Σ(n_i/N)^2
            # Ranges from 0 (no diversity) to 1 (maximum diversity)
            simpson = 1 - sum((count/n)**2 for count in type_counts.values())
            simpson_score = simpson * 100  # Convert to 0-100 scale
            
            # Gini Coefficient for POI types (measures inequality)
            counts_sorted = sorted(type_counts.values())
            if len(counts_sorted) > 1:
                cumsum = np.cumsum(counts_sorted)
                gini = (2 * np.sum((np.arange(1, len(counts_sorted) + 1)) * counts_sorted)) / (len(counts_sorted) * np.sum(counts_sorted))
                gini = gini - (len(counts_sorted) + 1) / len(counts_sorted)
            else:
                gini = 0.0
            
            # Category balance using Gini
            category_counts = []
            for category_types in categories.values():
                count = sum(1 for p in pois if p.get('poi_type') in category_types)
                category_counts.append(count)
            
            if sum(category_counts) > 0:
                cat_counts_sorted = sorted([c for c in category_counts if c > 0])
                if len(cat_counts_sorted) > 1:
                    cat_gini = (2 * np.sum((np.arange(1, len(cat_counts_sorted) + 1)) * cat_counts_sorted)) / (len(cat_counts_sorted) * np.sum(cat_counts_sorted))
                    cat_gini = cat_gini - (len(cat_counts_sorted) + 1) / len(cat_counts_sorted)
                    category_balance_gini = (1 - cat_gini) * 100  # Invert so high = balanced
                else:
                    category_balance_gini = 0.0
            else:
                category_balance_gini = 0.0
            
            return {
                'simpson_diversity': simpson_score,
                'gini_coefficient': gini,
                'category_balance_gini': category_balance_gini
            }
        
        except Exception as e:
            logger.error(f"Error extracting advanced diversity features: {e}")
            return {
                'simpson_diversity': 0.0,
                'gini_coefficient': 0.0,
                'category_balance_gini': 0.0
            }
    
    def extract_proximity_decay_curves(self, pois: List[Dict]) -> Dict:
        """
        Extract proximity decay curve features.
        
        Analyzes the distance distribution of POIs to understand
        accessibility patterns.
        
        Args:
            pois: List of POI dictionaries
        
        Returns:
            Dict of proximity curve features
        """
        if not pois:
            return {
                'distance_p25': 0.0,
                'distance_median': 0.0,
                'distance_p75': 0.0,
                'distance_p90': 0.0,
                'poi_concentration_500m': 0.0,
                'poi_concentration_1000m': 0.0,
                'distance_variance': 0.0,
                'distance_skewness': 0.0
            }
        
        try:
            distances = [p.get('distance_km', 999) for p in pois if 'distance_km' in p]
            
            if not distances:
                return {
                    'distance_p25': 0.0,
                    'distance_median': 0.0,
                    'distance_p75': 0.0,
                    'distance_p90': 0.0,
                    'poi_concentration_500m': 0.0,
                    'poi_concentration_1000m': 0.0,
                    'distance_variance': 0.0,
                    'distance_skewness': 0.0
                }
            
            # Percentiles
            p25 = np.percentile(distances, 25)
            p50 = np.percentile(distances, 50)
            p75 = np.percentile(distances, 75)
            p90 = np.percentile(distances, 90)
            
            # Concentration indices
            within_500m = sum(1 for d in distances if d <= 0.5)
            within_1000m = sum(1 for d in distances if d <= 1.0)
            
            concentration_500m = (within_500m / len(distances)) * 100
            concentration_1000m = (within_1000m / len(distances)) * 100
            
            # Distance variance (spread)
            variance = np.var(distances)
            
            # Skewness (asymmetry of distribution)
            mean_dist = np.mean(distances)
            std_dist = np.std(distances)
            if std_dist > 0:
                skewness = np.mean(((np.array(distances) - mean_dist) / std_dist) ** 3)
            else:
                skewness = 0.0
            
            return {
                'distance_p25': p25,
                'distance_median': p50,
                'distance_p75': p75,
                'distance_p90': p90,
                'poi_concentration_500m': concentration_500m,
                'poi_concentration_1000m': concentration_1000m,
                'distance_variance': variance,
                'distance_skewness': skewness
            }
        
        except Exception as e:
            logger.error(f"Error extracting proximity decay curves: {e}")
            return {
                'distance_p25': 0.0,
                'distance_median': 0.0,
                'distance_p75': 0.0,
                'distance_p90': 0.0,
                'poi_concentration_500m': 0.0,
                'poi_concentration_1000m': 0.0,
                'distance_variance': 0.0,
                'distance_skewness': 0.0
            }
    
    def extract_all_advanced_features(self, lat: float, lon: float, pois: List[Dict]) -> Dict:
        """
        Extract all advanced features (wrapper method for compatibility).
        
        Args:
            lat: Latitude
            lon: Longitude
            pois: List of POI dictionaries
        
        Returns:
            Dict of all advanced features
        """
        features = {}
        
        try:
            # Temporal features
            features.update(self.extract_temporal_features(pois))
            
            # Brand features
            features.update(self.extract_brand_features(pois))
            
            # Advanced spatial features (DBSCAN, NNI, hotspots)
            features.update(self.extract_advanced_spatial_features(pois))
            
            # Diversity features (Simpson's, Gini)
            features.update(self.extract_advanced_diversity_features(pois, config.CATEGORIES))
            
            # Proximity decay curves
            features.update(self.extract_proximity_decay_curves(pois))
            
        except Exception as e:
            logger.error(f"Error extracting advanced features: {e}")
        
        return features


