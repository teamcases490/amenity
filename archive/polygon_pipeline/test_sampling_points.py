"""
test_sampling_points.py - Experiment script to determine the optimal number of sample points.
Runs the polygon pipeline on a few diverse pincodes with different n_points.
"""

import time
import pandas as pd
import sys
import os
from pathlib import Path

# Setup paths
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "amenity_scorer"))
from polygon_sampler import load_geojson
from poi_polygon_fetcher import PolygonPOIFetcher
from category_scorer import CategoryScorer
from amenity_calculator import AmenityCalculator
from run_polygon_batch import process_pincode

def main():
    geojson_path = "data/All_India_pincode_Boundary-19312.geojson"
    print(f"Loading GeoJSON from {geojson_path}...")
    geojson_index = load_geojson(geojson_path)
    
    # Select a few diverse pincodes
    # Example:
    # 110001 (New Delhi GPO) - Dense Urban Metro
    # 110043 (Najafgarh) - Peri-urban / Edge case
    # 735231 (Jalpaiguri, WB) - Rural / Large
    # 682012 (Ernakulam, KL) - Coastal / Irregular
    # Hyper-complex shapes (largest coordinate sets in GeoJSON)
    test_pincodes = ["799104", "152123"]
    
    test_points = [12, 16]
    
    fetcher = PolygonPOIFetcher()
    scorer = CategoryScorer()
    calculator = AmenityCalculator()
    
    results = []
    
    for pc in test_pincodes:
        if pc not in geojson_index:
            print(f"Pincode {pc} not found in GeoJSON.")
            continue
            
        feat = geojson_index[pc]
        task = {
            "pincode": pc,
            "geometry": feat["geometry"],
            "properties": feat["properties"]
        }
        
        print(f"\n--- Testing Pincode: {pc} ({feat['properties'].get('Office_Name', 'Unknown')}) ---")
        
        # Pre-fetch POIs once to isolate the local math time
        print("Pre-fetching POIs for bbox...")
        start_fetch = time.time()
        # Just running a dummy process to cache it if it's not cached
        _ = process_pincode(task, fetcher, scorer, calculator, 1)
        fetch_time = time.time() - start_fetch
        print(f"Fetch (or cache load) took {fetch_time:.2f}s")
        
        for n in test_points:
            # We time process_pincode, but since POIs are cached, it's mostly local math
            start_math = time.time()
            res = process_pincode(task, fetcher, scorer, calculator, n)
            math_time = time.time() - start_math
            
            score = res["csv_row"]["amenity_index"]
            cls = res["csv_row"]["classification"]
            pts_used = res["csv_row"]["n_sample_points"]
            poi_used = res["csv_row"]["total_pois_used"]
            
            print(f"Points: {n:2d} | Actual Pts: {pts_used:2d} | Score: {score:5.1f} ({cls:7s}) | POIs: {poi_used:4d} | Time: {math_time:.3f}s")
            
            results.append({
                "pincode": pc,
                "n_req": n,
                "n_actual": pts_used,
                "score": score,
                "class": cls,
                "pois": poi_used,
                "time_s": math_time
            })
            
if __name__ == "__main__":
    main()
