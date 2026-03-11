"""
Main CLI Interface
==================

Command-line interface for the dynamic amenity feature extraction system.
"""

import sys
import json
import time
import argparse
import pandas as pd
from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed  # Fix #6: Better for I/O-bound tasks
from multiprocessing import cpu_count

from utils import setup_logging
from poi_fetcher import POIFetcher
from feature_extractor import FeatureExtractor
from category_scorer import CategoryScorer
from amenity_calculator import AmenityCalculator
import config


class AmenityPipeline:
    """Complete pipeline orchestrator."""
    
    def __init__(self):
        self.logger = setup_logging()
        self.poi_fetcher = POIFetcher(self.logger)
        self.feature_extractor = FeatureExtractor()
        self.category_scorer = CategoryScorer()
        self.amenity_calculator = AmenityCalculator()
        
        self.logger.info("=" * 80)
        self.logger.info("Dynamic Amenity Feature Extraction System v2.0")
        self.logger.info("=" * 80)
    
    def process_location(self, lat: float, lon: float) -> dict:
        """
        Process single location with comprehensive error handling.
        
        Args:
            lat: Latitude
            lon: Longitude
        
        Returns:
            Complete result dictionary or error dict
        """
        start_time = time.time()
        
        try:
            # Validate coordinates
            if not (-90 <= lat <= 90):
                raise ValueError(f"Invalid latitude: {lat} (must be -90 to 90)")
            if not (-180 <= lon <= 180):
                raise ValueError(f"Invalid longitude: {lon} (must be -180 to 180)")
            
            # Step 1: Fetch POIs
            try:
                pois = self.poi_fetcher.fetch(lat, lon, max_radius_km=2.0)
            except Exception as e:
                self.logger.error(f"POI fetch failed for ({lat:.4f}, {lon:.4f}): {e}")
                pois = []
            
            # Data quality warning
            if len(pois) < 10:
                self.logger.warning(f"Only {len(pois)} POIs found at ({lat:.4f}, {lon:.4f}) - data quality may be poor")
            
            # Step 2: Extract features
            try:
                features = self.feature_extractor.extract_all_features(lat, lon, pois)
            except Exception as e:
                self.logger.error(f"Feature extraction failed for ({lat:.4f}, {lon:.4f}): {e}")
                features = {'latitude': lat, 'longitude': lon, 'total_pois': len(pois)}
            
            # Step 3: Score categories
            category_scores = {}
            for category in config.CATEGORY_WEIGHTS.keys():
                try:
                    category_scores[category] = self.category_scorer.calculate_category_score(
                        category, features, pois
                    )
                except Exception as e:
                    self.logger.error(f"Category scoring failed for {category} at ({lat:.4f}, {lon:.4f}): {e}")
                    category_scores[category] = {'score': 0.0, 'components': {}}
            
            # Step 4: Calculate amenity index with anti-sprawl and quality penalties
            try:
                final_result = self.amenity_calculator.calculate_amenity_index(
                    category_scores, 
                    total_pois=len(pois),
                    features=features  # Pass features for Gini/Simpson integration
                )
            except Exception as e:
                self.logger.error(f"Amenity index calculation failed for ({lat:.4f}, {lon:.4f}): {e}")
                final_result = {
                    'amenity_index': 0.0,
                    'classification': 'Rural',
                    'data_quality': 'Error'
                }
            
            return {
                'location': {'latitude': lat, 'longitude': lon},
                'amenity_index': final_result,
                'category_scores': category_scores,
                'features': features,
                'metadata': {
                    'processing_time': time.time() - start_time,
                    'total_pois': len(pois),
                    'num_features': len(features),
                    'status': 'success'
                }
            }
        
        except Exception as e:
            self.logger.error(f"Critical error processing ({lat:.4f}, {lon:.4f}): {e}")
            return {
                'location': {'latitude': lat, 'longitude': lon},
                'amenity_index': {
                    'amenity_index': 0.0,
                    'classification': 'Error',
                    'data_quality': 'Error'
                },
                'category_scores': {},
                'features': {},
                'metadata': {
                    'processing_time': time.time() - start_time,
                    'total_pois': 0,
                    'num_features': 0,
                    'status': 'error',
                    'error': str(e)
                }
            }
    
    def process_batch(self, input_file: str, output_file: str, parallel: bool = True, n_workers: int = None):
        """
        Process batch of locations with optional parallel processing.
        
        Features:
        - Real-time JSON output (one line per location)
        - Comprehensive CSV with all category scores
        - Data quality metrics
        
        Args:
            input_file: Input CSV file path
            output_file: Output CSV file path (also creates .jsonl file)
            parallel: Whether to use parallel processing (default: True)
            n_workers: Number of parallel workers (default: CPU count - 1)
        """
        df = pd.read_csv(input_file)
        
        # Imports now handled globally
        
        # Find lat/lon columns
        lat_col = next((c for c in df.columns if 'lat' in c.lower()), None)
        lon_col = next((c for c in df.columns if 'lon' in c.lower()), None)
        
        if not lat_col or not lon_col:
            raise ValueError("Could not find latitude/longitude columns")
        
        # Prepare output file paths
        json_output = output_file.replace('.csv', '.jsonl')
        
        # RESUME LOGIC
        import os
        processed_locs = set()
        
        if os.path.exists(output_file):
            try:
                # Read existing results to find processed locations
                # Only read lat/lon columns to save memory
                existing_df = pd.read_csv(output_file, usecols=lambda c: c.lower() in ['latitude', 'longitude'])
                
                # Normalize column names
                cols = {c.lower(): c for c in existing_df.columns}
                if 'latitude' in cols and 'longitude' in cols:
                    lat_c, lon_c = cols['latitude'], cols['longitude']
                    for _, row in existing_df.iterrows():
                        processed_locs.add((round(row[lat_c], 6), round(row[lon_c], 6)))
                    
                self.logger.info(f"Resuming: Found {len(processed_locs)} already processed locations in {output_file}")
            except Exception as e:
                self.logger.warning(f"Could not read existing output file for resuming: {e}")
        
        # Define columns
        base_cols = ['latitude', 'longitude', 'amenity_index', 'classification', 
                    'data_quality', 'total_pois', 'num_features', 'processing_time']
        category_cols = [f'{cat}_score' for cat in config.CATEGORY_WEIGHTS.keys()]
        ordered_cols = base_cols + category_cols
        
        # Open/Initialize output files
        if not processed_locs:
            # New run: write header
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                pd.DataFrame(columns=ordered_cols).to_csv(f, index=False)
            mode = 'w'
            self.logger.info(f"Initialized new output files: {output_file}, {json_output}")
        else:
            # Resume: append mode
            mode = 'a'
            self.logger.info(f"Appending to existing output files: {output_file}, {json_output}")

        # Open JSONL file in correct mode
        json_file = open(json_output, mode, encoding='utf-8')

        # Filter locations to process
        all_locations = [(row[lat_col], row[lon_col]) for _, row in df.iterrows()]
        locations_to_process = []
        for lat, lon in all_locations:
            if (round(lat, 6), round(lon, 6)) not in processed_locs:
                locations_to_process.append((lat, lon))
        
        total_locs = len(locations_to_process)
        if total_locs == 0:
            self.logger.info("All locations already processed! Nothing to do.")
            json_file.close()
            return

        self.logger.info(f"Processing {total_locs} remaining locations...")

        # Processing Logic
        if parallel:
             if n_workers is None:
                from multiprocessing import cpu_count
                n_workers = min(10, cpu_count() * 2)
        
        if parallel and n_workers > 1:
            # SAFE PARALLEL PROCESSING
            safe_workers = min(n_workers, 4)  # Cap at 4 workers
            self.logger.info(f"Processing in PARALLEL mode (workers={safe_workers})...")
            
            with ThreadPoolExecutor(max_workers=safe_workers) as executor:
                # Submit tasks
                future_to_loc = {executor.submit(self._process_location_wrapper, loc): loc for loc in locations_to_process}
                
                for future in tqdm(as_completed(future_to_loc), total=total_locs, desc="Processing"):
                    loc = future_to_loc[future]
                    try:
                        result = future.result()
                        if result:
                            # 1. Write JSON Line
                            json_file.write(json.dumps(result) + '\n')
                            json_file.flush()
                            
                            # 2. Append to CSV
                            self._append_to_csv(result, output_file, ordered_cols)
                        else:
                            self.logger.warning(f"Processing returned None for {loc}")
                            
                    except Exception as e:
                        self.logger.error(f"Worker exception for {loc}: {e}")
        
        else:
            # SEQUENTIAL PROCESSING
            self.logger.info("Processing in SEQUENTIAL mode...")
            for lat, lon in tqdm(locations_to_process, desc="Processing"):
                try:
                    result = self.process_location(lat, lon)
                    if result:
                        # 1. Write JSON Line
                        json_file.write(json.dumps(result) + '\n')
                        json_file.flush()
                        
                        # 2. Append to CSV
                        self._append_to_csv(result, output_file, ordered_cols)
                    else:
                        self.logger.warning(f"Processing returned None for ({lat}, {lon})")
                        
                except Exception as e:
                    self.logger.error(f"Processing failed for ({lat}, {lon}): {e}")
        
        json_file.close()
        self.logger.info(f"[SUCCESS] Batch processing complete. Results saved to {output_file}")

    def _append_to_csv(self, result, output_file, ordered_cols):
        """Thread-safe append to CSV."""
        try:
            flat = {
                'latitude': result['location']['latitude'],
                'longitude': result['location']['longitude'],
                'amenity_index': result['amenity_index']['amenity_index'],
                'classification': result['amenity_index']['classification'],
                'total_pois': result['metadata']['total_pois'],
                'num_features': result['metadata']['num_features'],
                'processing_time': result['metadata']['processing_time'],
            }
            
            # Data Quality logic
            pois = result['metadata']['total_pois']
            if pois == 0:
                flat['data_quality'] = 'Zero'
            elif pois < 10:
                flat['data_quality'] = 'Low'
            elif pois < 50:
                flat['data_quality'] = 'Medium'
            else:
                flat['data_quality'] = 'High'
            
            # Category Scores
            for cat in config.CATEGORY_WEIGHTS.keys():
                if cat in result['category_scores']:
                    flat[f'{cat}_score'] = result['category_scores'][cat]['score']
                else:
                    flat[f'{cat}_score'] = 0.0
            
            # Create DataFrame for single row
            df_row = pd.DataFrame([flat])
            
            # Ensure all columns exist
            for col in ordered_cols:
                if col not in df_row.columns:
                    df_row[col] = 0.0
            
            # Reorder
            df_row = df_row[ordered_cols]
            
            # Append to file (header=False)
            df_row.to_csv(output_file, mode='a', header=False, index=False)
            
        except Exception as e:
            self.logger.error(f"Failed to append to CSV: {e}")
            
    def _process_location_wrapper(self, location_tuple):
        """Wrapper for parallel processing (must be picklable)."""
        lat, lon = location_tuple
        try:
            return self.process_location(lat, lon)
        except Exception as e:
            # Fix #3: Better error handling
            self.logger.error(f"Location ({lat:.4f}, {lon:.4f}) failed: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return None


def validate_coordinates(lat: float, lon: float):
    """
    Fix #8: Validate coordinates are within India's bounding box.
    
    Args:
        lat: Latitude
        lon: Longitude
    
    Raises:
        ValueError: If coordinates are outside India
    """
    # India bounding box: 6.5°N to 35.5°N, 68°E to 97.5°E
    if not (6.5 <= lat <= 35.5):
        raise ValueError(f"Latitude {lat} outside India (6.5°N to 35.5°N)")
    if not (68.0 <= lon <= 97.5):
        raise ValueError(f"Longitude {lon} outside India (68°E to 97.5°E)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Dynamic Amenity Feature Extraction System v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single location
  python main.py --lat 19.194 --lon 73.085 --output result.json
  
  # Batch processing
  python main.py --input locations.csv --output features.csv
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--lat', type=float, help='Latitude')
    group.add_argument('--input', help='Input CSV file')
    
    parser.add_argument('--lon', type=float, help='Longitude (required with --lat)')
    parser.add_argument('--output', help='Output file (JSON for single, CSV for batch)')
    parser.add_argument('--parallel', action='store_true', default=True, 
                       help='Use parallel processing for batch (default: True)')
    parser.add_argument('--workers', type=int, default=None,
                       help='Number of parallel workers (default: CPU count - 1)')
    parser.add_argument('--refresh-cache', action='store_true',
                       help='Force refresh cache (ignore existing cached data)')
    
    args = parser.parse_args()
    
    if args.lat and not args.lon:
        parser.error("--lon is required when using --lat")
    
    if args.input and not args.output:
        parser.error("--output is required when using --input")
    
    pipeline = AmenityPipeline()
    
    try:
        if args.lat:
            # Fix #8: Validate coordinates
            validate_coordinates(args.lat, args.lon)
            
            # Single location
            print(f"\n{'='*80}")
            print(f"Processing: ({args.lat}, {args.lon})")
            print(f"{'='*80}\n")
            
            result = pipeline.process_location(args.lat, args.lon)
            
            print(f"[SCORE] Amenity Index: {result['amenity_index']['amenity_index']:.1f}/100")
            print(f"[CLASS] Classification: {result['amenity_index']['classification']}")
            print(f"[POIS]  Total POIs: {result['metadata']['total_pois']}")
            print(f"[FEAT]  Features Extracted: {result['metadata']['num_features']}")
            print(f"[TIME]  Processing Time: {result['metadata']['processing_time']:.2f}s")
            
            print("\n[CATS]  Category Scores:")
            for cat, score_data in result['category_scores'].items():
                print(f"  {cat:12s}: {score_data['score']:5.1f}")
            
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(result, f, indent=2)
                print(f"\n[SAVED] Saved to: {args.output}")
        
        else:
            # Batch processing
            pipeline.process_batch(args.input, args.output, 
                                  parallel=args.parallel, 
                                  n_workers=args.workers)
    
    except KeyboardInterrupt:
        print("\n\n[WARN]  Stopped by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
