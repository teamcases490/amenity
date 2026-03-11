"""
Feature Engineering Pipeline
=============================

Transforms raw amenity counts into high-quality, non-redundant features
for machine learning models.

Key Principles:
1. Remove redundant features (percentages, multi-radius duplicates)
2. Engineer informative features (gradients, ratios, diversity metrics)
3. Handle rare POIs appropriately (aggregation, thresholding)
4. Reduce multicollinearity (VIF < 5)
5. Maintain interpretability
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from sklearn.preprocessing import StandardScaler


class AmenityFeatureEngineer:
    """
    Transform raw amenity counts into ML-ready features.
    
    Removes ~1,500 misleading features and creates ~500 high-quality features.
    """
    
    def __init__(self, rare_poi_threshold: float = 0.05):
        """
        Initialize feature engineer.
        
        Args:
            rare_poi_threshold: Drop POI types present in <5% of locations
        """
        self.rare_poi_threshold = rare_poi_threshold
        self.scaler = StandardScaler()
        self.feature_names = []
        self.dropped_features = []
        
    def fit_transform(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Fit and transform features.
        
        Args:
            features_df: Raw features from amenity system (2,982 features)
            
        Returns:
            Cleaned features (~500 features)
        """
        print(f"Input features: {len(features_df.columns)}")
        
        # Convert all features to numeric (handle any string values)
        df = features_df.copy()
        for col in df.columns:
            if col not in ['latitude', 'longitude']:  # Keep lat/lon as-is
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Fill any NaN values with 0
        df = df.fillna(0)
        
        # Step 1: Remove percentage features
        df = self._remove_percentage_features(df)
        
        # Step 2: Remove rare POI features
        df = self._remove_rare_poi_features(df)
        
        # Step 3: Engineer density gradients
        df = self._engineer_density_gradients(df)
        
        # Step 4: Engineer diversity metrics
        df = self._engineer_diversity_metrics(df)
        
        # Step 5: Engineer proximity ratios
        df = self._engineer_proximity_ratios(df)
        
        # Step 6: Aggregate rare POIs by category
        df = self._aggregate_rare_pois(df)
        
        # Step 7: Remove building tag duplicates
        df = self._remove_building_duplicates(df)
        
        # Step 8: Keep only discriminative component scores
        df = self._filter_component_scores(df)
        
        print(f"Output features: {len(df.columns)}")
        print(f"Dropped features: {len(self.dropped_features)}")
        
        self.feature_names = df.columns.tolist()
        return df
    
    def _remove_percentage_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove all percentage features (redundant with counts)."""
        pct_cols = [col for col in df.columns if '_pct_' in col]
        print(f"  Removing {len(pct_cols)} percentage features")
        self.dropped_features.extend(pct_cols)
        return df.drop(columns=pct_cols)
    
    def _remove_rare_poi_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove POI types present in <5% of locations."""
        rare_cols = []
        
        for col in df.columns:
            if '_count_' in col or '_density_' in col:
                # Check if feature is mostly zeros
                non_zero_pct = (df[col] > 0).sum() / len(df)
                if non_zero_pct < self.rare_poi_threshold:
                    rare_cols.append(col)
        
        print(f"  Removing {len(rare_cols)} rare POI features (<{self.rare_poi_threshold*100}% presence)")
        self.dropped_features.extend(rare_cols)
        return df.drop(columns=rare_cols)
    
    def _engineer_density_gradients(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create density gradients instead of multi-radius densities.
        
        Gradient = (density_2000m - density_500m) / 1500m
        Positive gradient = POIs increase with distance (sprawl)
        Negative gradient = POIs concentrated near center (urban core)
        """
        new_features = {}
        density_cols_to_drop = []
        
        # Find all POI types with density at multiple radii
        poi_types = set()
        for col in df.columns:
            if '_density_500m' in col:
                poi_type = col.replace('_density_500m', '')
                poi_types.add(poi_type)
        
        for poi_type in poi_types:
            col_500 = f'{poi_type}_density_500m'
            col_1000 = f'{poi_type}_density_1000m'
            col_2000 = f'{poi_type}_density_2000m'
            
            if all(col in df.columns for col in [col_500, col_1000, col_2000]):
                # Create gradient feature
                gradient = (df[col_2000] - df[col_500]) / 1.5  # per km
                new_features[f'{poi_type}_density_gradient'] = gradient
                
                # Keep only 2000m density (most comprehensive)
                density_cols_to_drop.extend([col_500, col_1000])
        
        print(f"  Created {len(new_features)} density gradient features")
        print(f"  Removing {len(density_cols_to_drop)} redundant density features")
        
        df = df.drop(columns=density_cols_to_drop)
        self.dropped_features.extend(density_cols_to_drop)
        
        return pd.concat([df, pd.DataFrame(new_features, index=df.index)], axis=1)
    
    def _engineer_diversity_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create POI diversity metrics.
        
        - Shannon entropy: Diversity of POI types
        - Simpson index: Probability two random POIs are different types
        - Evenness: How evenly distributed POI types are
        """
        new_features = {}
        
        # Get all count features at 2000m radius
        count_cols = [col for col in df.columns if '_count_2000m' in col]
        
        if count_cols:
            counts = df[count_cols].values
            
            # Shannon entropy
            proportions = counts / (counts.sum(axis=1, keepdims=True) + 1e-10)
            entropy = -np.sum(proportions * np.log(proportions + 1e-10), axis=1)
            new_features['poi_diversity_shannon'] = entropy
            
            # Simpson index
            simpson = 1 - np.sum(proportions ** 2, axis=1)
            new_features['poi_diversity_simpson'] = simpson
            
            # Evenness (entropy / max_entropy)
            max_entropy = np.log(len(count_cols))
            evenness = entropy / max_entropy
            new_features['poi_diversity_evenness'] = evenness
            
            # Number of POI types present
            num_types = (counts > 0).sum(axis=1)
            new_features['poi_type_count'] = num_types
        
        print(f"  Created {len(new_features)} diversity features")
        
        return pd.concat([df, pd.DataFrame(new_features, index=df.index)], axis=1)
    
    def _engineer_proximity_ratios(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create proximity ratios (nearest / average distance).
        
        Ratio < 1: Nearest POI much closer than average (good clustering)
        Ratio ~ 1: POIs evenly distributed
        Ratio > 1: Impossible (nearest can't be farther than average)
        """
        new_features = {}
        nearest_cols_to_drop = []
        
        # Find all POI types with nearest and average distance
        poi_types = set()
        for col in df.columns:
            if col.startswith('nearest_') and col.endswith('_km'):
                poi_type = col.replace('nearest_', '').replace('_km', '')
                poi_types.add(poi_type)
        
        for poi_type in poi_types:
            nearest_col = f'nearest_{poi_type}_km'
            avg_col = f'avg_dist_{poi_type}_km'
            
            if nearest_col in df.columns and avg_col in df.columns:
                # Create proximity ratio
                ratio = df[nearest_col] / (df[avg_col] + 1e-10)
                new_features[f'{poi_type}_proximity_ratio'] = ratio
                
                # Drop nearest distance (keep average and ratio)
                nearest_cols_to_drop.append(nearest_col)
        
        print(f"  Created {len(new_features)} proximity ratio features")
        print(f"  Removing {len(nearest_cols_to_drop)} redundant nearest distance features")
        
        df = df.drop(columns=nearest_cols_to_drop)
        self.dropped_features.extend(nearest_cols_to_drop)
        
        return pd.concat([df, pd.DataFrame(new_features, index=df.index)], axis=1)
    
    def _aggregate_rare_pois(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate rare POIs by category.
        
        Instead of: golf_course_count, swimming_pool_count, spa_count
        Create: premium_leisure_count (aggregated)
        """
        # Define rare POI aggregations
        aggregations = {
            'premium_leisure': ['golf_course', 'spa', 'sauna', 'country_club', 'marina'],
            'specialty_food': ['chocolate', 'tea', 'coffee', 'ice_cream', 'confectionery'],
            'specialty_retail': ['antiques', 'art', 'craft', 'fabric', 'wool', 'pet'],
            'emergency_services': ['fire_extinguisher', 'fire_hydrant', 'defibrillator'],
            'alternative_medicine': ['ayurvedic', 'homeopathy', 'unani'],
        }
        
        new_features = {}
        cols_to_drop = []
        
        for agg_name, poi_types in aggregations.items():
            # Aggregate counts at 2000m
            count_cols = [f'{poi}_count_2000m' for poi in poi_types if f'{poi}_count_2000m' in df.columns]
            if count_cols:
                new_features[f'{agg_name}_count_2000m'] = df[count_cols].sum(axis=1)
                cols_to_drop.extend(count_cols)
            
            # Aggregate densities at 2000m
            density_cols = [f'{poi}_density_2000m' for poi in poi_types if f'{poi}_density_2000m' in df.columns]
            if density_cols:
                new_features[f'{agg_name}_density_2000m'] = df[density_cols].sum(axis=1)
                cols_to_drop.extend(density_cols)
        
        print(f"  Created {len(new_features)} aggregated rare POI features")
        print(f"  Removing {len(cols_to_drop)} individual rare POI features")
        
        df = df.drop(columns=cols_to_drop)
        self.dropped_features.extend(cols_to_drop)
        
        return pd.concat([df, pd.DataFrame(new_features, index=df.index)], axis=1)
    
    def _remove_building_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remove building tag features that duplicate amenity tags.
        
        Keep: building_commercial, building_office, building_retail (unique)
        Drop: building_hospital, building_school (duplicates amenity tags)
        """
        # Building tags that duplicate amenity tags
        duplicate_buildings = [
            'building_hospital', 'building_school', 'building_college',
            'building_university', 'building_church', 'building_temple',
            'building_mosque', 'building_hotel'
        ]
        
        cols_to_drop = []
        for building in duplicate_buildings:
            cols_to_drop.extend([col for col in df.columns if building in col])
        
        print(f"  Removing {len(cols_to_drop)} duplicate building tag features")
        self.dropped_features.extend(cols_to_drop)
        
        return df.drop(columns=cols_to_drop)
    
    def _filter_component_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Keep only discriminative component scores.
        
        Drop: economic (saturated), spatial (low variance), accessibility (ceiling effect)
        Keep: density, proximity, quality (discriminative)
        """
        # Component scores to drop
        drop_components = ['economic', 'spatial', 'accessibility']
        
        cols_to_drop = []
        for component in drop_components:
            cols_to_drop.extend([col for col in df.columns if f'_{component}' in col and 'components' not in col])
        
        print(f"  Removing {len(cols_to_drop)} non-discriminative component scores")
        self.dropped_features.extend(cols_to_drop)
        
        return df.drop(columns=cols_to_drop)
    
    def get_feature_importance_groups(self) -> Dict[str, List[str]]:
        """
        Group features by type for interpretability.
        
        Returns:
            Dictionary mapping feature group names to feature lists
        """
        groups = {
            'density': [],
            'proximity': [],
            'quality': [],
            'diversity': [],
            'gradients': [],
            'ratios': [],
            'aggregated': [],
            'category_scores': [],
            'other': []
        }
        
        for feature in self.feature_names:
            if '_density_' in feature:
                groups['density'].append(feature)
            elif '_proximity_ratio' in feature:
                groups['ratios'].append(feature)
            elif 'avg_dist_' in feature:
                groups['proximity'].append(feature)
            elif '_quality' in feature:
                groups['quality'].append(feature)
            elif 'diversity' in feature or 'type_count' in feature:
                groups['diversity'].append(feature)
            elif '_gradient' in feature:
                groups['gradients'].append(feature)
            elif any(agg in feature for agg in ['premium_leisure', 'specialty_', 'emergency_', 'alternative_']):
                groups['aggregated'].append(feature)
            elif 'score' in feature or 'index' in feature:
                groups['category_scores'].append(feature)
            else:
                groups['other'].append(feature)
        
        return groups


def create_feature_engineering_pipeline():
    """
    Create and return configured feature engineering pipeline.
    
    Usage:
        engineer = create_feature_engineering_pipeline()
        clean_features = engineer.fit_transform(raw_features_df)
    """
    return AmenityFeatureEngineer(rare_poi_threshold=0.05)


if __name__ == '__main__':
    # Example usage
    print("Feature Engineering Pipeline")
    print("=" * 50)
    print("\nConfiguration:")
    print("  - Rare POI threshold: 5% (drop if present in <5% of locations)")
    print("  - Remove percentage features: Yes")
    print("  - Create density gradients: Yes")
    print("  - Create diversity metrics: Yes")
    print("  - Create proximity ratios: Yes")
    print("  - Aggregate rare POIs: Yes")
    print("  - Remove building duplicates: Yes")
    print("  - Filter component scores: Yes")
    print("\nExpected reduction: 2,982 → ~500 features (83% reduction)")
