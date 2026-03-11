"""
Amenity Index Calculator
=========================

Calculates final amenity index (0-100) and 5-tier classification.
"""

from typing import Dict

import amenity_v1.config


class AmenityCalculator:
    """Calculate final amenity index and classification."""
    
    def __init__(self):
        self.category_weights = config.CATEGORY_WEIGHTS
    
    def calculate_amenity_index(self, category_scores: Dict, total_pois: int = 0, features: Dict = None) -> Dict:
        """
        Calculate final amenity index (0-100) with anti-sprawl and quality penalties.
        
        Args:
            category_scores: Dictionary of category scores
            total_pois: Total number of POIs fetched (for quality assessment)
            features: Optional features dict for diversity metrics
        
        Returns:
            Dictionary with amenity_index, classification, category_scores, and data_quality
        """
        # Handle total_pois if it's passed as a dict
        if isinstance(total_pois, dict):
            total_pois = total_pois.get('total_pois', 0)
        total_pois = int(total_pois) if total_pois else 0
        
        # Weighted combination
        amenity_index = sum(
            self.category_weights.get(cat, 0) * category_scores.get(cat, {}).get('score', 0)
            for cat in self.category_weights.keys()
        )
        
        # Cap amenity index at 100
        amenity_index = min(100, amenity_index)
        
        # ===== PENALTY SYSTEM: ADDITIVE (FIXED) =====
        # All penalties are now additive to prevent exponential stacking
        # Maximum total penalty capped at 50%
        total_penalty = 0.0
        
        # ===== PENALTY 1: Data Quality (POI Count) =====
        # Thresholds and penalties come from config to stay in sync.
        thresholds = config.DATA_QUALITY_POI_THRESHOLDS
        penalties = config.DATA_QUALITY_PENALTIES
        if total_pois < thresholds['very_sparse']:
            total_penalty += penalties['very_sparse']   # 20% for < 5 POIs
        elif total_pois < thresholds['sparse']:
            total_penalty += penalties['sparse']        # 10% for < 20 POIs
        elif total_pois < thresholds['moderate']:
            total_penalty += penalties['moderate']      # 5% for < 40 POIs
        # else: no penalty for good coverage (40+ POIs)
        
        # ===== PENALTY 2: Gini Coefficient (Spatial Inequality) =====
        # High inequality in POI distribution = sprawl indicator
        if features:
            gini = features.get('global_gini_coefficient', 0)
            # Max 15% penalty for extreme inequality (was 30% multiplicative)
            total_penalty += gini * 0.15
        
        # ===== PENALTY 3: Simpson's Diversity (Mono-use Areas) =====
        # Low diversity = mono-use area penalty
        if features:
            simpson = features.get('global_simpson_diversity', 0) / 100  # Normalize to [0,1]
            # Penalty for lack of diversity (inverted)
            # Max 10% penalty for zero diversity (was 20% multiplicative)
            total_penalty += (1 - simpson) * 0.10
        
        # ===== PENALTY 4: Category Minimum Presence =====
        # Essential categories must be present for urban quality
        required_categories = ['essential', 'healthcare', 'transport']
        present_categories = [
            cat for cat in required_categories 
            if category_scores.get(cat, {}).get('score', 0) > 10
        ]
        missing_count = len(required_categories) - len(present_categories)
        if missing_count > 0:
            # 3% penalty per missing essential category (was 5% multiplicative)
            # Max penalty: 9% for all 3 missing (was 15% multiplicative)
            total_penalty += min(0.09, 0.03 * missing_count)
        
        # ===== APPLY TOTAL PENALTY (CAPPED AT 50%) =====
        total_penalty = min(total_penalty, 0.50)  # Hard cap at 50% max penalty
        amenity_index *= (1 - total_penalty)
        
        # Final bounds check
        amenity_index = max(0, min(100, amenity_index))
        
        # Round BEFORE classification to ensure consistency
        amenity_index = round(amenity_index, 1)
        
        # 3-tier classification: Metro / Urban / Rural
        if amenity_index >= 60:
            classification = "Metro"
        elif amenity_index >= 30:
            classification = "Urban"
        else:
            classification = "Rural"
        
        # Data quality assessment based on POI count
        if total_pois == 0:
            data_quality = 'Zero'
        elif total_pois < 10:
            data_quality = 'Low'
        elif total_pois < 50:
            data_quality = 'Medium'
        else:
            data_quality = 'High'
        
        return {
            'amenity_index': round(amenity_index, 1),
            'classification': classification,
            'category_scores': {k: v['score'] for k, v in category_scores.items()},
            'data_quality': data_quality
        }
