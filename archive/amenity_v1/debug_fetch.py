
import logging
import sys
import os

# Add amenity_scorer to sys.path so 'import config' and 'from utils import' work inside poi_fetcher
sys.path.append(os.path.join(os.path.dirname(__file__), "amenity_scorer"))

from amenity_v1.poi_fetcher import POIFetcher

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_fetch")

def debug_location(lat, lon):
    print(f"--- DEBUG FETCHING ({lat}, {lon}) ---")
    fetcher = POIFetcher(logger)
    
    # Force fresh fetch if needed, but standard fetch usage first
    pois = fetcher.fetch(lat, lon, max_radius_km=2.0)
    
    print(f"Total POIs fetched: {len(pois)}")
    
    if pois:
        print("Sample POIs:")
        for p in pois[:5]:
            print(p)
            
    # Check if they have valid types
    valid = [p for p in pois if p.get('poi_type')]
    print(f"POIs with valid 'poi_type': {len(valid)}")

if __name__ == "__main__":
    # Nariman Point
    lat = 18.926245
    lon = 72.8279664
    debug_location(lat, lon)
