"""
Dynamic Feature Extractor
==========================

Extracts 150-400 features dynamically based on available POIs.
"""

import numpy as np
from typing import List, Dict
from collections import Counter
from scipy.stats import entropy
from sklearn.cluster import DBSCAN

import amenity_v1.config
from amenity_v1.advanced_features import AdvancedFeatureExtractor


class FeatureExtractor:
    """
    Extract ALL features dynamically from POIs.
    
    Features extracted:
    - Raw POI features (counts, densities, proximities) for EVERY POI type found
    - Category aggregations (healthcare, education, etc.)
    - Quality features (ratios, sophistication)
    - Gravity model features (accessibility)
    - Diversity features (entropy, unique types)
    - Spatial features (clustering, hotspots)
    - Economic features (employment, consumption)
    - Cross-radius features (gradients)
    - ADVANCED: Temporal, brand, multi-radius gradients, DBSCAN clustering
    """
    
    def __init__(self):
        self.radii = config.RADII
        self.poi_weights = config.POI_WEIGHTS
        self.density_thresholds = config.DENSITY_THRESHOLDS
        self.categories = config.CATEGORIES
        self.advanced_extractor = AdvancedFeatureExtractor()
    
    def extract_all_features(self, lat: float, lon: float, pois: List[Dict]) -> Dict:
        """
        Extract ALL features dynamically.
        
        Returns 150-400 features depending on POI availability.
        
        Args:
            lat: Latitude
            lon: Longitude
            pois: List of POI dictionaries
        
        Returns:
            Dictionary of features
        """
        features = {
            'latitude': lat,
            'longitude': lon,
            'total_pois': len(pois)
        }
        
        # Phase 0: Validate and sanitize POIs
        # Ensure all POIs have required keys to prevent downstream crashes
        valid_pois = []
        for p in pois:
            if 'poi_type' in p and 'distance_km' in p:
                valid_pois.append(p)
            else:
                # Log warning or just skip
                pass
        
        # Use sanitized list for all extractions
        pois = valid_pois
        features['total_pois'] = len(pois)
        
        # Phase 1: Raw POI features (dynamic - varies by location)
        features.update(self._extract_raw_poi_features(pois))
        
        # Phase 2: Category aggregations
        features.update(self._extract_category_features(features, pois))
        
        # Phase 3: Quality features
        features.update(self._extract_quality_features(pois))
        
        # Phase 4: Gravity model features
        features.update(self._extract_gravity_features(pois))
        
        # Phase 5: Diversity features
        features.update(self._extract_diversity_features(pois))
        
        # Phase 6: Spatial features
        features.update(self._extract_spatial_features(pois))
        
        # Phase 7: Economic features
        features.update(self._extract_economic_features(pois))
        
        # Phase 8: Cross-radius features
        features.update(self._extract_cross_radius_features(pois))
        
        # Phase 9: Composite features
        features.update(self._extract_composite_features(features, pois))
        
        # Phase 10: ADVANCED - Temporal accessibility
        features.update(self._extract_advanced_temporal_features(pois))
        
        # Phase 11: ADVANCED - Brand/chain presence
        features.update(self._extract_advanced_brand_features(pois))
        
        # Phase 12: ADVANCED - Multi-radius density gradients
        features.update(self._extract_advanced_gradient_features(pois))
        
        # Phase 13: ADVANCED - Enhanced spatial clustering
        features.update(self._extract_advanced_spatial_features(pois))
        
        # Phase 14: ADVANCED - Simpson's diversity & Gini coefficient
        features.update(self._extract_advanced_diversity_metrics(pois))
        
        # Phase 15: ADVANCED - Proximity decay curves
        features.update(self._extract_advanced_proximity_curves(pois))
        
        return features
    
    def _extract_raw_poi_features(self, pois: List[Dict]) -> Dict:
        """Extract features for EVERY POI type found."""
        features = {}
        
        poi_types = set(p['poi_type'] for p in pois if p.get('poi_type'))
        
        for poi_type in poi_types:
            type_pois = [p for p in pois if p.get('poi_type') == poi_type]
            
            # Count and density at each radius
            for radius_m in self.radii:
                radius_km = radius_m / 1000
                pois_in_radius = [p for p in type_pois if p['distance_km'] <= radius_km]
                
                features[f'{poi_type}_count_{radius_m}m'] = len(pois_in_radius)
                
                area_km2 = np.pi * radius_km**2
                features[f'{poi_type}_density_{radius_m}m'] = len(pois_in_radius) / area_km2 if area_km2 > 0 else 0
                
                total_in_radius = len([p for p in pois if p['distance_km'] <= radius_km])
                features[f'{poi_type}_pct_{radius_m}m'] = (
                    len(pois_in_radius) / total_in_radius * 100 if total_in_radius > 0 else 0
                )
            
            # Proximity features
            if type_pois:
                distances = [p['distance_km'] for p in type_pois]
                features[f'nearest_{poi_type}_km'] = min(distances)
                features[f'avg_dist_{poi_type}_km'] = np.mean(distances)
        
        return features
    
    def _extract_category_features(self, raw_features: Dict, pois: List[Dict]) -> Dict:
        """
        Aggregate features into categories.
        
        IMPORTANT: Counts POIs from the FULL list (all radii) to match what
        the category scorer uses. This ensures consistency between features
        and scoring calculations.
        """
        features = {}
        
        for category, poi_types in self.categories.items():
            # Count POIs from full list (matches what scorer uses)
            category_pois = [p for p in pois if p.get('poi_type') in poi_types]
            total_count = len(category_pois)
            features[f'{category}_total_count'] = total_count
            
            # Total density (still use 1000m for density calculations)
            total_density = sum(
                raw_features.get(f'{pt}_density_1000m', 0) for pt in poi_types
            )
            features[f'{category}_total_density'] = total_density
            
            # Diversity (from full list)
            unique_types = set(p.get('poi_type') for p in category_pois)
            features[f'{category}_diversity'] = len(unique_types) / len(poi_types) if poi_types else 0
        
        return features
    
    def _extract_quality_features(self, pois: List[Dict]) -> Dict:
        """Extract quality ratios."""
        features = {}
        
        # Healthcare quality
        hospital_count = len([p for p in pois if p.get('poi_type') == 'hospital' and p['distance_km'] <= 1.0])
        clinic_count = len([p for p in pois if p.get('poi_type') == 'clinic' and p['distance_km'] <= 1.0])
        features['health_quality_ratio'] = hospital_count / (clinic_count + 1)
        
        # Education quality
        university_count = len([p for p in pois if p.get('poi_type') == 'university' and p['distance_km'] <= 1.0])
        school_count = len([p for p in pois if p.get('poi_type') == 'school' and p['distance_km'] <= 1.0])
        features['education_quality_ratio'] = university_count / (school_count + 1)
        
        # Retail sophistication
        mall_count = len([p for p in pois if p.get('poi_type') == 'mall' and p['distance_km'] <= 1.0])
        shop_count = len([p for p in pois if p.get('poi_type') == 'shop' and p['distance_km'] <= 1.0])
        features['retail_sophistication'] = mall_count / (shop_count + 1)
        
        # Transport quality
        metro_count = len([p for p in pois if p.get('poi_type') in ['station', 'subway'] and p['distance_km'] <= 1.0])
        bus_count = len([p for p in pois if p.get('poi_type') == 'bus_stop' and p['distance_km'] <= 1.0])
        features['transport_quality'] = metro_count / (bus_count + 1)
        
        return features
    
    def _extract_gravity_features(self, pois: List[Dict]) -> Dict:
        """Extract gravity model features (accessibility)."""
        features = {}
        
        for category, poi_types in self.categories.items():
            gravity_score = 0.0
            
            for poi in pois:
                poi_type = poi.get('poi_type')
                if poi_type in poi_types:
                    weight = self.poi_weights.get(category, {}).get(poi_type, 1.0)
                    distance = max(poi['distance_km'], 0.1)
                    gravity_score += weight / (distance ** 2)
            
            features[f'gravity_{category}'] = gravity_score
        
        return features
    
    def _extract_diversity_features(self, pois: List[Dict]) -> Dict:
        """Extract diversity features."""
        features = {}
        
        poi_types = [p['poi_type'] for p in pois if p.get('poi_type')]
        
        if poi_types:
            type_counts = Counter(poi_types)
            type_probs = np.array(list(type_counts.values())) / len(poi_types)
            features['amenity_entropy'] = entropy(type_probs)
        else:
            features['amenity_entropy'] = 0
        
        features['unique_amenity_types'] = len(set(poi_types))
        
        # Category balance
        category_counts = []
        for category, poi_types_list in self.categories.items():
            count = sum(1 for p in pois if p.get('poi_type') in poi_types_list)
            category_counts.append(count)
        
        if category_counts and sum(category_counts) > 0:
            category_probs = np.array(category_counts) / sum(category_counts)
            features['category_balance'] = entropy(category_probs)
        else:
            features['category_balance'] = 0
        
        return features
    
    def _extract_spatial_features(self, pois: List[Dict]) -> Dict:
        """Extract spatial clustering features."""
        features = {}
        
        if len(pois) < 5:
            features['clustering_coefficient'] = 0
            features['hotspot_intensity'] = 0
            features['spatial_concentration'] = 0
            return features
        
        # DBSCAN clustering
        coords = np.array([[p['lat'], p['lon']] for p in pois])
        clustering = DBSCAN(eps=0.002, min_samples=3).fit(coords)
        labels = clustering.labels_
        
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        features['clustering_coefficient'] = n_clusters / len(pois) if pois else 0
        
        if n_clusters > 0:
            cluster_sizes = [np.sum(labels == i) for i in range(n_clusters)]
            features['hotspot_intensity'] = max(cluster_sizes) / len(pois)
        else:
            features['hotspot_intensity'] = 0
        
        # Spatial concentration (Gini coefficient)
        distances = [p['distance_km'] for p in pois]
        if distances:
            sorted_dist = np.sort(distances)
            n = len(sorted_dist)
            sum_dist = np.sum(sorted_dist)
            
            # FIX: Handle case where all distances are zero (all POIs at same location)
            if sum_dist == 0:
                # All POIs at same point = perfect concentration, Gini = 0 (no inequality in distances)
                features['spatial_concentration'] = 0
            else:
                index = np.arange(1, n + 1)
                features['spatial_concentration'] = (
                    (2 * np.sum(index * sorted_dist)) / (n * sum_dist) - (n + 1) / n
                )
        else:
            features['spatial_concentration'] = 0
        
        return features
    
    def _extract_economic_features(self, pois: List[Dict]) -> Dict:
        """Extract economic activity features."""
        features = {}
        
        # Employment density
        employment_types = ['office', 'coworking_space', 'business']
        employment_pois = [p for p in pois if p.get('poi_type') in employment_types and p['distance_km'] <= 1.0]
        features['employment_density'] = len(employment_pois) / (np.pi * 1.0**2)
        
        # Consumption intensity
        consumption_types = ['restaurant', 'cafe', 'shop', 'mall', 'supermarket']
        consumption_pois = [p for p in pois if p.get('poi_type') in consumption_types and p['distance_km'] <= 1.0]
        features['consumption_intensity'] = len(consumption_pois) / (np.pi * 1.0**2)
        
        # Premium presence
        premium_types = ['mall', 'hotel', 'gym', 'spa', 'golf_course', 'resort']
        premium_pois = [p for p in pois if p.get('poi_type') in premium_types]
        features['premium_presence'] = len(premium_pois) / len(pois) if pois else 0
        
        # Income proxy
        features['income_proxy_score'] = (
            features['employment_density'] * 0.4 +
            features['consumption_intensity'] * 0.3 +
            features['premium_presence'] * 100 * 0.3
        )
        
        return features
    
    def _extract_cross_radius_features(self, pois: List[Dict]) -> Dict:
        """Extract cross-radius gradient features."""
        features = {}
        
        density_500m = len([p for p in pois if p['distance_km'] <= 0.5]) / (np.pi * 0.5**2)
        density_1000m = len([p for p in pois if p['distance_km'] <= 1.0]) / (np.pi * 1.0**2)
        density_2000m = len([p for p in pois if p['distance_km'] <= 2.0]) / (np.pi * 2.0**2)
        
        # FIX: Properly handle "donut" patterns (empty core, populated ring)
        # If inner is 0 but outer > 0, this indicates a steep/infinite gradient, not uniform
        if density_500m > 0:
            features['density_gradient_500_to_1000'] = density_1000m / density_500m
        elif density_1000m > 0:
            features['density_gradient_500_to_1000'] = 10.0  # Steep gradient indicator
        else:
            features['density_gradient_500_to_1000'] = 1.0  # Both zero = uniform
        
        if density_1000m > 0:
            features['density_gradient_1000_to_2000'] = density_2000m / density_1000m
        elif density_2000m > 0:
            features['density_gradient_1000_to_2000'] = 10.0  # Steep gradient indicator
        else:
            features['density_gradient_1000_to_2000'] = 1.0  # Both zero = uniform
        
        if density_500m > 0:
            features['overall_density_gradient'] = density_2000m / density_500m
        elif density_2000m > 0:
            features['overall_density_gradient'] = 10.0  # Steep gradient indicator
        else:
            features['overall_density_gradient'] = 1.0  # Both zero = uniform
        
        return features
    
    def _extract_composite_features(self, features: Dict, pois: List[Dict]) -> Dict:
        """Extract composite features."""
        composite = {}
        
        # Centrality score
        density_500m = len([p for p in pois if p['distance_km'] <= 0.5]) / (np.pi * 0.5**2)
        density_2000m = len([p for p in pois if p['distance_km'] <= 2.0]) / (np.pi * 2.0**2)
        composite['centrality_score'] = density_500m / density_2000m if density_2000m > 0 else 0
        
        # Self-sufficiency
        essential_types = ['grocery', 'supermarket', 'pharmacy', 'clinic', 'bank', 'atm']
        available_essential = sum(
            1 for et in essential_types 
            if features.get(f'{et}_count_1000m', 0) > 0
        )
        composite['self_sufficiency'] = available_essential / len(essential_types)
        
        # Service completeness
        all_service_types = set()
        for category_types in self.categories.values():
            all_service_types.update(category_types)
        
        available_services = sum(
            1 for st in all_service_types 
            if features.get(f'{st}_count_1000m', 0) > 0
        )
        composite['service_completeness'] = available_services / len(all_service_types)
        
        return composite
    
    def _extract_advanced_temporal_features(self, pois: List[Dict]) -> Dict:
        """Extract temporal accessibility features for all POIs and by category."""
        features = {}
        
        # Global temporal features
        temporal = self.advanced_extractor.extract_temporal_features(pois)
        features.update({
            'global_pct_24_7': temporal['pct_24_7'],
            'global_weekend_availability': temporal['weekend_availability'],
            'global_evening_availability': temporal['evening_availability']
        })
        
        # Category-specific temporal features
        for category, category_types in self.categories.items():
            category_pois = [p for p in pois if p.get('poi_type') in category_types]
            if category_pois:
                cat_temporal = self.advanced_extractor.extract_temporal_features(category_pois)
                features[f'{category}_pct_24_7'] = cat_temporal['pct_24_7']
                features[f'{category}_weekend_availability'] = cat_temporal['weekend_availability']
                features[f'{category}_evening_availability'] = cat_temporal['evening_availability']
        
        return features
    
    def _extract_advanced_brand_features(self, pois: List[Dict]) -> Dict:
        """Extract brand/chain presence features for all POIs and by category."""
        features = {}
        
        # Global brand features
        brand = self.advanced_extractor.extract_brand_features(pois)
        features.update({
            'global_premium_brand_count': brand['premium_brand_count'],
            'global_premium_brand_pct': brand['premium_brand_pct'],
            'global_brand_diversity': brand['brand_diversity'],
            'global_chain_presence_pct': brand['chain_presence_pct']
        })
        
        # Category-specific brand features
        for category, category_types in self.categories.items():
            category_pois = [p for p in pois if p.get('poi_type') in category_types]
            if category_pois:
                cat_brand = self.advanced_extractor.extract_brand_features(category_pois, category)
                features[f'{category}_premium_brand_count'] = cat_brand['premium_brand_count']
                features[f'{category}_premium_brand_pct'] = cat_brand['premium_brand_pct']
                features[f'{category}_brand_diversity'] = cat_brand['brand_diversity']
        
        return features
    
    def _extract_advanced_gradient_features(self, pois: List[Dict]) -> Dict:
        """Extract multi-radius density gradient features by category."""
        features = {}
        
        # Category-specific gradients
        for category, category_types in self.categories.items():
            gradient = self.advanced_extractor.extract_density_gradients(pois, category_types)
            features[f'{category}_density_gradient'] = gradient['density_gradient_mean']
            features[f'{category}_density_concavity'] = gradient['density_concavity']
            features[f'{category}_density_monotonic'] = 1.0 if gradient['density_monotonic'] else 0.0
            features[f'{category}_density_stability_cv'] = gradient['density_stability_cv']
            features[f'{category}_density_pattern'] = gradient['density_pattern']
        
        return features
    
    def _extract_advanced_spatial_features(self, pois: List[Dict]) -> Dict:
        """Extract advanced spatial clustering features using DBSCAN."""
        features = {}
        
        # Global spatial features
        spatial = self.advanced_extractor.extract_advanced_spatial_features(pois)
        features.update({
            'global_dbscan_n_clusters': spatial['dbscan_n_clusters'],
            'global_dbscan_cluster_score': spatial['dbscan_cluster_score'],
            'global_nearest_neighbor_index': spatial['nearest_neighbor_index'],
            'global_hotspot_intensity': spatial['hotspot_intensity']
        })
        
        # Category-specific spatial features
        for category, category_types in self.categories.items():
            category_pois = [p for p in pois if p.get('poi_type') in category_types]
            if len(category_pois) >= 3:
                cat_spatial = self.advanced_extractor.extract_advanced_spatial_features(category_pois)
                features[f'{category}_dbscan_n_clusters'] = cat_spatial['dbscan_n_clusters']
                features[f'{category}_dbscan_cluster_score'] = cat_spatial['dbscan_cluster_score']
                features[f'{category}_hotspot_intensity'] = cat_spatial['hotspot_intensity']
        
        return features
    
    def _extract_advanced_diversity_metrics(self, pois: List[Dict]) -> Dict:
        """Extract Simpson's diversity index and Gini coefficient."""
        features = {}
        
        # Global diversity metrics
        diversity = self.advanced_extractor.extract_advanced_diversity_features(pois, self.categories)
        features.update({
            'global_simpson_diversity': diversity['simpson_diversity'],
            'global_gini_coefficient': diversity['gini_coefficient'],
            'global_category_balance_gini': diversity['category_balance_gini']
        })
        
        return features
    
    def _extract_advanced_proximity_curves(self, pois: List[Dict]) -> Dict:
        """Extract proximity decay curve features."""
        features = {}
        
        # Global proximity curves
        proximity = self.advanced_extractor.extract_proximity_decay_curves(pois)
        features.update({
            'global_distance_p25': proximity['distance_p25'],
            'global_distance_median': proximity['distance_median'],
            'global_distance_p75': proximity['distance_p75'],
            'global_distance_p90': proximity['distance_p90'],
            'global_poi_concentration_500m': proximity['poi_concentration_500m'],
            'global_poi_concentration_1000m': proximity['poi_concentration_1000m'],
            'global_distance_variance': proximity['distance_variance'],
            'global_distance_skewness': proximity['distance_skewness']
        })
        
        # Category-specific proximity curves
        for category, category_types in self.categories.items():
            category_pois = [p for p in pois if p.get('poi_type') in category_types]
            if category_pois:
                cat_proximity = self.advanced_extractor.extract_proximity_decay_curves(category_pois)
                features[f'{category}_distance_median'] = cat_proximity['distance_median']
                features[f'{category}_poi_concentration_500m'] = cat_proximity['poi_concentration_500m']
                features[f'{category}_distance_variance'] = cat_proximity['distance_variance']
        
        return features


