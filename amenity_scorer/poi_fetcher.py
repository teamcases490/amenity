"""
poi_fetcher.py — Fetch POI data from OpenStreetMap via the Overpass API.

Features:
  - Disk-based JSON cache (configurable TTL)
  - Exponential-backoff retry on transient errors
  - Rate limiting (respects Overpass fair-use policy)
  - Comprehensive OSM tag coverage for Indian cities
"""

import json
import logging
import random
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import requests

import config
from utils import RateLimiter, cache_key, haversine_km

logger = logging.getLogger(__name__)


class POIFetcher:
    """
    Fetch and cache Points of Interest from the Overpass API.

    Usage:
        fetcher = POIFetcher(logger)
        pois = fetcher.fetch(lat=19.076, lon=72.877, max_radius_km=2.0)
    """

    OVERPASS_ENDPOINTS = [
        "https://overpass-api.de/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter",
        "https://z.overpass-api.de/api/interpreter",
    ]

    def __init__(self, logger_instance: Optional[logging.Logger] = None):
        self.logger = logger_instance or logger
        self.cache_dir = Path(config.CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = timedelta(days=config.CACHE_TTL_DAYS)
        self.rate_limiter = RateLimiter(requests_per_second=config.REQUESTS_PER_SECOND)
        self._endpoint_idx = 0
        self._endpoint_lock = threading.Lock()

    def fetch(
        self,
        lat: float,
        lon: float,
        max_radius_km: float = 2.0,
        force_refresh: bool = False,
    ) -> List[Dict]:
        """
        Return all POIs within `max_radius_km` of (lat, lon).

        Checks disk cache first; falls back to Overpass API on miss.
        Each POI dict contains at minimum: poi_type, lat, lon, distance_km.
        """
        key = cache_key(lat, lon, max_radius_km)

        # Check cache if not forcing refresh
        if not force_refresh:
            cached = self._load_cache(key)
            if cached is not None:
                self.logger.debug(f"Cache hit for ({lat:.4f}, {lon:.4f})")
                return cached

        # Fetch from API
        pois = self._fetch_from_api(lat, lon, max_radius_km)

        self._save_cache(key, pois, ttl_days=7 if not pois else self.cache_ttl.days)

        return pois

    def _load_cache(self, key: str) -> Optional[List[Dict]]:
        path = self.cache_dir / f"{key}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(data["cached_at"])
            # Respect per-entry TTL (empty results use 7 days, normal use 30 days)
            ttl = timedelta(days=data.get("ttl_days", self.cache_ttl.days))
            if datetime.now() - cached_at > ttl:
                path.unlink(missing_ok=True)
                return None
            return data["pois"]
        except Exception:
            return None

    def _save_cache(self, key: str, pois: List[Dict], ttl_days: int = None) -> None:
        path = self.cache_dir / f"{key}.json"
        if ttl_days is None:
            ttl_days = self.cache_ttl.days
        try:
            path.write_text(
                json.dumps(
                    {
                        "cached_at": datetime.now().isoformat(),
                        "pois": pois,
                        "ttl_days": ttl_days,
                    }
                ),
                encoding="utf-8",
            )
        except Exception as exc:
            self.logger.warning(f"Cache write failed: {exc}")

    def _fetch_from_api(self, lat: float, lon: float, radius_km: float) -> List[Dict]:
        """Query Overpass API with exponential-backoff retry."""
        radius_m = int(radius_km * 1000)
        query = self._build_comprehensive_query(lat, lon, radius_m)

        for attempt in range(config.API_MAX_RETRIES):
            with self._endpoint_lock:
                endpoint = self.OVERPASS_ENDPOINTS[
                    self._endpoint_idx % len(self.OVERPASS_ENDPOINTS)
                ]
            try:
                self.rate_limiter.wait()
                resp = requests.post(
                    endpoint,
                    data={"data": query},
                    timeout=config.API_TIMEOUT,
                    headers={"User-Agent": "amenity-scorer/2.1 (research)"},
                )

                if resp.status_code == 429:
                    # Short jittered wait — the parallel workers already stagger
                    # via the RateLimiter, so a long wait here serializes them badly.
                    wait = 15 + (attempt * 5) + random.uniform(0, 5)
                    self.logger.warning(
                        f"Rate limited (429) on {endpoint}. "
                        f"Rotating endpoint and waiting {wait:.1f}s... (Attempt {attempt+1})"
                    )
                    with self._endpoint_lock:
                        self._endpoint_idx += 1
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                try:
                    data = resp.json()
                except Exception:
                    # Sometimes Overpass returns 200 OK but with an HTML error or empty body
                    raise requests.exceptions.Timeout(
                        f"Malformed JSON response from {endpoint}. Possibly internal Overpass timeout or gateway issue."
                    )

                if "remark" in data:
                    remark = data["remark"]
                    if "timeout" in remark.lower() or "runtime error" in remark.lower():
                        raise requests.exceptions.Timeout(f"Overpass remark: {remark}")
                    self.logger.warning(f"Overpass API remark: {remark}")

                elements = data.get("elements", [])
                pois = self._parse_elements(elements, lat, lon)

                if not pois:
                    self.logger.info(
                        f"Fetched 0 POIs at ({lat:.4f}, {lon:.4f}). This may be valid for rural areas."
                    )
                else:
                    self.logger.info(
                        f"Fetched {len(pois)} POIs at ({lat:.4f}, {lon:.4f})"
                    )

                return pois

            except (
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
            ) as exc:
                wait = (2**attempt) + random.uniform(1, 3)
                self.logger.warning(
                    f"Connection/Timeout error: {exc}. Retry {attempt+1}/{config.API_MAX_RETRIES} in {wait:.1f}s"
                )
                with self._endpoint_lock:
                    self._endpoint_idx += 1
                time.sleep(wait)

            except requests.exceptions.HTTPError as exc:
                code = exc.response.status_code
                if code in [500, 502, 503, 504]:
                    wait = (2**attempt) * 2 + random.uniform(1, 3)
                    self.logger.warning(
                        f"HTTP {code} (attempt {attempt+1}/{config.API_MAX_RETRIES}), waiting {wait:.1f}s"
                    )
                    time.sleep(wait)
                else:
                    # 403, 400, etc. — this endpoint is refusing us; rotate and retry
                    self.logger.warning(f"HTTP {code} from {endpoint}: rotating endpoint")
                    with self._endpoint_lock:
                        self._endpoint_idx += 1
                    time.sleep(2 + random.uniform(0, 2))

            except Exception as exc:
                self.logger.error(f"Unexpected error: {exc}", exc_info=True)
                break

        self.logger.error(f"All retries exhausted for ({lat:.4f}, {lon:.4f})")
        return []

    def _build_comprehensive_query(
        self, lat: float, lon: float, radius_m: float
    ) -> str:
        """
        Build Overpass query with ALL OSM tag types + India-specific tags.
        """
        query = f"""
        [out:json][timeout:120];
        (
          /* Primary Amenities */
          node["amenity"](around:{radius_m},{lat},{lon});
          way["amenity"](around:{radius_m},{lat},{lon});
          
          /* Retail & Commercial */
          node["shop"](around:{radius_m},{lat},{lon});
          way["shop"](around:{radius_m},{lat},{lon});
          node["office"](around:{radius_m},{lat},{lon});
          way["office"](around:{radius_m},{lat},{lon});
          node["craft"](around:{radius_m},{lat},{lon});
          way["craft"](around:{radius_m},{lat},{lon});
          
          /* Specialized & Services */
          node["healthcare"](around:{radius_m},{lat},{lon});
          way["healthcare"](around:{radius_m},{lat},{lon});
          node["leisure"](around:{radius_m},{lat},{lon});
          way["leisure"](around:{radius_m},{lat},{lon});
          node["tourism"](around:{radius_m},{lat},{lon});
          way["tourism"](around:{radius_m},{lat},{lon});
          node["sport"](around:{radius_m},{lat},{lon});
          way["sport"](around:{radius_m},{lat},{lon});
          node["emergency"](around:{radius_m},{lat},{lon});
          way["emergency"](around:{radius_m},{lat},{lon});
          
          /* Transport */
          node["public_transport"](around:{radius_m},{lat},{lon});
          way["public_transport"](around:{radius_m},{lat},{lon});
          node["railway"~"^(station|halt|subway|light_rail|monorail)$"](around:{radius_m},{lat},{lon});
          way["railway"~"^(station|halt|subway|light_rail|monorail)$"](around:{radius_m},{lat},{lon});
          node["aeroway"](around:{radius_m},{lat},{lon});
          way["aeroway"](around:{radius_m},{lat},{lon});
          
          /* India Specifics */
          node["amenity"~"^(coaching|training|place_of_worship|taxi|fuel)$"](around:{radius_m},{lat},{lon});
          way["amenity"~"^(coaching|training|place_of_worship|taxi|fuel)$"](around:{radius_m},{lat},{lon});
          node["shop"~"^(kirana|general|convenience|medical|chemist|beauty|hairdresser)$"](around:{radius_m},{lat},{lon});
          way["shop"~"^(kirana|general|convenience|medical|chemist|beauty|hairdresser)$"](around:{radius_m},{lat},{lon});
          
          /* Buildings (only if tagged with relevant usage) */
          node["building"~"^(commercial|office|retail|hospital|school|college|university|government|public|train_station|hotel|stadium|temple|church|mosque|industrial)$"](around:{radius_m},{lat},{lon});
          way["building"~"^(commercial|office|retail|hospital|school|college|university|government|public|train_station|hotel|stadium|temple|church|mosque|industrial)$"](around:{radius_m},{lat},{lon});
        );
        out center tags;
        """
        return query

    def _parse_elements(
        self, elements: List[Dict], origin_lat: float, origin_lon: float
    ) -> List[Dict]:
        """Convert raw Overpass elements to normalised POI dicts (deduplicated by ID)."""
        pois = []
        seen_ids = set()

        for el in elements:
            el_id = el.get("id")
            if el_id in seen_ids:
                continue
            seen_ids.add(el_id)

            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            if lat is None or lon is None:
                continue

            tags = el.get("tags", {})
            poi_type = self._resolve_poi_type(tags)
            if not poi_type:
                continue

            dist = haversine_km(origin_lat, origin_lon, lat, lon)
            pois.append(
                {
                    "id": el_id,
                    "poi_type": poi_type,
                    "lat": lat,
                    "lon": lon,
                    "distance_km": dist,
                    "name": tags.get("name", ""),
                    "brand": tags.get("brand", ""),
                    "operator": tags.get("operator", ""),
                    "opening_hours": tags.get("opening_hours", ""),
                    "tags": tags,
                }
            )
        return pois

    def _resolve_poi_type(self, tags: Dict) -> str:
        """
        Extract the most specific POI type from OSM tags.

        Priority: amenity > shop > healthcare > leisure > tourism > sport >
                  craft > emergency > aeroway > aerialway > waterway >
                  natural > man_made > public_transport > highway > office >
                  railway > building

        Tag collision note: 'amenity=station' (bus/train station tagged under
        amenity) is returned as 'amenity_station' to avoid collision with
        'station' (aerialway=station — cable-car station) which carries weight
        3.0 in the transport POI_WEIGHTS.
        """
        # Primary tag keys
        primary_keys = [
            "amenity",
            "shop",
            "healthcare",
            "leisure",
            "tourism",
            "sport",
            "craft",
            "emergency",
            "aeroway",
            "aerialway",
            "waterway",
            "natural",
            "man_made",
        ]
        for key in primary_keys:
            val = tags.get(key)
            if val:
                # Resolve the 'amenity=station' vs 'aerialway=station' collision.
                # Both produce the raw string 'station'; prefix amenity variant
                # so it doesn't accidentally inherit the aerialway weight (3.0).
                if key == "amenity" and val == "station":
                    return "amenity_station"
                return val

        # Public Transport
        if tags.get("public_transport"):
            return f"public_transport_{tags['public_transport']}"

        # Highway tags (specific amenity-like infrastructure)
        if tags.get("highway") in {
            "bus_stop",
            "platform",
            "rest_area",
            "services",
            "elevator",
        }:
            return tags["highway"]

        if tags.get("office"):
            return f"office_{tags['office']}"

        if tags.get("railway"):
            return f"railway_{tags['railway']}"

        if tags.get("building") and tags["building"] != "yes":
            return f"building_{tags['building']}"

        return ""
