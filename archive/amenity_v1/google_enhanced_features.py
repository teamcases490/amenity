"""
Google Maps Enhanced Features
==============================

Additional feature extraction leveraging Google Maps data:
- Rating-based quality metrics
- Price level economic indicators
- Live temporal accessibility
- Actual road distance analysis
- Business verification status
"""

import numpy as np
from typing import Dict, List
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class GoogleEnhancedFeatures:
    """Extract enhanced features from Google Maps POI data."""
    
    def __init__(self):
        pass
    
    def extract_rating_features(self, pois: List[Dict]) -> Dict:
        """
        Extract rating-based quality features.
        
        Args:
            pois: List of POI dictionaries with Google Maps data
        
        Returns:
            Dict of rating features
        """
        if not pois:
            return {
                'avg_rating': 0.0,
                'median_rating': 0.0,
                'rating_std': 0.0,
                'pct_highly_rated': 0.0,  # >= 4.0 stars
                'pct_premium_rated': 0.0,  # >= 4.5 stars
                'total_reviews': 0,
                'avg_reviews_per_poi': 0.0,
                'pct_with_ratings': 0.0,
                'rating_weighted_score': 0.0
            }
        
        try:
            # Extract ratings
            ratings = [p.get('rating') for p in pois if p.get('rating') is not None]
            review_counts = [p.get('user_ratings_total', 0) for p in pois]
            
            if not ratings:
                return {
                    'avg_rating': 0.0,
                    'median_rating': 0.0,
                    'rating_std': 0.0,
                    'pct_highly_rated': 0.0,
                    'pct_premium_rated': 0.0,
                    'total_reviews': sum(review_counts),
                    'avg_reviews_per_poi': np.mean(review_counts) if review_counts else 0.0,
                    'pct_with_ratings': 0.0,
                    'rating_weighted_score': 0.0
                }
            
            # Calculate statistics
            avg_rating = np.mean(ratings)
            median_rating = np.median(ratings)
            rating_std = np.std(ratings)
            
            # Quality thresholds
            highly_rated = sum(1 for r in ratings if r >= 4.0)
            premium_rated = sum(1 for r in ratings if r >= 4.5)
            
            pct_highly_rated = (highly_rated / len(ratings)) * 100
            pct_premium_rated = (premium_rated / len(ratings)) * 100
            
            # Review statistics
            total_reviews = sum(review_counts)
            avg_reviews = np.mean(review_counts) if review_counts else 0.0
            
            # Coverage
            pct_with_ratings = (len(ratings) / len(pois)) * 100
            
            # Weighted score (rating weighted by review count)
            if total_reviews > 0:
                weighted_ratings = [
                    p.get('rating', 0) * p.get('user_ratings_total', 0)
                    for p in pois if p.get('rating') is not None
                ]
                rating_weighted_score = sum(weighted_ratings) / total_reviews
            else:
                rating_weighted_score = 0.0
            
            return {
                'avg_rating': round(avg_rating, 2),
                'median_rating': round(median_rating, 2),
                'rating_std': round(rating_std, 2),
                'pct_highly_rated': round(pct_highly_rated, 1),
                'pct_premium_rated': round(pct_premium_rated, 1),
                'total_reviews': total_reviews,
                'avg_reviews_per_poi': round(avg_reviews, 1),
                'pct_with_ratings': round(pct_with_ratings, 1),
                'rating_weighted_score': round(rating_weighted_score, 2)
            }
        
        except Exception as e:
            logger.error(f"Error extracting rating features: {e}")
            return {
                'avg_rating': 0.0,
                'median_rating': 0.0,
                'rating_std': 0.0,
                'pct_highly_rated': 0.0,
                'pct_premium_rated': 0.0,
                'total_reviews': 0,
                'avg_reviews_per_poi': 0.0,
                'pct_with_ratings': 0.0,
                'rating_weighted_score': 0.0
            }
    
    def extract_price_level_features(self, pois: List[Dict]) -> Dict:
        """
        Extract price level economic indicators.
        
        Args:
            pois: List of POI dictionaries
        
        Returns:
            Dict of price level features
        """
        if not pois:
            return {
                'avg_price_level': 0.0,
                'median_price_level': 0.0,
                'pct_free': 0.0,
                'pct_inexpensive': 0.0,
                'pct_moderate': 0.0,
                'pct_expensive': 0.0,
                'pct_very_expensive': 0.0,
                'pct_with_price_info': 0.0,
                'economic_vibrancy_score': 0.0
            }
        
        try:
            # Extract price levels
            price_levels = [p.get('price_level', 0) for p in pois if p.get('price_level', 0) > 0]
            
            if not price_levels:
                return {
                    'avg_price_level': 0.0,
                    'median_price_level': 0.0,
                    'pct_free': 0.0,
                    'pct_inexpensive': 0.0,
                    'pct_moderate': 0.0,
                    'pct_expensive': 0.0,
                    'pct_very_expensive': 0.0,
                    'pct_with_price_info': 0.0,
                    'economic_vibrancy_score': 0.0
                }
            
            # Statistics
            avg_price = np.mean(price_levels)
            median_price = np.median(price_levels)
            
            # Distribution
            all_prices = [p.get('price_level', 0) for p in pois]
            pct_free = (sum(1 for p in all_prices if p == 0) / len(pois)) * 100
            pct_inexpensive = (sum(1 for p in all_prices if p == 1) / len(pois)) * 100
            pct_moderate = (sum(1 for p in all_prices if p == 2) / len(pois)) * 100
            pct_expensive = (sum(1 for p in all_prices if p == 3) / len(pois)) * 100
            pct_very_expensive = (sum(1 for p in all_prices if p == 4) / len(pois)) * 100
            
            # Coverage
            pct_with_price = (len(price_levels) / len(pois)) * 100
            
            # Economic vibrancy score (0-100)
            # Higher price levels indicate more upscale area
            vibrancy_score = 50 + (avg_price / 4.0) * 50
            
            return {
                'avg_price_level': round(avg_price, 2),
                'median_price_level': round(median_price, 1),
                'pct_free': round(pct_free, 1),
                'pct_inexpensive': round(pct_inexpensive, 1),
                'pct_moderate': round(pct_moderate, 1),
                'pct_expensive': round(pct_expensive, 1),
                'pct_very_expensive': round(pct_very_expensive, 1),
                'pct_with_price_info': round(pct_with_price, 1),
                'economic_vibrancy_score': round(vibrancy_score, 1)
            }
        
        except Exception as e:
            logger.error(f"Error extracting price level features: {e}")
            return {
                'avg_price_level': 0.0,
                'median_price_level': 0.0,
                'pct_free': 0.0,
                'pct_inexpensive': 0.0,
                'pct_moderate': 0.0,
                'pct_expensive': 0.0,
                'pct_very_expensive': 0.0,
                'pct_with_price_info': 0.0,
                'economic_vibrancy_score': 0.0
            }
    
    def extract_temporal_features_enhanced(self, pois: List[Dict]) -> Dict:
        """
        Extract enhanced temporal accessibility features.
        
        Args:
            pois: List of POI dictionaries
        
        Returns:
            Dict of temporal features
        """
        if not pois:
            return {
                'pct_currently_open': 0.0,
                'pct_operational': 0.0,
                'pct_verified': 0.0,
                'live_availability_score': 0.0
            }
        
        try:
            # Current status
            currently_open = sum(1 for p in pois if p.get('open_now', False))
            pct_open = (currently_open / len(pois)) * 100
            
            # Business status
            operational = sum(1 for p in pois if p.get('is_operational', True))
            pct_operational = (operational / len(pois)) * 100
            
            # Verification (operational + has reviews)
            verified = sum(1 for p in pois if p.get('is_verified', False))
            pct_verified = (verified / len(pois)) * 100
            
            # Live availability score (0-100)
            # Combines current open status with operational status
            availability_score = (pct_open * 0.7) + (pct_operational * 0.3)
            
            return {
                'pct_currently_open': round(pct_open, 1),
                'pct_operational': round(pct_operational, 1),
                'pct_verified': round(pct_verified, 1),
                'live_availability_score': round(availability_score, 1)
            }
        
        except Exception as e:
            logger.error(f"Error extracting temporal features: {e}")
            return {
                'pct_currently_open': 0.0,
                'pct_operational': 0.0,
                'pct_verified': 0.0,
                'live_availability_score': 0.0
            }
    
    def extract_distance_accuracy_features(self, pois: List[Dict]) -> Dict:
        """
        Extract features comparing Haversine vs actual road distances.
        
        Args:
            pois: List of POI dictionaries with actual_distance_km
        
        Returns:
            Dict of distance accuracy features
        """
        if not pois:
            return {
                'avg_distance_accuracy': 1.0,
                'median_walk_time_min': 0.0,
                'nearest_walk_time_min': 0.0,
                'pct_within_5min_walk': 0.0,
                'pct_within_15min_walk': 0.0,
                'walkability_score': 0.0
            }
        
        try:
            # Distance accuracy (Haversine / Actual)
            accuracies = [p.get('distance_accuracy', 1.0) for p in pois if 'distance_accuracy' in p]
            avg_accuracy = np.mean(accuracies) if accuracies else 1.0
            
            # Walking times
            walk_times = [p.get('walk_time_min', 0) for p in pois if 'walk_time_min' in p]
            
            if not walk_times:
                return {
                    'avg_distance_accuracy': round(avg_accuracy, 2),
                    'median_walk_time_min': 0.0,
                    'nearest_walk_time_min': 0.0,
                    'pct_within_5min_walk': 0.0,
                    'pct_within_15min_walk': 0.0,
                    'walkability_score': 0.0
                }
            
            median_walk = np.median(walk_times)
            nearest_walk = min(walk_times)
            
            # Accessibility thresholds
            within_5min = sum(1 for t in walk_times if t <= 5)
            within_15min = sum(1 for t in walk_times if t <= 15)
            
            pct_5min = (within_5min / len(walk_times)) * 100
            pct_15min = (within_15min / len(walk_times)) * 100
            
            # Walkability score (0-100)
            # Higher score = more POIs within walking distance
            walkability = (pct_5min * 0.6) + (pct_15min * 0.4)
            
            return {
                'avg_distance_accuracy': round(avg_accuracy, 2),
                'median_walk_time_min': round(median_walk, 1),
                'nearest_walk_time_min': round(nearest_walk, 1),
                'pct_within_5min_walk': round(pct_5min, 1),
                'pct_within_15min_walk': round(pct_15min, 1),
                'walkability_score': round(walkability, 1)
            }
        
        except Exception as e:
            logger.error(f"Error extracting distance accuracy features: {e}")
            return {
                'avg_distance_accuracy': 1.0,
                'median_walk_time_min': 0.0,
                'nearest_walk_time_min': 0.0,
                'pct_within_5min_walk': 0.0,
                'pct_within_15min_walk': 0.0,
                'walkability_score': 0.0
            }
    
    def extract_quality_indicators(self, pois: List[Dict]) -> Dict:
        """
        Extract quality indicator features.
        
        Args:
            pois: List of POI dictionaries
        
        Returns:
            Dict of quality features
        """
        if not pois:
            return {
                'pct_premium': 0.0,
                'pct_popular': 0.0,
                'avg_quality_score': 0.0,
                'quality_weighted_density': 0.0
            }
        
        try:
            # Premium POIs (high rating or expensive)
            premium = sum(1 for p in pois if p.get('is_premium', False))
            pct_premium = (premium / len(pois)) * 100
            
            # Popular POIs (many reviews)
            popular = sum(1 for p in pois if p.get('is_popular', False))
            pct_popular = (popular / len(pois)) * 100
            
            # Average quality score
            quality_scores = [p.get('quality_score', 0) for p in pois]
            avg_quality = np.mean(quality_scores) if quality_scores else 0.0
            
            # Quality-weighted density
            # Sum of quality scores (higher quality POIs count more)
            quality_weighted = sum(quality_scores)
            
            return {
                'pct_premium': round(pct_premium, 1),
                'pct_popular': round(pct_popular, 1),
                'avg_quality_score': round(avg_quality, 1),
                'quality_weighted_density': round(quality_weighted, 1)
            }
        
        except Exception as e:
            logger.error(f"Error extracting quality indicators: {e}")
            return {
                'pct_premium': 0.0,
                'pct_popular': 0.0,
                'avg_quality_score': 0.0,
                'quality_weighted_density': 0.0
            }
    
    def extract_all_google_features(self, pois: List[Dict]) -> Dict:
        """
        Extract all Google Maps enhanced features.
        
        Args:
            pois: List of POI dictionaries with Google Maps data
        
        Returns:
            Dict of all enhanced features
        """
        features = {}
        
        # Rating features
        rating_features = self.extract_rating_features(pois)
        features.update({f'google_{k}': v for k, v in rating_features.items()})
        
        # Price level features
        price_features = self.extract_price_level_features(pois)
        features.update({f'google_{k}': v for k, v in price_features.items()})
        
        # Temporal features
        temporal_features = self.extract_temporal_features_enhanced(pois)
        features.update({f'google_{k}': v for k, v in temporal_features.items()})
        
        # Distance accuracy features
        distance_features = self.extract_distance_accuracy_features(pois)
        features.update({f'google_{k}': v for k, v in distance_features.items()})
        
        # Quality indicators
        quality_features = self.extract_quality_indicators(pois)
        features.update({f'google_{k}': v for k, v in quality_features.items()})
        
        return features
    
    def extract_category_google_features(self, pois: List[Dict], category_types: List[str]) -> Dict:
        """
        Extract Google features for a specific category.
        
        Args:
            pois: List of all POI dictionaries
            category_types: List of POI types in this category
        
        Returns:
            Dict of category-specific Google features
        """
        # Filter to category
        category_pois = [p for p in pois if p.get('poi_type') in category_types]
        
        if not category_pois:
            return {
                'category_avg_rating': 0.0,
                'category_total_reviews': 0,
                'category_avg_price': 0.0,
                'category_pct_premium': 0.0,
                'category_quality_score': 0.0
            }
        
        # Extract features for this category
        rating_features = self.extract_rating_features(category_pois)
        price_features = self.extract_price_level_features(category_pois)
        quality_features = self.extract_quality_indicators(category_pois)
        
        return {
            'category_avg_rating': rating_features['avg_rating'],
            'category_total_reviews': rating_features['total_reviews'],
            'category_avg_price': price_features['avg_price_level'],
            'category_pct_premium': quality_features['pct_premium'],
            'category_quality_score': quality_features['avg_quality_score']
        }
