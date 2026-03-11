"""
Google Maps POI Fetcher
=======================

Fetches Points of Interest from Google Maps Platform with enhanced data:
- Star ratings (1-5)
- Review counts
- Price levels ($ to $$$$)
- Business hours (live status)
- Actual road distances
- Business verification
"""

import json
import time
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

import amenity_v1.config
from amenity_v1.utils import haversine_distance, generate_cache_key, RateLimiter

logger = logging.getLogger(__name__)


class GooglePOIFetcher:
    """Fetch POIs from Google Maps Platform with rich amenity data."""
    
    def __init__(self, api_key: str, logger=None):
        """
        Initialize Google POI fetcher.
        
        Args:
            api_key: Google Maps API key
            logger: Logger instance
        """
        self.api_key = api_key
        self.logger = logger or logging.getLogger(__name__)
        self.cache_dir = Path(config.CACHE_DIR)
        self.cache_dir.mkdir(exist_ok=True)
        self.rate_limiter = RateLimiter(config.REQUESTS_PER_SECOND)
        
        # Google Maps API endpoints
        self.places_url = "https://places.googleapis.com/v1/places:searchNearby"
        self.distance_matrix_url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    
    def fetch(self, lat: float, lon: float, max_radius_km: float = 2.0, 
              force_refresh: bool = False, include_distances: bool = True) -> List[Dict]:
        """
        Fetch ALL POIs at max radius with enhanced Google data.
        
        Args:
            lat: Latitude
            lon: Longitude
            max_radius_km: Maximum radius in kilometers
            force_refresh: Force refresh cache
            include_distances: Calculate actual road distances (uses Distance Matrix API)
        
        Returns:
            List of POI dictionaries with enhanced fields
        """
        cache_key = generate_cache_key(lat, lon, max_radius_km)
        cache_file = self.cache_dir / f"google_{cache_key}.json"
        
        # Check cache
        if not force_refresh and cache_file.exists():
            cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if cache_age.days < config.CACHE_TTL_DAYS:
                self.logger.info(f"Cache hit for ({lat}, {lon}) - Age: {cache_age.days} days")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        
        # Fetch from Google Maps
        self.logger.info(f"Fetching from Google Maps: ({lat}, {lon}), radius={max_radius_km}km")
        pois = self._fetch_from_google(lat, lon, max_radius_km)
        
        # Add actual road distances if requested
        if include_distances and pois:
            pois = self._add_actual_distances(lat, lon, pois)
        
        # Cache results
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(pois, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Fetched {len(pois)} POIs from Google Maps")
        return pois
    
    def _fetch_from_google(self, lat: float, lon: float, radius_km: float) -> List[Dict]:
        """Fetch from Google Places API (New) with retries."""
        
        all_pois = []
        
        # Google Places API supports multiple type queries
        # We'll batch by major categories to get comprehensive coverage
        type_batches = [
            # Healthcare & Essential
            ["hospital", "doctor", "dentist", "pharmacy", "physiotherapist", 
             "veterinary_care", "medical_lab"],
            
            # Education
            ["school", "university", "library", "primary_school", "secondary_school"],
            
            # Finance
            ["bank", "atm", "post_office", "accounting", "insurance_agency"],
            
            # Shopping
            ["shopping_mall", "supermarket", "convenience_store", "department_store",
             "clothing_store", "electronics_store", "furniture_store", "book_store",
             "jewelry_store", "shoe_store", "sporting_goods_store", "home_goods_store"],
            
            # Food & Dining
            ["restaurant", "cafe", "bar", "bakery", "meal_takeaway", "meal_delivery",
             "american_restaurant", "chinese_restaurant", "indian_restaurant",
             "italian_restaurant", "japanese_restaurant", "pizza_restaurant"],
            
            # Transport
            ["bus_station", "subway_station", "train_station", "taxi_stand",
             "gas_station", "parking", "car_rental", "airport"],
            
            # Cultural & Recreation
            ["museum", "art_gallery", "movie_theater", "park", "tourist_attraction",
             "amusement_park", "aquarium", "zoo", "stadium", "bowling_alley"],
            
            # Premium & Wellness
            ["gym", "spa", "beauty_salon", "hair_care", "lodging", "resort_hotel",
             "extended_stay_hotel", "motel"],
            
            # Employment & Business - REMOVED UNSUPPORTED TYPES
            # Note: Google doesn't support 'office', 'coworking_space', 'business_center'
            # These will be inferred from other data
            
            # Civic & Government
            ["city_hall", "courthouse", "police", "fire_station", "local_government_office",
             "embassy"]
        ]
        
        for batch in type_batches:
            self.rate_limiter.wait()
            
            try:
                pois = self._search_nearby(lat, lon, radius_km, batch)
                all_pois.extend(pois)
                self.logger.info(f"Fetched {len(pois)} POIs for types: {batch[:3]}...")
                
            except Exception as e:
                self.logger.error(f"Error fetching batch {batch[:3]}: {e}")
                continue
        
        # Remove duplicates (same place_id)
        unique_pois = {}
        for poi in all_pois:
            place_id = poi.get('place_id')
            if place_id and place_id not in unique_pois:
                unique_pois[place_id] = poi
        
        return list(unique_pois.values())
    
    def _search_nearby(self, lat: float, lon: float, radius_km: float, 
                       included_types: List[str]) -> List[Dict]:
        """
        Execute nearby search with pagination to get ALL results.
        
        Google Places API returns max 20 results per page.
        We follow nextPageToken to get all available POIs.
        """
        
        headers = {
            'Content-Type': 'application/json',
            'X-Goog-Api-Key': self.api_key,
            'X-Goog-FieldMask': (
                'places.id,'
                'places.displayName,'
                'places.types,'
                'places.location,'
                'places.rating,'
                'places.userRatingCount,'
                'places.priceLevel,'
                'places.currentOpeningHours,'
                'places.businessStatus,'
                'places.formattedAddress,'
                'places.primaryType,'
                'places.regularOpeningHours,'
                'nextPageToken'
            )
        }
        
        data = {
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": lat,
                        "longitude": lon
                    },
                    "radius": radius_km * 1000  # Convert to meters
                }
            },
            "includedTypes": included_types,
            "maxResultCount": 20  # Max per request
        }
        
        all_results = []
        page_count = 0
        max_pages = config.GOOGLE_MAX_PAGES_PER_BATCH  # Configurable pagination depth
        
        while page_count < max_pages:
            for attempt in range(config.API_MAX_RETRIES):
                try:
                    response = requests.post(
                        self.places_url,
                        headers=headers,
                        json=data,
                        timeout=config.API_TIMEOUT
                    )
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        
                        # Parse and add POIs from this page
                        page_pois = self._parse_google_response(response_data, lat, lon)
                        all_results.extend(page_pois)
                        page_count += 1
                        
                        self.logger.info(f"  Page {page_count}: {len(page_pois)} POIs (total: {len(all_results)})")
                        
                        # Check for next page
                        next_page_token = response_data.get('nextPageToken')
                        
                        if next_page_token and page_count < max_pages:
                            # Google requires 2-second delay before using nextPageToken
                            self.logger.info(f"  Fetching next page (waiting 2s)...")
                            time.sleep(2)
                            
                            # Update request with page token
                            data['pageToken'] = next_page_token
                            # Remove locationRestriction when using pageToken (Google requirement)
                            if 'locationRestriction' in data:
                                del data['locationRestriction']
                            if 'includedTypes' in data:
                                del data['includedTypes']
                        else:
                            # No more pages or reached max pages
                            return all_results
                        
                        break  # Success, exit retry loop
                        
                    elif response.status_code == 429:
                        # Rate limit - wait and retry
                        wait_time = 2 ** attempt
                        self.logger.warning(f"Rate limited, waiting {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        self.logger.error(f"API error {response.status_code}: {response.text}")
                        return all_results  # Return what we have so far
                        
                except requests.exceptions.Timeout:
                    self.logger.warning(f"Timeout on attempt {attempt + 1}")
                    if attempt < config.API_MAX_RETRIES - 1:
                        time.sleep(2 ** attempt)
                except Exception as e:
                    self.logger.error(f"Request failed: {e}")
                    return all_results  # Return what we have so far
            
            # If we exhausted retries, return what we have
            if page_count == 0:
                return []
        
        return all_results
    
    def _parse_google_response(self, data: Dict, center_lat: float, center_lon: float) -> List[Dict]:
        """
        Parse Google Places API response.
        
        Extracts enhanced amenity data including ratings, hours, price levels.
        """
        pois = []
        
        for place in data.get('places', []):
            try:
                # Extract location
                location = place.get('location', {})
                poi_lat = location.get('latitude')
                poi_lon = location.get('longitude')
                
                if not poi_lat or not poi_lon:
                    continue
                
                # Calculate straight-line distance
                distance_km = haversine_distance(center_lat, center_lon, poi_lat, poi_lon)
                
                # Extract primary type
                primary_type = place.get('primaryType', '')
                types = place.get('types', [])
                
                # Map to our category system
                poi_type = self._map_google_type(primary_type, types)
                
                # Extract name
                display_name = place.get('displayName', {})
                name = display_name.get('text', 'Unknown') if isinstance(display_name, dict) else str(display_name)
                
                # Extract rating data
                rating = place.get('rating')
                user_ratings_total = place.get('userRatingCount', 0)
                
                # Extract price level (PRICE_LEVEL_UNSPECIFIED, FREE, INEXPENSIVE, MODERATE, EXPENSIVE, VERY_EXPENSIVE)
                price_level_str = place.get('priceLevel', 'PRICE_LEVEL_UNSPECIFIED')
                price_level = self._parse_price_level(price_level_str)
                
                # Extract opening hours
                current_hours = place.get('currentOpeningHours', {})
                regular_hours = place.get('regularOpeningHours', {})
                
                open_now = current_hours.get('openNow', False)
                
                # Extract business status
                business_status = place.get('businessStatus', 'OPERATIONAL')
                is_operational = business_status == 'OPERATIONAL'
                
                # Build POI object with enhanced fields
                poi = {
                    # Basic fields (compatible with OSM structure)
                    'lat': poi_lat,
                    'lon': poi_lon,
                    'poi_type': poi_type,
                    'name': name,
                    'distance_km': distance_km,
                    
                    # Enhanced Google Maps fields
                    'place_id': place.get('id'),
                    'rating': rating,
                    'user_ratings_total': user_ratings_total,
                    'price_level': price_level,
                    'open_now': open_now,
                    'business_status': business_status,
                    'is_operational': is_operational,
                    'types': types,
                    'primary_type': primary_type,
                    'address': place.get('formattedAddress', ''),
                    
                    # Flags for feature engineering
                    'has_rating': rating is not None,
                    'has_reviews': user_ratings_total > 0,
                    'has_price_info': price_level > 0,
                    'is_verified': is_operational and user_ratings_total > 10,
                    
                    # Quality indicators
                    'is_premium': (rating or 0) >= 4.5 or price_level >= 3,
                    'is_popular': user_ratings_total >= 100,
                    'quality_score': self._calculate_quality_score(rating, user_ratings_total, price_level)
                }
                
                pois.append(poi)
                
            except Exception as e:
                self.logger.error(f"Error parsing place: {e}")
                continue
        
        return pois
    
    def _map_google_type(self, primary_type: str, all_types: List[str]) -> str:
        """
        Map Google Place types to our category system.
        
        Uses primary_type first, falls back to types list.
        """
        # Comprehensive mapping
        type_mapping = {
            # Healthcare
            'hospital': 'hospital',
            'doctor': 'doctors',
            'dentist': 'dentist',
            'pharmacy': 'pharmacy',
            'physiotherapist': 'physiotherapist',
            'veterinary_care': 'veterinary',
            'medical_lab': 'laboratory',
            'health': 'health_centre',
            
            # Education
            'school': 'school',
            'primary_school': 'school',
            'secondary_school': 'school',
            'university': 'university',
            'library': 'library',
            'preschool': 'kindergarten',
            
            # Finance
            'bank': 'bank',
            'atm': 'atm',
            'post_office': 'post_office',
            'accounting': 'accountant',
            'insurance_agency': 'insurance',
            
            # Shopping
            'shopping_mall': 'mall',
            'supermarket': 'supermarket',
            'convenience_store': 'convenience',
            'department_store': 'department_store',
            'clothing_store': 'clothes',
            'electronics_store': 'electronics',
            'furniture_store': 'furniture',
            'book_store': 'books',
            'jewelry_store': 'jewelry',
            'shoe_store': 'shoes',
            'sporting_goods_store': 'sports',
            'home_goods_store': 'hardware',
            'grocery_store': 'grocery',
            'liquor_store': 'alcohol',
            'pet_store': 'pet',
            
            # Food
            'restaurant': 'restaurant',
            'cafe': 'cafe',
            'bar': 'bar',
            'bakery': 'bakery',
            'meal_takeaway': 'fast_food',
            'meal_delivery': 'fast_food',
            'american_restaurant': 'restaurant',
            'chinese_restaurant': 'chinese',
            'indian_restaurant': 'indian',
            'italian_restaurant': 'italian',
            'japanese_restaurant': 'sushi',
            'pizza_restaurant': 'pizza',
            'fast_food_restaurant': 'fast_food',
            
            # Transport
            'bus_station': 'bus_station',
            'subway_station': 'subway',
            'train_station': 'station',
            'taxi_stand': 'taxi',
            'gas_station': 'fuel',
            'parking': 'parking',
            'car_rental': 'car_rental',
            'airport': 'airport',
            
            # Cultural
            'museum': 'museum',
            'art_gallery': 'gallery',
            'movie_theater': 'cinema',
            'park': 'park',
            'tourist_attraction': 'attraction',
            'amusement_park': 'attraction',
            'aquarium': 'attraction',
            'zoo': 'attraction',
            'stadium': 'stadium',
            'performing_arts_theater': 'theatre',
            
            # Premium
            'gym': 'gym',
            'spa': 'spa',
            'beauty_salon': 'beauty',
            'hair_care': 'beauty',
            'lodging': 'hotel',
            'hotel': 'hotel',
            'resort_hotel': 'resort',
            'extended_stay_hotel': 'hotel',
            'motel': 'hotel',
            
            # Employment
            'office': 'office',
            'coworking_space': 'coworking_space',
            'business_center': 'office',
            'corporate_office': 'office',
            
            # Civic
            'city_hall': 'townhall',
            'courthouse': 'courthouse',
            'police': 'police',
            'fire_station': 'fire_station',
            'local_government_office': 'government',
            'embassy': 'embassy',
        }
        
        # Try primary type first
        if primary_type in type_mapping:
            return type_mapping[primary_type]
        
        # Try all types
        for t in all_types:
            if t in type_mapping:
                return type_mapping[t]
        
        # Return primary type as fallback
        return primary_type or 'unknown'
    
    def _parse_price_level(self, price_level_str: str) -> int:
        """Convert Google price level string to numeric (0-4)."""
        mapping = {
            'PRICE_LEVEL_UNSPECIFIED': 0,
            'FREE': 0,
            'INEXPENSIVE': 1,      # $
            'MODERATE': 2,          # $$
            'EXPENSIVE': 3,         # $$$
            'VERY_EXPENSIVE': 4     # $$$$
        }
        return mapping.get(price_level_str, 0)
    
    def _calculate_quality_score(self, rating: Optional[float], 
                                 review_count: int, price_level: int) -> float:
        """
        Calculate quality score (0-100) from Google data.
        
        Formula:
        - Rating contributes 70% (rating/5 * 70)
        - Popularity contributes 20% (log scale)
        - Price level contributes 10%
        """
        if rating is None:
            rating = 3.0  # Default neutral rating
        
        # Rating component (0-70)
        rating_score = (rating / 5.0) * 70
        
        # Popularity component (0-20) - logarithmic scale
        if review_count > 0:
            import math
            popularity_score = min(20, math.log10(review_count + 1) * 5)
        else:
            popularity_score = 0
        
        # Price level component (0-10)
        price_score = (price_level / 4.0) * 10
        
        total = rating_score + popularity_score + price_score
        return round(min(100, total), 1)
    
    def _add_actual_distances(self, origin_lat: float, origin_lon: float, 
                             pois: List[Dict]) -> List[Dict]:
        """
        Add actual road distances using Distance Matrix API.
        
        Batches POIs to minimize API calls (max 25 destinations per request).
        """
        if not pois:
            return pois
        
        self.logger.info(f"Calculating actual distances for {len(pois)} POIs...")
        
        # Batch POIs (max 25 per request)
        batch_size = 25
        batches = [pois[i:i+batch_size] for i in range(0, len(pois), batch_size)]
        
        for batch in batches:
            self.rate_limiter.wait()
            
            try:
                # Build destinations string
                destinations = '|'.join([f"{p['lat']},{p['lon']}" for p in batch])
                
                params = {
                    'origins': f"{origin_lat},{origin_lon}",
                    'destinations': destinations,
                    'mode': 'walking',  # Default to walking
                    'key': self.api_key
                }
                
                response = requests.get(self.distance_matrix_url, params=params, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data['status'] == 'OK':
                        elements = data['rows'][0]['elements']
                        
                        for i, element in enumerate(elements):
                            if element['status'] == 'OK':
                                # Add actual distance and time
                                batch[i]['actual_distance_km'] = element['distance']['value'] / 1000
                                batch[i]['walk_time_min'] = element['duration']['value'] / 60
                                
                                # Calculate accuracy of Haversine
                                haversine_dist = batch[i]['distance_km']
                                actual_dist = batch[i]['actual_distance_km']
                                batch[i]['distance_accuracy'] = haversine_dist / actual_dist if actual_dist > 0 else 1.0
                            else:
                                # Fallback to Haversine
                                batch[i]['actual_distance_km'] = batch[i]['distance_km']
                                batch[i]['walk_time_min'] = batch[i]['distance_km'] * 12  # ~12 min per km
                                batch[i]['distance_accuracy'] = 1.0
                
            except Exception as e:
                self.logger.error(f"Distance Matrix API error: {e}")
                # Fallback to Haversine for this batch
                for poi in batch:
                    poi['actual_distance_km'] = poi['distance_km']
                    poi['walk_time_min'] = poi['distance_km'] * 12
                    poi['distance_accuracy'] = 1.0
        
        return pois
    
    def filter_by_radius(self, pois: List[Dict], radius_km: float) -> List[Dict]:
        """Filter POIs to specific radius (distances already calculated)."""
        # Use actual distance if available, otherwise use Haversine
        return [
            p for p in pois 
            if p.get('actual_distance_km', p.get('distance_km', 999)) <= radius_km
        ]
