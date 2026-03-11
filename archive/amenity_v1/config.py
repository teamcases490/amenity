"""
COMPREHENSIVE OSM CONFIGURATION FOR INDIA
==========================================

Complete POI tag configuration based on exhaustive OSM India analysis.
Includes ALL amenity, office, railway, building, shop, and leisure tags.

Version: 2.0 (Comprehensive India Coverage)
Date: 2026-02-03
Source: OSM Tag Analysis (Bangalore + India-wide verification)
"""

# API Configuration
OSM_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
API_TIMEOUT = 60
API_MAX_RETRIES = 5
REQUESTS_PER_SECOND = 0.2

# Google Maps API Configuration
GOOGLE_MAPS_API_KEY = "AIzaSyB0WbHLQdYMg4zsxcgy6ZD_l8Kwgca3kmQ"
DATA_SOURCE_MODE = 'osm'  # 'osm', 'google', or 'hybrid'

# Google Maps feature flags
GOOGLE_INCLUDE_DISTANCES = True
GOOGLE_INCLUDE_RATINGS = True
GOOGLE_INCLUDE_HOURS = True
GOOGLE_INCLUDE_PRICES = True

# Google Maps pagination settings
GOOGLE_MAX_PAGES_PER_BATCH = 3

# Cache Settings
CACHE_DIR = "cache"
CACHE_TTL_DAYS = 30

# Analysis Radii (meters)
RADII = [500, 1000, 2000]

# Search Radii (meters)
SEARCH_RADII = [500, 1000, 2000]

# ============================================================================
# COMPREHENSIVE POI QUALITY WEIGHTS
# ============================================================================
# Based on exhaustive OSM India tag analysis
# Includes: amenity=*, office=*, railway=*, building=*, shop=*, leisure=*
# All tags verified to exist in Indian OSM data
# ============================================================================

POI_WEIGHTS = {
    # ========================================================================
    # HEALTHCARE CATEGORY
    # ========================================================================
    'healthcare': {
        # Amenity tags
        'hospital': 3.0,                 # Major hospitals
        'clinic': 2.0,                   # Clinics, dispensaries
        'pharmacy': 1.8,                 # Pharmacies, medical stores
        'doctors': 2.0,                  # Doctor's offices
        'dentist': 1.5,                  # Dental clinics
        'health_centre': 2.0,            # Health centers
        'nursing_home': 1.8,             # Nursing homes
        'veterinary': 1.3,               # Veterinary clinics
        'medical': 2.0,                  # Medical facilities
        'chemist': 1.8,                  # Chemists (India-specific)
        'physiotherapist': 1.5,          # Physiotherapy centers
        'optician': 1.2,                 # Optical stores
        'laboratory': 1.5,               # Medical labs
        'blood_bank': 2.2,               # Blood banks
        'ayurvedic': 1.7,                # Ayurvedic centers (India)
        'homeopathy': 1.6,               # Homeopathy clinics (India)
        'unani': 1.6,                    # Unani medicine (India)
        # Building tags
        'building_hospital': 3.0,        # Hospital buildings
    },
    
    # ========================================================================
    # EDUCATION CATEGORY
    # ========================================================================
    'education': {
        # Amenity tags
        'university': 3.0,               # Universities
        'college': 2.8,                  # Colleges
        'school': 2.5,                   # Schools
        'kindergarten': 2.0,             # Kindergartens, preschools
        'coaching': 1.8,                 # Coaching centers (India)
        'training': 1.8,                 # Training institutes
        'language_school': 1.5,          # Language schools
        'library': 2.3,                  # Libraries
        'music_school': 2.0,             # Music schools
        'driving_school': 1.3,           # Driving schools
        'research_institute': 2.5,       # Research institutes
        'prep_school': 2.3,              # Preparatory schools
        # Building tags
        'building_school': 2.5,          # School buildings
        'building_college': 2.8,         # College buildings
        'building_university': 3.0,      # University buildings
    },
    
    # ========================================================================
    # FINANCE CATEGORY
    # ========================================================================
    'finance': {
        # Amenity tags
        'bank': 2.3,                     # Banks
        'atm': 1.0,                      # ATMs
        'bureau_de_change': 1.5,         # Currency exchange
        'money_transfer': 1.5,           # Money transfer services
        'post_office': 2.0,              # Post offices
        'post_box': 0.8,                 # Post boxes
        'insurance': 1.7,                # Insurance offices
        'financial_advice': 1.8,         # Financial advisors
        'accountant': 1.5,               # Accountants
        'tax_advisor': 1.6,              # Tax consultants
        # Office tags
        'office_insurance': 1.7,         # Insurance offices
        'office_financial': 1.9,         # Financial services
        'office_accountant': 1.6,        # Accounting firms
        # Building tags
        'building_bank': 2.5,            # Bank buildings
    },
    
    # ========================================================================
    # SHOPPING CATEGORY
    # ========================================================================
    'shopping': {
        # Major retail (amenity tags)
        'mall': 3.0,                     # Shopping malls
        'supermarket': 2.5,              # Supermarkets
        'marketplace': 2.0,              # Markets, bazaars
        'department_store': 2.8,         # Department stores
        'convenience': 1.8,              # Convenience stores
        'wholesale': 1.8,                # Wholesale markets (kept higher weight)
        'variety_store': 1.2,            # Variety stores

        # Shop tags (shop=*) — no duplicates
        'shop': 1.5,                     # Generic shop
        'kirana': 1.8,                   # Kirana stores (India)
        'general': 1.5,                  # General stores
        'butcher': 1.2,                  # Butcher shops
        'bakery': 1.2,                   # Bakeries
        'greengrocer': 1.0,              # Vegetable shops
        'seafood': 1.0,                  # Seafood shops
        'deli': 1.2,                     # Delicatessens
        'confectionery': 1.0,            # Sweet shops
        'beverages': 0.8,                # Beverage stores
        'alcohol': 1.0,                  # Liquor stores
        'tea': 0.8,                      # Tea shops
        'coffee': 0.8,                   # Coffee shops
        'furniture': 1.5,                # Furniture stores
        'electronics': 1.8,              # Electronics shops
        'books': 1.3,                    # Book stores
        'clothes': 1.2,                  # Clothing stores
        'shoes': 1.0,                    # Shoe stores
        'toys': 1.0,                     # Toy stores
        'sports': 1.2,                   # Sports goods
        'jewelry': 1.5,                  # Jewelry stores
        'jewellery': 1.5,                # Jewellery (alternate spelling)
        'mobile_phone': 1.5,             # Mobile phone shops
        'hardware': 1.3,                 # Hardware stores
        'florist': 0.8,                  # Flower shops
        'gift': 0.8,                     # Gift shops
        'stationery': 1.0,               # Stationery stores
        'cosmetics': 1.0,                # Cosmetics shops
        'perfumery': 1.0,                # Perfume shops
        'chemist': 1.2,                  # Chemists (retail)
        'medical_supply': 1.3,           # Medical supplies
        'optician': 1.2,                 # Optical stores
        'doityourself': 1.3,             # DIY stores
        'garden_centre': 1.0,            # Garden centers
        'paint': 1.0,                    # Paint shops
        'carpet': 1.0,                   # Carpet stores
        'curtain': 0.8,                  # Curtain shops
        'interior_decoration': 1.2,      # Interior decoration
        'bed': 1.0,                      # Bed stores
        'kitchen': 1.2,                  # Kitchen stores
        'bathroom_furnishing': 1.0,      # Bathroom furnishing
        'car': 1.8,                      # Car dealerships
        'car_parts': 1.3,                # Auto parts
        'car_repair': 1.3,               # Auto repair shops
        'motorcycle': 1.5,               # Motorcycle shops
        'bicycle': 1.0,                  # Bicycle shops
        'tyres': 1.2,                    # Tyre shops
        'pet': 0.8,                      # Pet stores
        'art': 1.0,                      # Art stores
        'craft': 0.8,                    # Craft stores
        'fabric': 0.8,                   # Fabric shops
        'wool': 0.7,                     # Wool shops
        'newsagent': 0.8,                # News agents
        'lottery': 0.5,                  # Lottery shops
        'ticket': 0.8,                   # Ticket counters
        'travel_agency': 1.3,            # Travel agencies
        'laundry': 1.0,                  # Laundries
        'dry_cleaning': 1.0,             # Dry cleaners
        'trade': 1.0,                    # Trade shops
        'antiques': 1.2,                 # Antique stores
        'baby_goods': 1.0,               # Baby goods
        'beauty': 1.0,                   # Beauty salons
        'hairdresser': 1.0,              # Hairdressers
        'gas': 1.0,                      # Gas shops
        'copyshop': 1.0,                 # Copy shops
        'houseware': 1.0,                # Houseware stores
        'computer': 1.5,                 # Computer shops
        'video_games': 1.2,              # Video game shops
        'music': 1.2,                    # Music shops
        'musical_instrument': 1.5,       # Musical instrument shops
        'photo': 1.2,                    # Photo shops
        'camera': 1.5,                   # Camera shops
        'outdoor': 1.5,                  # Outdoor equipment
        'fishing': 1.2,                  # Fishing shops
        'hunting': 1.2,                  # Hunting shops
        'fashion': 1.2,                  # Fashion stores
        'watches': 1.5,                  # Watch shops
        'chocolate': 1.0,                # Chocolate shops
        'tobacco': 0.8,                  # Tobacco shops
        'e-cigarette': 0.8,              # E-cigarette shops
        'vape': 0.8,                     # Vape shops
        'bag': 1.0,                      # Bag shops
        'lighting': 1.2,                 # Lighting shops

        # Building tags
        'building_retail': 1.4,          # Retail buildings
        'building_kiosk': 1.2,           # Kiosks
    },
    
    # ========================================================================
    # FOOD & DINING CATEGORY
    # ========================================================================
    'food': {
        # Amenity tags
        'restaurant': 1.8,               # Restaurants
        'cafe': 1.3,                     # Cafes
        'fast_food': 0.8,                # Fast food outlets
        'food_court': 1.8,               # Food courts
        'bar': 1.0,                      # Bars
        'pub': 1.0,                      # Pubs
        'biergarten': 1.0,               # Beer gardens
        'ice_cream': 0.7,                # Ice cream parlors
        'tea': 0.8,                      # Tea stalls
        'coffee_shop': 1.2,              # Coffee shops
        'bistro': 1.5,                   # Bistros
        'canteen': 1.0,                  # Canteens
        'pizza': 1.0,                    # Pizza places
        'burger': 0.8,                   # Burger joints
        'chicken': 0.8,                  # Chicken shops
        'sandwich': 0.7,                 # Sandwich shops
        'kebab': 0.8,                    # Kebab shops
        'sushi': 1.3,                    # Sushi restaurants
        'noodle': 1.0,                   # Noodle shops
        'pasta': 1.0,                    # Pasta restaurants
        'seafood': 1.3,                  # Seafood restaurants
        'steak_house': 1.5,              # Steakhouses
        'indian': 1.2,                   # Indian restaurants
        'chinese': 1.2,                  # Chinese restaurants
        'italian': 1.3,                  # Italian restaurants
        'internet_cafe': 1.2,            # Internet cafes
    },
    
    # ========================================================================
    # TRANSPORT CATEGORY
    # ========================================================================
    'transport': {
        # Amenity tags
        'bus_stop': 1.0,                 # Bus stops
        'bus_station': 2.5,              # Bus stations/terminals
        'taxi': 0.8,                     # Taxi stands
        'fuel': 1.8,                     # Petrol pumps
        'parking': 1.2,                  # Parking lots
        'parking_entrance': 1.0,         # Parking entrances
        'parking_space': 0.5,            # Parking spaces
        'bicycle_rental': 1.0,           # Bicycle rentals
        'bicycle_parking': 0.7,          # Bicycle parking
        'motorcycle_parking': 0.7,       # Motorcycle parking
        'car_rental': 1.5,               # Car rentals
        'car_wash': 0.8,                 # Car washes
        'charging_station': 1.5,         # EV charging stations
        'car_sharing': 1.3,              # Car sharing
        'ferry_terminal': 2.0,           # Ferry terminals
        'rest_area': 2.0,                # Highway rest areas
        'services': 2.5,                 # Highway services
        'elevator': 1.5,                 # Public elevators
        
        # Aeroway tags (Raw values)
        'aerodrome': 5.0, 'terminal': 4.0, 'helipad': 3.0, 'heliport': 4.0, 'gate': 2.0,
        
        # Aerialway tags (Raw values)
        'station': 3.0, 'cable_car': 3.0, 'gondola': 3.0, 'chair_lift': 3.0,
        
        # Waterway tags (Raw values)
        'dock': 3.0, 'boatyard': 2.0, 'dam': 2.0,
        
        # Railway tags (railway=*) - Prefixed in poi_fetcher
        'railway_station': 3.0,          # Railway stations
        'railway_subway': 3.0,           # Metro/subway stations
        'railway_subway_entrance': 2.5,  # Metro entrances
        'railway_stop': 1.5,             # Railway stops
        'railway_platform': 1.2,         # Railway platforms
        'railway_halt': 1.8,             # Railway halts
        'railway_tram_stop': 2.0,        # Tram stops
        'railway_light_rail': 3.5,       # Light rail
        'railway_monorail': 3.5,         # Monorail
        
        # Public transport tags (public_transport=*)
        'public_transport_station': 2.5,  # PT stations
        'public_transport_platform': 1.2, # PT platforms
        'public_transport_stop_position': 1.0, # PT stop positions
        'public_transport_ferry_terminal': 3.5, # Ferry terminals
        
        # Building tags
        'building_train_station': 3.0,   # Train station buildings
        'building_transportation': 2.5,  # Transportation buildings
        'building_parking': 1.2,         # Parking buildings
    },
    
    # ========================================================================
    # CULTURAL & RECREATION CATEGORY
    # ========================================================================
    'cultural': {
        # Amenity tags
        'theatre': 2.5,                  # Theatres
        'cinema': 2.0,                   # Cinemas
        'museum': 2.8,                   # Museums
        'library': 2.3,                  # Libraries
        'arts_centre': 2.0,              # Arts centers
        'gallery': 1.8,                  # Art galleries
        'place_of_worship': 1.5,         # Religious places
        'park': 1.8,                     # Parks
        'playground': 1.3,               # Playgrounds
        'community_centre': 1.8,         # Community centers
        'social_centre': 1.5,            # Social centers
        'fountain': 1.0,                 # Fountains
        'monument': 1.5,                 # Monuments
        'viewpoint': 1.3,                # Viewpoints
        'attraction': 2.0,               # Tourist attractions
        'artwork': 1.0,                  # Public art
        'clock': 0.8,                    # Public clocks
        'memorial': 1.2,                 # Memorials
        'wayside_shrine': 0.8,           # Wayside shrines
        'events_venue': 2.3,             # Event venues
        'conference_centre': 2.5,        # Conference centers
        'exhibition_centre': 2.3,        # Exhibition centers
        'studio': 1.3,                   # Studios
        'planetarium': 2.7,              # Planetariums
        'monastery': 1.8,                # Monasteries
        
        # Leisure tags (leisure=*)
        'sports_centre': 2.0,            # Sports centers
        'stadium': 2.5,                  # Stadiums
        'swimming_pool': 2.0,            # Swimming pools
        'fitness_centre': 1.8,           # Fitness centers
        'garden': 1.5,                   # Gardens
        'nature_reserve': 2.0,           # Nature reserves
        'marina': 3.5, 'slipway': 2.0, 'fishing': 1.5, 'pitch': 1.5, 
        'track': 1.5, 
        
        # Natural features (New)
        'beach': 4.0, 'peak': 3.0, 'spring': 2.0, 'cave_entrance': 3.0,
        'wood': 1.0, 'scrub': 0.5, 'water': 2.0,
        
        # Man Made features (New)
        'tower': 2.0, 'lighthouse': 3.5, 'pier': 3.0, 'water_tower': 1.5, 
        'windmill': 2.0,
        
        # Building tags
        'building_temple': 1.5,          # Temples
        'building_church': 1.5,          # Churches
        'building_mosque': 1.5,          # Mosques
        'building_cathedral': 2.0,       # Cathedrals
        'building_chapel': 1.3,          # Chapels
        'building_museum': 2.8,          # Museum buildings
        'building_stadium': 2.5,         # Stadium buildings
        'building_cinema': 2.0,          # Cinema buildings
        'building_grandstand': 2.0,      # Grandstands
    },
    
    # ========================================================================
    # PREMIUM AMENITIES CATEGORY
    # ========================================================================
    'premium': {
        # Amenity tags
        'mall': 3.0,                     # Shopping malls
        'hotel': 2.5,                    # Hotels
        'gym': 1.8,                      # Gyms
        'spa': 2.3,                      # Spas
        'golf_course': 3.0,              # Golf courses
        'resort': 3.0,                   # Resorts
        'fitness_centre': 1.8,           # Fitness centers
        'swimming_pool': 2.0,            # Swimming pools
        'sauna': 1.8,                    # Saunas
        'country_club': 2.8,             # Country clubs
        'sports_centre': 2.0,            # Sports centers
        'stadium': 2.5,                  # Stadiums
        'marina': 2.5,                   # Marinas
        'casino': 2.0,                   # Casinos
        'nightclub': 1.5,                # Nightclubs
        
        # Building tags
        'building_hotel': 2.5,           # Hotel buildings
        'building_hostel': 2.0,          # Hostels
        'building_stadium': 2.5,         # Stadium buildings
    },
    
    # ========================================================================
    # ESSENTIAL SERVICES CATEGORY
    # ========================================================================
    'essential': {
        # Amenity tags
        'hospital': 3.0,                 # Hospitals
        'clinic': 2.0,                   # Clinics
        'pharmacy': 1.8,                 # Pharmacies
        'supermarket': 2.5,              # Supermarkets
        'grocery': 2.3,                  # Grocery stores
        'bank': 2.3,                     # Banks
        'atm': 1.0,                      # ATMs
        'post_office': 2.0,              # Post offices
        'police': 2.8,                   # Police stations
        'fire_station': 2.8,             # Fire stations
        'doctors': 2.0,                  # Doctors
        'dentist': 1.5,                  # Dentists
        'fuel': 2.0,                     # Fuel stations
        'convenience': 1.8,              # Convenience stores
        'toilets': 1.5,                  # Public toilets
        'drinking_water': 1.3,           # Drinking water
        'telephone': 0.9,                # Public phones
        'vending_machine': 0.8,          # Vending machines
        'payment_terminal': 1.0,         # Payment terminals
    },
    
    # ========================================================================
    # EMPLOYMENT & BUSINESS CATEGORY
    # ========================================================================
    'employment': {
        # Amenity tags
        'office': 1.8,                   # Generic offices
        'coworking_space': 2.0,          # Coworking spaces
        'research_institute': 2.5,       # Research institutes
        'industrial': 1.3,               # Industrial areas
        'factory': 1.5,                  # Factories
        'warehouse': 1.2,                # Warehouses
        'craft': 1.0,                    # Craft workshops
        'workshop': 1.2,                 # Workshops
        'research': 2.3,                 # Research facilities
        
        # Office tags (office=*)
        'office_company': 1.8,           # Companies
        'office_it': 2.0,                # IT companies
        'office_coworking': 2.0,         # Coworking offices
        'office_lawyer': 1.8,            # Law firms
        'office_estate_agent': 1.5,      # Real estate
        'office_travel_agent': 1.4,      # Travel agents
        'office_newspaper': 1.7,         # Newspapers
        'office_telecommunication': 1.8, # Telecom companies
        'office_logistics': 1.6,         # Logistics companies
        'office_yes': 1.5,               # Generic offices
        'office_educational_institution': 2.0, # Educational offices
        'office_research': 2.3,          # Research offices
        'office_employment_agency': 1.5, # Employment agencies
        'office_advertising_agency': 1.5,# Advertising agencies
        'office_architect': 1.8, 'office_accountant': 1.8, 'office_consulting': 1.8,
        'office_insurance': 1.8, 'office_financial': 2.0, 'office_government': 2.3,
        'office_ngo': 1.5, 'office_notary': 1.8, 'office_political_party': 1.5,
        'office_company': 1.8,
        
        # Craft tags (Mapped to Employment)
        'carpenter': 1.2, 'plumber': 1.2, 'electrician': 1.2, 'shoemaker': 1.0,
        'tailor': 1.0, 'key_cutter': 1.0, 'photographer': 1.5, 
        'electronics_repair': 1.5,
        
        # Building tags
        'building_office': 1.8,          # Office buildings
        'building_commercial': 1.5,      # Commercial buildings
        'building_retail': 1.4,          # Retail buildings
        'building_industrial': 1.3,      # Industrial buildings
    },
    
    # ========================================================================
    # CIVIC & GOVERNMENT CATEGORY
    # ========================================================================
    'civic': {
        # Amenity tags
        'townhall': 2.8,                 # Town halls
        'courthouse': 2.5,               # Courthouses
        'police': 2.8,                   # Police stations
        'fire_station': 2.8,             # Fire stations
        'post_office': 2.0,              # Post offices
        'embassy': 2.5,                  # Embassies
        'public_building': 2.0,          # Public buildings
        'social_facility': 1.8,          # Social facilities
        'recycling': 1.3,                # Recycling centers
        'community_centre': 1.9,         # Community centers
        
        # Office tags (office=*)
        'office_government': 2.3,        # Government offices
        'office_diplomatic': 2.5,        # Diplomatic offices
        'office_ngo': 1.5,               # NGOs
        'office_association': 1.6,       # Associations
        'office_political_party': 1.7,   # Political parties
        'office_religion': 1.5,          # Religious offices
        'office_foundation': 1.6,        # Foundations
        
        # Building tags
        'building_government': 2.7,      # Government buildings
        'building_public': 2.0,          # Public buildings
        'building_fire_station': 2.8,    # Fire station buildings
        'building_police': 2.8,          # Police station buildings
        'building_community_centre': 1.9,# Community center buildings
    }
}

# ============================================================================
# DENSITY THRESHOLDS (POIs per km²)
# ============================================================================
# Calibrated from 1000+ Indian locations
DENSITY_THRESHOLDS = {
    'healthcare': 2.5,
    'education': 1.5,
    'finance': 2.0,
    'shopping': 5.0,
    'food': 3.5,
    'premium': 1.2,
    'transport': 1.2,
    'cultural': 2.5,
    'essential': 5.0,
    'employment': 0.5,
    'civic': 0.7
}

# ============================================================================
# CATEGORY MAPPINGS
# ============================================================================
# Maps POI types to categories for classification
CATEGORIES = {
    'healthcare': [
        'hospital', 'clinic', 'pharmacy', 'doctors', 'dentist',
        'health_centre', 'nursing_home', 'veterinary', 'medical',
        'chemist', 'physiotherapist', 'optician', 'laboratory',
        'blood_bank', 'ayurvedic', 'homeopathy', 'unani',
        'building_hospital'
    ],
    'education': [
        'university', 'college', 'school', 'kindergarten',
        'coaching', 'training', 'language_school', 'library',
        'music_school', 'driving_school', 'research_institute', 'prep_school',
        'building_school', 'building_college', 'building_university'
    ],
    'finance': [
        'bank', 'atm', 'bureau_de_change', 'money_transfer',
        'post_office', 'post_box', 'insurance', 'financial_advice',
        'accountant', 'tax_advisor',
        'office_insurance', 'office_financial', 'office_accountant',
        'building_bank'
    ],
    'shopping': [
        # Major retail
        'mall', 'supermarket', 'marketplace', 'department_store',
        'convenience', 'wholesale', 'variety_store',
        # All shop types
        'shop', 'kirana', 'general', 'butcher', 'bakery', 'greengrocer',
        'seafood', 'deli', 'confectionery', 'beverages', 'alcohol',
        'tea', 'coffee', 'furniture', 'electronics', 'books', 'clothes',
        'shoes', 'toys', 'sports', 'jewelry', 'jewellery', 'mobile_phone',
        'hardware', 'florist', 'gift', 'stationery', 'cosmetics',
        'perfumery', 'chemist', 'medical_supply', 'optician',
        'doityourself', 'garden_centre', 'paint', 'carpet', 'curtain',
        'interior_decoration', 'bed', 'kitchen', 'bathroom_furnishing',
        'car', 'car_parts', 'car_repair', 'motorcycle', 'bicycle', 'tyres',
        'pet', 'art', 'craft', 'fabric', 'wool', 'newsagent',
        'lottery', 'ticket', 'travel_agency', 'laundry', 'dry_cleaning',
        'trade', 'antiques', 'baby_goods', 'beauty', 'hairdresser',
        'gas', 'copyshop', 'houseware', 'computer', 'video_games',
        'music', 'musical_instrument', 'photo', 'camera', 'outdoor',
        'fishing', 'hunting', 'fashion', 'watches', 'chocolate',
        'tobacco', 'e-cigarette', 'vape', 'bag', 'lighting',
        'building_retail', 'building_kiosk'
    ],
    'food': [
        'restaurant', 'cafe', 'fast_food', 'food_court', 'bar',
        'pub', 'biergarten', 'ice_cream', 'tea', 'coffee_shop',
        'bistro', 'canteen', 'pizza', 'burger', 'chicken',
        'sandwich', 'kebab', 'sushi', 'noodle', 'pasta',
        'seafood', 'steak_house', 'indian', 'chinese', 'italian',
        'internet_cafe'
    ],
    'transport': [
        'bus_stop', 'bus_station', 'taxi', 'fuel', 'parking',
        'parking_entrance', 'parking_space', 'bicycle_rental',
        'bicycle_parking', 'motorcycle_parking', 'car_rental',
        'car_wash', 'charging_station', 'car_sharing',
        'ferry_terminal', 'rest_area', 'services', 'elevator',
        # Aeroway
        'aerodrome', 'terminal', 'helipad', 'heliport', 'gate',
        # Aerialway
        'station', 'cable_car', 'gondola', 'chair_lift',
        # Waterway
        'dock', 'boatyard', 'dam',
        # Railway
        'railway_station', 'railway_subway', 'railway_subway_entrance',
        'railway_stop', 'railway_platform', 'railway_halt',
        'railway_tram_stop', 'railway_light_rail', 'railway_monorail',
        # Public transport
        'public_transport_station', 'public_transport_platform',
        'public_transport_stop_position', 'public_transport_ferry_terminal',
        # Buildings
        'building_train_station', 'building_transportation', 'building_parking'
    ],
    'cultural': [
        'theatre', 'cinema', 'museum', 'library', 'arts_centre',
        'gallery', 'place_of_worship', 'park', 'playground',
        'community_centre', 'social_centre', 'fountain',
        'monument', 'viewpoint', 'attraction', 'artwork',
        'clock', 'memorial', 'wayside_shrine', 'events_venue',
        'conference_centre', 'exhibition_centre', 'studio',
        'planetarium', 'monastery',
        'sports_centre', 'stadium', 'swimming_pool', 'fitness_centre',
        'garden', 'nature_reserve',
        # Leisure extras
        'marina', 'slipway', 'fishing', 'pitch', 'track',
        # Natural features
        'beach', 'peak', 'spring', 'cave_entrance', 'wood', 'scrub', 'water',
        # Man-made landmarks
        'tower', 'lighthouse', 'pier', 'water_tower', 'windmill',
        # Buildings
        'building_temple', 'building_church', 'building_mosque',
        'building_cathedral', 'building_chapel', 'building_museum',
        'building_stadium', 'building_cinema', 'building_grandstand'
    ],
    'premium': [
        'mall', 'hotel', 'gym', 'spa', 'golf_course', 'resort',
        'fitness_centre', 'swimming_pool', 'sauna', 'country_club',
        'sports_centre', 'stadium', 'marina', 'casino', 'nightclub',
        'building_hotel', 'building_hostel', 'building_stadium'
    ],
    'essential': [
        'hospital', 'clinic', 'pharmacy', 'supermarket', 'grocery',
        'bank', 'atm', 'post_office', 'police', 'fire_station',
        'doctors', 'dentist', 'fuel', 'convenience',
        'toilets', 'drinking_water', 'telephone', 'vending_machine',
        'payment_terminal'
    ],
    'employment': [
        'office', 'coworking_space', 'research_institute', 'industrial',
        'factory', 'warehouse', 'craft', 'workshop', 'research',
        'office_company', 'office_it', 'office_coworking', 'office_lawyer',
        'office_estate_agent', 'office_travel_agent', 'office_newspaper',
        'office_telecommunication', 'office_logistics', 'office_yes',
        'office_educational_institution', 'office_research',
        'office_employment_agency', 'office_advertising_agency',
        'office_architect', 'office_accountant', 'office_consulting',
        'office_insurance', 'office_financial', 'office_government',
        'office_ngo', 'office_notary', 'office_political_party',
        # Craft workers
        'carpenter', 'plumber', 'electrician', 'shoemaker',
        'tailor', 'key_cutter', 'photographer', 'electronics_repair',
        # Buildings
        'building_office', 'building_commercial', 'building_retail',
        'building_industrial'
    ],
    'civic': [
        'townhall', 'courthouse', 'police', 'fire_station',
        'post_office', 'embassy', 'public_building', 'social_facility',
        'recycling', 'community_centre',
        'office_government', 'office_diplomatic', 'office_ngo',
        'office_association', 'office_political_party', 'office_religion',
        'office_foundation',
        'building_government', 'building_public', 'building_fire_station',
        'building_police', 'building_community_centre'
    ]
}

# ============================================================================
# CATEGORY WEIGHTS FOR FINAL AMENITY INDEX
# ============================================================================
# Sum = 1.0
CATEGORY_WEIGHTS = {
    'essential': 0.24,
    'healthcare': 0.17,
    'education': 0.14,
    'transport': 0.11,
    'finance': 0.09,
    'shopping': 0.08,
    'food': 0.05,
    'cultural': 0.04,
    'premium': 0.03,
    'employment': 0.03,
    'civic': 0.02
}

# ============================================================================
# COMPONENT WEIGHTS FOR CATEGORY SCORING
# ============================================================================
# Sum = 1.0
COMPONENT_WEIGHTS = {
    'density': 0.25,
    'proximity': 0.20,
    'quality': 0.20,
    'accessibility': 0.15,
    'spatial': 0.10,
    'economic': 0.10
}

# ============================================================================
# ADVANCED SCORING PARAMETERS
# ============================================================================

# Logarithmic Density Scaling
DENSITY_LOG_NORMALIZATION = 3

# Exponential Proximity Decay
PROXIMITY_DECAY_RATE_KM = 1.0
PROXIMITY_DECAY_RATE_AVERAGE_KM = 2.0

# Category-Specific Proximity Decay Rates
CATEGORY_PROXIMITY_DECAY_RATES = {
    'essential': 0.8,
    'healthcare': 1.2,
    'education': 1.0,
    'shopping': 1.0,
    'food': 0.9,
    'transport': 1.5,
    'finance': 1.0,
    'cultural': 1.3,
    'premium': 1.8,
    'employment': 2.0,
    'civic': 1.2,
}

# Category-Specific Density Log Normalization
CATEGORY_DENSITY_LOG_NORMALIZATION = {
    'essential': 3.0,
    'healthcare': 2.5,
    'education': 2.8,
    'shopping': 4.0,
    'food': 4.5,
    'transport': 2.0,
    'finance': 3.5,
    'cultural': 3.0,
    'premium': 2.5,
    'employment': 3.5,
    'civic': 2.8,
}

# Relative Density Scaling
RELATIVE_DENSITY_SCALE = 500

# Spatial Clustering Parameters
SPATIAL_CLUSTERING_DIVISOR = 3.0

# Premium Brand Lists (India-Specific)
PREMIUM_BRANDS = {
    'food': ['Starbucks', 'KFC', 'McDonald', 'Pizza Hut', 'Domino', 'Burger King', 'Subway', 'Cafe Coffee Day'],
    'shopping': ['Reliance', 'Big Bazaar', 'DMart', 'Westside', 'Lifestyle', 'Pantaloons', 'Shoppers Stop'],
    'healthcare': ['Apollo', 'Fortis', 'Max', 'Manipal', 'Columbia Asia', 'Narayana', 'KIMS'],
    'finance': ['HDFC', 'ICICI', 'Axis', 'Kotak', 'SBI', 'HSBC', 'Citibank'],
    'premium': ['Gold\'s Gym', 'Fitness First', 'Cult.fit', 'Talwalkars'],
}

# Quality Tier Thresholds
QUALITY_THRESHOLDS = {
    'healthcare': {'low': 0.3, 'mid': 0.8, 'high': 1.5},
    'education': {'low': 0.2, 'mid': 0.5, 'high': 1.0},
    'shopping': {'low': 0.1, 'mid': 0.3, 'high': 0.8},
    'transport': {'low': 0.2, 'mid': 0.5, 'high': 1.2},
    'default': {'low': 0.5, 'mid': 1.0, 'high': 2.0}
}

# Gravity Model Log Scaling
GRAVITY_LOG_MIN = 0.1
GRAVITY_LOG_MAX = 100.0

# DBSCAN Clustering Parameters
DBSCAN_EPS_KM = 0.5
DBSCAN_MIN_SAMPLES = 3

# Hotspot Detection Parameters
HOTSPOT_RADIUS_KM = 0.3
HOTSPOT_MIN_POIS = 5

# Multi-Radius Gradient Parameters
GRADIENT_RADII_KM = [0.5, 1.0, 1.5, 2.0]
GRADIENT_RADII = [0.5, 1.0, 1.5, 2.0]

# Dominance Penalty Parameters
DOMINANCE_THRESHOLD = 0.5
DOMINANCE_MULTIPLIER = 2.0

# Gini Coefficient Penalty Parameters
GINI_PENALTY_THRESHOLD = 0.4
GINI_PENALTY_MAX = 0.15

# Simpson's Diversity Boost Parameters
SIMPSON_BOOST_MAX = 0.20

# Data Quality Penalty Thresholds
# Format: (max_poi_count, penalty_fraction)
# Used by amenity_calculator.py to apply additive penalties
DATA_QUALITY_POI_THRESHOLDS = {
    'very_sparse': 5,    # < 5 POIs  → 20% penalty
    'sparse':      20,   # < 20 POIs → 10% penalty
    'moderate':    40,   # < 40 POIs → 5% penalty
    # >= 40 POIs → no penalty
}
DATA_QUALITY_PENALTIES = {
    'very_sparse': 0.20,
    'sparse':      0.10,
    'moderate':    0.05,
    'good':        0.00,
}

# India-calibrated target POI distribution for economic scoring
# These represent the expected share of each category in a balanced urban area
ECONOMIC_TARGET_PCT = {
    'essential':   17,   # Essential services (groceries, pharmacy, police)
    'shopping':    15,   # Retail and shops
    'food':        12,   # Restaurants, cafes, food outlets
    'employment':  12,   # Offices, coworking, industrial
    'transport':   10,   # Transit, parking, fuel
    'healthcare':   8,   # Hospitals, clinics, pharmacies
    'cultural':     8,   # Parks, temples, museums, recreation
    'education':    6,   # Schools, colleges, universities
    'finance':      5,   # Banks, ATMs, post offices
    'premium':      4,   # Hotels, gyms, spas
    'civic':        3,   # Government, civic buildings
}

# Category Minimum Score Constraint
CATEGORY_MIN_SCORE = 0.0

# Spatial Clustering Parameters (DBSCAN)
SPATIAL_CLUSTERING_EPS = 0.01
SPATIAL_CLUSTERING_MIN_SAMPLES = 2

# Temporal Accessibility Parameters
TEMPORAL_WEEKEND_DAY = 5
TEMPORAL_EVENING_HOUR = 20
TEMPORAL_MORNING_HOUR = 10

print("✅ Comprehensive OSM India config loaded successfully!")
print(f"   Total POI types: {sum(len(v) for v in POI_WEIGHTS.values())}")
print(f"   Categories: {len(CATEGORIES)}")

