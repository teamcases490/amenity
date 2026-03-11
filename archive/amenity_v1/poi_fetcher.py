"""
POI Fetcher
===========

Fetches Points of Interest from OpenStreetMap with comprehensive tag coverage.
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict

import amenity_v1.config
from amenity_v1.utils import haversine_distance, generate_cache_key, RateLimiter


class POIFetcher:
    """
    Fetch POIs from OpenStreetMap with ALL tag types.
    
    Queries: amenity, shop, healthcare, leisure, office, railway, tourism,
             sport, craft, emergency, public_transport
    """
    
    def __init__(self, logger):
        """
        Initialize POI fetcher.
        
        Args:
            logger: Logger instance
        """
        self.logger = logger
        self.rate_limiter = RateLimiter(config.REQUESTS_PER_SECOND)
        
        self.cache_dir = Path(config.CACHE_DIR)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_ttl = timedelta(days=config.CACHE_TTL_DAYS)
    
    def fetch(self, lat: float, lon: float, max_radius_km: float = 2.0, force_refresh: bool = False) -> List[Dict]:
        """
        Fetch ALL POIs at max radius (single API call).
        
        Args:
            lat: Latitude
            lon: Longitude
            max_radius_km: Maximum radius in kilometers
            force_refresh: Force refresh cache (ignore existing cache)
        
        Returns:
            List of POI dictionaries with lat, lon, poi_type, name, distance_km, tags
        """
        cache_key = generate_cache_key(lat, lon, max_radius_km)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        # DEBUG: Log cache file usage
        self.logger.debug(f"Checking cache: {cache_file} (Lat: {lat}, Lon: {lon}, R: {max_radius_km})")
        
        # Fix #5: Check cache (skip if force_refresh)
        if not force_refresh and cache_file.exists():
            cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if cache_age < self.cache_ttl:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    pois = json.load(f)
                
                # CRITICAL FIX: Extract poi_type from tags if missing
                for poi in pois:
                    if 'poi_type' not in poi or not poi['poi_type']:
                        poi['poi_type'] = self._extract_poi_type(poi.get('tags', {}))
                
                self.logger.debug(f"Cache hit: {len(pois)} POIs")
                return pois
        
        # Fetch from API
        self.logger.info(f"Fetching POIs: ({lat:.4f}, {lon:.4f}) @ {max_radius_km}km")
        pois = self._fetch_from_osm(lat, lon, max_radius_km)
        
        # Cache result
        if pois:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(pois, f)
            self.logger.info(f"Cached {len(pois)} POIs")
        
        return pois or []
    
    def _fetch_from_osm(self, lat: float, lon: float, radius_km: float) -> List[Dict]:
        """Fetch from OSM Overpass API with retries."""
        radius_m = radius_km * 1000
        query = self._build_comprehensive_query(lat, lon, radius_m)
        
        for attempt in range(config.API_MAX_RETRIES):
            self.rate_limiter.wait()
            
            try:
                response = requests.post(
                    config.OSM_OVERPASS_URL,
                    data={'data': query},
                    timeout=config.API_TIMEOUT
                )
                
                # Check for rate limiting
                if response.status_code == 429:
                    # Exponential backoff for rate limits: 30s, 60s, 120s...
                    wait_time = 30 * (2 ** attempt)
                    self.logger.warning(f"Rate limited (429). Waiting {wait_time}s... (Attempt {attempt+1}/{config.API_MAX_RETRIES})")
                    time.sleep(wait_time)
                    continue
                
                if response.status_code == 504:
                    wait_time = 20 * (attempt + 1)
                    self.logger.warning(f"Gateway Timeout (504). Waiting {wait_time}s... (Attempt {attempt+1})")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                data = response.json()
                
                pois = self._parse_response(data, lat, lon)
                self.logger.info(f"[SUCCESS] Fetched {len(pois)} POIs")
                
                # CRITICAL: If valid response but 0 POIs, ensure we don't cache if it looks suspicious
                # (though for Rural areas 0 is valid, but for Colaba it shouldn't be).
                # For now, we accept it but log it.
                if not pois:
                    self.logger.warning(f"Fetched 0 POIs at ({lat}, {lon}). This might be valid for rural, but check query.")
                
                return pois
            
            except Exception as e:
                self.logger.error(f"Fetch error (attempt {attempt + 1}): {e}")
                if attempt < config.API_MAX_RETRIES - 1:
                    import random
                    sleep_time = (2 ** attempt) + random.uniform(1, 3)
                    time.sleep(sleep_time)
        
        # If all retries failed, RAISE ERROR instead of returning empty list
        # This allows main.py to handle it (e.g., skip, re-queue, or error out)
        raise RuntimeError(f"Failed to fetch POIs after {config.API_MAX_RETRIES} attempts. Last status: {response.status_code if 'response' in locals() else 'Unknown'}")
    
    def _build_comprehensive_query(self, lat: float, lon: float, radius_m: float) -> str:
        """
        Build Overpass query with ALL OSM tag types + India-specific tags.
        
        This is KEY to maximizing POI coverage for Indian locations!
        """
        query = f"""
        [out:json][timeout:120];
        (
          /* AMENITY tags - restaurants, banks, hospitals, schools, etc. */
          node["amenity"](around:{radius_m},{lat},{lon});
          way["amenity"](around:{radius_m},{lat},{lon});
          
          /* SHOP tags - malls, supermarkets, stores, retail */
          node["shop"](around:{radius_m},{lat},{lon});
          way["shop"](around:{radius_m},{lat},{lon});
          
          /* HEALTHCARE tags - hospitals, clinics, pharmacies */
          node["healthcare"](around:{radius_m},{lat},{lon});
          way["healthcare"](around:{radius_m},{lat},{lon});
          
          /* LEISURE tags - gyms, parks, sports centers, playgrounds */
          node["leisure"](around:{radius_m},{lat},{lon});
          way["leisure"](around:{radius_m},{lat},{lon});
          
          /* OFFICE tags - employment centers, coworking spaces */
          node["office"](around:{radius_m},{lat},{lon});
          way["office"](around:{radius_m},{lat},{lon});
          
          /* RAILWAY tags - metro, train stations, subway */
          node["railway"~"^(station|halt|subway|light_rail|monorail)$"](around:{radius_m},{lat},{lon});
          way["railway"~"^(station|halt|subway|light_rail|monorail)$"](around:{radius_m},{lat},{lon});
          
          /* TOURISM tags - hotels, attractions, museums */
          node["tourism"](around:{radius_m},{lat},{lon});
          way["tourism"](around:{radius_m},{lat},{lon});
          
          /* SPORT tags - sports facilities, stadiums */
          node["sport"](around:{radius_m},{lat},{lon});
          way["sport"](around:{radius_m},{lat},{lon});
          
          /* CRAFT tags - workshops, artisans */
          node["craft"](around:{radius_m},{lat},{lon});
          way["craft"](around:{radius_m},{lat},{lon});
          
          /* EMERGENCY tags - police, fire stations */
          node["emergency"](around:{radius_m},{lat},{lon});
          way["emergency"](around:{radius_m},{lat},{lon});
          
          /* PUBLIC_TRANSPORT tags - bus stops, stations */
          node["public_transport"](around:{radius_m},{lat},{lon});
          way["public_transport"](around:{radius_m},{lat},{lon});
          
          /* INDIA-SPECIFIC: Coaching centers (very common in India) */
          node["amenity"="coaching"](around:{radius_m},{lat},{lon});
          way["amenity"="coaching"](around:{radius_m},{lat},{lon});
          node["amenity"="training"](around:{radius_m},{lat},{lon});
          way["amenity"="training"](around:{radius_m},{lat},{lon});
          
          /* INDIA-SPECIFIC: Kirana stores (neighborhood grocery) */
          node["shop"="kirana"](around:{radius_m},{lat},{lon});
          way["shop"="kirana"](around:{radius_m},{lat},{lon});
          node["shop"="general"](around:{radius_m},{lat},{lon});
          way["shop"="general"](around:{radius_m},{lat},{lon});
          node["shop"="convenience"](around:{radius_m},{lat},{lon});
          way["shop"="convenience"](around:{radius_m},{lat},{lon});
          
          /* INDIA-SPECIFIC: Medical shops/chemists */
          node["shop"="medical"](around:{radius_m},{lat},{lon});
          way["shop"="medical"](around:{radius_m},{lat},{lon});
          node["shop"="chemist"](around:{radius_m},{lat},{lon});
          way["shop"="chemist"](around:{radius_m},{lat},{lon});
          
          /* INDIA-SPECIFIC: Salons and beauty parlors */
          node["shop"="beauty"](around:{radius_m},{lat},{lon});
          way["shop"="beauty"](around:{radius_m},{lat},{lon});
          node["shop"="hairdresser"](around:{radius_m},{lat},{lon});
          way["shop"="hairdresser"](around:{radius_m},{lat},{lon});
          
          /* INDIA-SPECIFIC: Gyms and fitness centers */
          node["leisure"="fitness_centre"](around:{radius_m},{lat},{lon});
          way["leisure"="fitness_centre"](around:{radius_m},{lat},{lon});
          node["amenity"="gym"](around:{radius_m},{lat},{lon});
          way["amenity"="gym"](around:{radius_m},{lat},{lon});
          
          /* INDIA-SPECIFIC: Temples, mosques, churches, gurudwaras */
          node["amenity"="place_of_worship"](around:{radius_m},{lat},{lon});
          way["amenity"="place_of_worship"](around:{radius_m},{lat},{lon});
          
          /* INDIA-SPECIFIC: Auto/taxi stands */
          node["amenity"="taxi"](around:{radius_m},{lat},{lon});
          way["amenity"="taxi"](around:{radius_m},{lat},{lon});
          node["highway"="bus_stop"](around:{radius_m},{lat},{lon});
          
          /* INDIA-SPECIFIC: Petrol pumps */
          node["amenity"="fuel"](around:{radius_m},{lat},{lon});
          way["amenity"="fuel"](around:{radius_m},{lat},{lon});
          
          /* BUILDING tags - CRITICAL for employment, civic, cultural */
          node["building"~"^(commercial|office|retail|hospital|school|college|university|government|public|train_station|hotel|stadium|temple|church|mosque|industrial)$"](around:{radius_m},{lat},{lon});
          way["building"~"^(commercial|office|retail|hospital|school|college|university|government|public|train_station|hotel|stadium|temple|church|mosque|industrial)$"](around:{radius_m},{lat},{lon});
          
          /* TRANSPORTATION - AIR */
          node["aeroway"](around:{radius_m},{lat},{lon});
          way["aeroway"](around:{radius_m},{lat},{lon});

          /* TRANSPORTATION - AERIAL */
          node["aerialway"](around:{radius_m},{lat},{lon});
          way["aerialway"](around:{radius_m},{lat},{lon});

          /* TRANSPORTATION - WATER */
          node["waterway"~"^(dock|boatyard|dam)$"](around:{radius_m},{lat},{lon});
          way["waterway"~"^(dock|boatyard|dam)$"](around:{radius_m},{lat},{lon});

          /* NATURE & LANDMARKS */
          node["natural"~"^(beach|peak|spring|cave_entrance|wood|water)$"](around:{radius_m},{lat},{lon});
          way["natural"~"^(beach|peak|spring|cave_entrance|wood|water)$"](around:{radius_m},{lat},{lon});
          node["man_made"~"^(tower|lighthouse|pier|water_tower|windmill)$"](around:{radius_m},{lat},{lon});
          way["man_made"~"^(tower|lighthouse|pier|water_tower|windmill)$"](around:{radius_m},{lat},{lon});

          /* EXPANDED HIGHWAY (amenity-like only) */
          node["highway"~"^(rest_area|services|elevator|bus_stop|platform)$"](around:{radius_m},{lat},{lon});
          way["highway"~"^(rest_area|services|elevator|bus_stop|platform)$"](around:{radius_m},{lat},{lon});
        );
        out center tags;
        """
        return query
    
    def _parse_response(self, data: Dict, center_lat: float, center_lon: float) -> List[Dict]:
        """
        Parse Overpass API response.
        
        CRITICAL FIX: Properly extract POI type from ANY OSM tag.
        """
        pois = []
        
        for element in data.get('elements', []):
            # Get coordinates
            if element['type'] == 'node':
                poi_lat, poi_lon = element['lat'], element['lon']
            elif element['type'] == 'way' and 'center' in element:
                poi_lat, poi_lon = element['center']['lat'], element['center']['lon']
            else:
                continue
            
            # Get tags
            tags = element.get('tags', {})
            
            # Extract POI type from ANY tag (FIXED!)
            poi_type = self._extract_poi_type(tags)
            
            if not poi_type:
                continue
            
            # Calculate distance
            distance_km = haversine_distance(center_lat, center_lon, poi_lat, poi_lon)
            
            pois.append({
                'lat': poi_lat,
                'lon': poi_lon,
                'poi_type': poi_type,
                'name': tags.get('name', ''),
                'distance_km': distance_km,
                'tags': tags
            })
        
        return pois
    
    def _extract_poi_type(self, tags: Dict) -> str:
        """
        Extract POI type from ANY OSM tag.
        
        Priority order: amenity > shop > healthcare > leisure > office > 
                       railway > tourism > sport > craft > emergency > public_transport > building
        
        IMPORTANT: Building tags are ONLY used if no other primary tag exists.
        This prevents double-counting (e.g., a hospital building is counted as 'hospital', not 'building_hospital').
        """
        # Primary tags (higher priority)
        # Primary tags (higher priority)
        primary_tags = [
            'amenity', 'shop', 'healthcare', 'leisure',
            'tourism', 'sport', 'craft', 'emergency', 'public_transport',
            'aeroway', 'aerialway', 'waterway', 'natural', 'man_made'
        ]
        
        # Check primary tags first
        for tag_key in primary_tags:
            if tag_key in tags and tags[tag_key]:
                return tags[tag_key]
        
        # Special handling for office tags (prefix with 'office_')
        if 'office' in tags and tags['office']:
            return f"office_{tags['office']}"
        
        # Special handling for railway tags (prefix with 'railway_')
        if 'railway' in tags and tags['railway']:
            return f"railway_{tags['railway']}"
            
        # Special handling for highway tags (Amenity-like ONLY)
        # We strictly exclude infrastructure like primary, secondary, residential, etc.
        if 'highway' in tags and tags['highway']:
            hw_val = tags['highway']
            if hw_val in {'bus_stop', 'platform', 'rest_area', 'services', 'elevator'}:
                return hw_val
        
        # Handle building tags LAST (only if no other tag exists)
        # This captures building-only POIs like office buildings, commercial buildings, etc.
        if 'building' in tags and tags['building']:
            building_type = tags['building']
            # Only include specific building types, not generic "yes"
            if building_type != 'yes':
                return f"building_{building_type}"
        
        return ''
    
    def filter_by_radius(self, pois: List[Dict], radius_km: float) -> List[Dict]:
        """Filter POIs to specific radius (distances already calculated)."""
        return [p for p in pois if p['distance_km'] <= radius_km]
