"""
Main Pipeline with Google Maps Integration
===========================================

Unified pipeline supporting both OSM and Google Maps data sources.
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List
import pandas as pd
from tqdm import tqdm

import config
from poi_fetcher import POIFetcher
from google_poi_fetcher import GooglePOIFetcher
from feature_extractor import FeatureExtractor
from google_enhanced_features import GoogleEnhancedFeatures
from advanced_features import AdvancedFeatureExtractor
from category_scorer import CategoryScorer
from amenity_calculator import AmenityCalculator
from utils import setup_logging

logger = logging.getLogger(__name__)


class AmenityPipeline:
    """Main pipeline with Google Maps support."""
    
    def __init__(self, mode: str = None, google_api_key: str = None):
        """
        Initialize pipeline.
        
        Args:
            mode: Data source mode ('osm', 'google', 'hybrid')
            google_api_key: Google Maps API key (required for 'google' or 'hybrid')
        """
        # Determine mode
        self.mode = mode or config.DATA_SOURCE_MODE
        
        # Get API key
        self.google_api_key = google_api_key or config.GOOGLE_MAPS_API_KEY or os.getenv('GOOGLE_MAPS_API_KEY')
        
        # Validate configuration
        if self.mode in ['google', 'hybrid'] and not self.google_api_key:
            raise ValueError(
                "Google Maps API key required for mode='google' or 'hybrid'. "
                "Set GOOGLE_MAPS_API_KEY in config.py or environment variable."
            )
        
        # Initialize fetchers
        self.osm_fetcher = POIFetcher(logger=logger)
        
        if self.mode in ['google', 'hybrid']:
            self.google_fetcher = GooglePOIFetcher(self.google_api_key, logger=logger)
        else:
            self.google_fetcher = None
        
        # Initialize feature extractors
        self.feature_extractor = FeatureExtractor()
        self.advanced_extractor = AdvancedFeatureExtractor()
        self.google_extractor = GoogleEnhancedFeatures() if self.mode in ['google', 'hybrid'] else None
        
        # Initialize scorers
        self.category_scorer = CategoryScorer()
        self.amenity_calculator = AmenityCalculator()
        
        logger.info(f"Pipeline initialized in mode: {self.mode}")
    
    def fetch_pois(self, lat: float, lon: float, force_refresh: bool = False) -> List[Dict]:
        """
        Fetch POIs based on configured mode.
        
        Args:
            lat: Latitude
            lon: Longitude
            force_refresh: Force refresh cache
        
        Returns:
            List of POI dictionaries
        """
        if self.mode == 'osm':
            return self._fetch_osm(lat, lon, force_refresh)
        elif self.mode == 'google':
            return self._fetch_google(lat, lon, force_refresh)
        elif self.mode == 'hybrid':
            return self._fetch_hybrid(lat, lon, force_refresh)
        else:
            raise ValueError(f"Invalid mode: {self.mode}")
    
    def _fetch_osm(self, lat: float, lon: float, force_refresh: bool) -> List[Dict]:
        """Fetch from OSM."""
        logger.info(f"Fetching from OSM: ({lat}, {lon})")
        return self.osm_fetcher.fetch(lat, lon, max(config.RADII) / 1000, force_refresh)
    
    def _fetch_google(self, lat: float, lon: float, force_refresh: bool) -> List[Dict]:
        """Fetch from Google Maps."""
        logger.info(f"Fetching from Google Maps: ({lat}, {lon})")
        return self.google_fetcher.fetch(
            lat, lon,
            max(config.RADII) / 1000,
            force_refresh,
            include_distances=config.GOOGLE_INCLUDE_DISTANCES
        )
    
    def _fetch_hybrid(self, lat: float, lon: float, force_refresh: bool) -> List[Dict]:
        """Fetch from Google with OSM fallback."""
        try:
            logger.info(f"Trying Google Maps first: ({lat}, {lon})")
            pois = self.google_fetcher.fetch(
                lat, lon,
                max(config.RADII) / 1000,
                force_refresh,
                include_distances=config.GOOGLE_INCLUDE_DISTANCES
            )
            
            if pois:
                logger.info(f"Google Maps success: {len(pois)} POIs")
                return pois
            else:
                logger.warning("Google Maps returned 0 POIs, falling back to OSM")
                return self._fetch_osm(lat, lon, force_refresh)
        
        except Exception as e:
            logger.error(f"Google Maps failed: {e}, falling back to OSM")
            return self._fetch_osm(lat, lon, force_refresh)
    
    def process_location(self, lat: float, lon: float, force_refresh: bool = False) -> Dict:
        """
        Process a single location with enhanced Google features.
        
        Args:
            lat: Latitude
            lon: Longitude
            force_refresh: Force refresh cache
        
        Returns:
            Complete results dictionary
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing: ({lat}, {lon})")
        logger.info(f"{'='*60}")
        
        # 1. Fetch POIs
        pois = self.fetch_pois(lat, lon, force_refresh)
        
        if not pois:
            logger.warning("No POIs found, returning zero scores")
            return self._empty_result(lat, lon)
        
        logger.info(f"Total POIs: {len(pois)}")
        
        # 2. Extract base features
        features = self.feature_extractor.extract_all_features(lat, lon, pois)
        
        # 3. Extract advanced features
        advanced_features = self.advanced_extractor.extract_all_advanced_features(lat, lon, pois)
        features.update(advanced_features)
        
        # 4. Extract Google-enhanced features (if using Google data)
        if self.mode in ['google', 'hybrid'] and self.google_extractor:
            google_features = self.google_extractor.extract_all_google_features(pois)
            features.update(google_features)
            logger.info(f"Google features extracted: {len(google_features)}")
        
        # 5. Calculate category scores
        category_scores = {}
        for category in config.CATEGORIES:
            try:
                score_data = self.category_scorer.calculate_category_score(category, features, pois)
                category_scores[category] = score_data
            except Exception as e:
                logger.error(f"Error scoring category {category}: {e}")
                category_scores[category] = {'score': 0, 'components': {}}
        
        # 6. Calculate final amenity index
        result_dict = self.amenity_calculator.calculate_amenity_index(
            category_scores, len(pois), features
        )
        amenity_index = result_dict['amenity_index']
        classification = result_dict['classification']
        data_quality = result_dict['data_quality']
        
        # 7. Build result
        result = {
            'latitude': lat,
            'longitude': lon,
            'data_source': self.mode,
            'total_pois': len(pois),
            'amenity_index': amenity_index,
            'classification': classification,
            'data_quality': data_quality,
            'category_scores': category_scores,
            'features': features
        }
        
        # Add Google-specific summary if available
        if self.mode in ['google', 'hybrid'] and 'google_avg_rating' in features:
            result['google_summary'] = {
                'avg_rating': features.get('google_avg_rating', 0),
                'total_reviews': features.get('google_total_reviews', 0),
                'avg_price_level': features.get('google_avg_price_level', 0),
                'pct_premium': features.get('google_pct_premium', 0),
                'walkability_score': features.get('google_walkability_score', 0),
                'live_availability_score': features.get('google_live_availability_score', 0)
            }
        
        logger.info(f"Amenity Index: {amenity_index} ({classification})")
        logger.info(f"Data Quality: {data_quality}")
        
        return result
    
    def _empty_result(self, lat: float, lon: float) -> Dict:
        """Return empty result for locations with no POIs."""
        return {
            'latitude': lat,
            'longitude': lon,
            'data_source': self.mode,
            'total_pois': 0,
            'amenity_index': 0.0,
            'classification': 'Rural',
            'data_quality': 'Zero',
            'category_scores': {},
            'features': {}
        }
    
    def process_batch(self, locations: List[Dict], output_file: str = None) -> pd.DataFrame:
        """
        Process multiple locations.
        
        Args:
            locations: List of {'lat': ..., 'lon': ...} dicts
            output_file: Optional output CSV path
        
        Returns:
            DataFrame with results
        """
        results = []
        
        for loc in tqdm(locations, desc="Processing locations"):
            try:
                result = self.process_location(loc['lat'], loc['lon'])
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing ({loc['lat']}, {loc['lon']}): {e}")
                results.append(self._empty_result(loc['lat'], loc['lon']))
        
        # Convert to DataFrame
        df = self._results_to_dataframe(results)
        
        # Save if requested
        if output_file:
            df.to_csv(output_file, index=False)
            logger.info(f"Results saved to: {output_file}")
        
        return df
    
    def _results_to_dataframe(self, results: List[Dict]) -> pd.DataFrame:
        """Convert results to DataFrame."""
        rows = []
        
        for r in results:
            row = {
                'latitude': r['latitude'],
                'longitude': r['longitude'],
                'data_source': r['data_source'],
                'total_pois': r['total_pois'],
                'amenity_index': r['amenity_index'],
                'classification': r['classification'],
                'data_quality': r['data_quality']
            }
            
            # Add category scores
            for cat, scores in r.get('category_scores', {}).items():
                row[f'{cat}_score'] = scores.get('score', 0)
            
            # Add Google summary if available
            if 'google_summary' in r:
                for k, v in r['google_summary'].items():
                    row[f'google_{k}'] = v
            
            rows.append(row)
        
        return pd.DataFrame(rows)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Amenity Scoring Pipeline with Google Maps')
    parser.add_argument('--lat', type=float, help='Latitude')
    parser.add_argument('--lon', type=float, help='Longitude')
    parser.add_argument('--input', type=str, help='Input CSV with lat,lon columns')
    parser.add_argument('--output', type=str, help='Output file path')
    parser.add_argument('--mode', type=str, choices=['osm', 'google', 'hybrid'],
                       help='Data source mode (default: from config)')
    parser.add_argument('--google-api-key', type=str, help='Google Maps API key')
    parser.add_argument('--force-refresh', action='store_true', help='Force refresh cache')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    
    # Initialize pipeline
    pipeline = AmenityPipeline(mode=args.mode, google_api_key=args.google_api_key)
    
    # Process
    if args.lat and args.lon:
        # Single location
        result = pipeline.process_location(args.lat, args.lon, args.force_refresh)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"RESULTS FOR ({args.lat}, {args.lon})")
        print(f"{'='*60}")
        print(f"Data Source: {result['data_source']}")
        print(f"Total POIs: {result['total_pois']}")
        print(f"Amenity Index: {result['amenity_index']}")
        print(f"Classification: {result['classification']}")
        print(f"Data Quality: {result['data_quality']}")
        
        if 'google_summary' in result:
            print(f"\nGoogle Maps Summary:")
            print(f"  Average Rating: {result['google_summary']['avg_rating']:.1f} ★")
            print(f"  Total Reviews: {result['google_summary']['total_reviews']:,}")
            print(f"  Price Level: {result['google_summary']['avg_price_level']:.1f}/4")
            print(f"  Premium POIs: {result['google_summary']['pct_premium']:.1f}%")
            print(f"  Walkability: {result['google_summary']['walkability_score']:.1f}/100")
        
        print(f"\nCategory Scores:")
        for cat, scores in result['category_scores'].items():
            print(f"  {cat}: {scores['score']:.1f}")
        
        # Save if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"\nFull results saved to: {args.output}")
    
    elif args.input:
        # Batch processing
        df_input = pd.read_csv(args.input)
        
        if 'lat' not in df_input.columns or 'lon' not in df_input.columns:
            print("Error: Input CSV must have 'lat' and 'lon' columns")
            sys.exit(1)
        
        locations = df_input[['lat', 'lon']].to_dict('records')
        
        output_file = args.output or 'amenity_results.csv'
        df_results = pipeline.process_batch(locations, output_file)
        
        print(f"\n{'='*60}")
        print(f"BATCH PROCESSING COMPLETE")
        print(f"{'='*60}")
        print(f"Locations processed: {len(df_results)}")
        print(f"Results saved to: {output_file}")
        
        # Print summary statistics
        print(f"\nClassification Distribution:")
        print(df_results['classification'].value_counts())
        
        print(f"\nAmenity Index Statistics:")
        print(df_results['amenity_index'].describe())
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
