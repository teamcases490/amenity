"""
poi_polygon_fetcher.py — Fetch all POIs inside a pincode polygon bounding box
                          with a buffer. Uses ONE Overpass API call per pincode,
                          then filters results spatially.

This is a copy-and-extend of amenity_scorer/poi_fetcher.py adapted for
polygon-based queries. The amenity_scorer package is NOT modified.
"""

import json
import logging
import random
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys
import os

import requests

# Add amenity_scorer to path for config and utils
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'amenity_scorer'))
import config
from utils import RateLimiter

logger = logging.getLogger(__name__)


class PolygonPOIFetcher:
    """
    Fetch POIs for an entire pincode polygon in a single Overpass query.

    Unlike the centroid-based fetcher, this:
      - Computes a bounding box from the polygon
      - Adds a configurable buffer (default 500m)
      - Queries all POIs in that bbox in ONE call
      - Returns raw POI list with (lat, lon, poi_type, tags)

    The feature extractor then computes distances from each sample point locally.
    """

    OVERPASS_ENDPOINTS = [
        "https://overpass-api.de/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]

    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir or config.CACHE_DIR) / "polygon"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = timedelta(days=config.CACHE_TTL_DAYS)
        self.rate_limiter = RateLimiter(requests_per_second=config.REQUESTS_PER_SECOND)
        self._endpoint_idx = 0
        self._endpoint_lock = threading.Lock()  # protect shared counter

    def fetch_for_bbox(
        self,
        min_lat: float, min_lon: float,
        max_lat: float, max_lon: float,
        pincode: str,
        buffer_km: float = 0.5,
        force_refresh: bool = False,
    ) -> List[Dict]:
        """
        Fetch all POIs in the bounding box (with buffer) for a pincode polygon.
        Results are cached per pincode.

        Returns flat list of POI dicts with keys:
          poi_type, lat, lon, tags, distance_km (set to 0 — calculated later per sample point)
        """
        cache_key = f"poly_{pincode}"
        if not force_refresh:
            cached = self._load_cache(cache_key)
            if cached is not None:
                logger.debug("Polygon cache hit for pincode %s", pincode)
                return cached

        # Apply buffer in degrees (~0.009 deg per km at India latitudes)
        buf_deg = buffer_km / 111.0
        q_min_lat = min_lat - buf_deg
        q_max_lat = max_lat + buf_deg
        q_min_lon = min_lon - buf_deg
        q_max_lon = max_lon + buf_deg

        pois = self._fetch_bbox(q_min_lat, q_min_lon, q_max_lat, q_max_lon)
        self._save_cache(cache_key, pois, ttl_days=7 if not pois else self.cache_ttl.days)
        return pois

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _load_cache(self, key: str) -> Optional[List[Dict]]:
        path = self.cache_dir / f"{key}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(data["cached_at"])
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
                json.dumps({"cached_at": datetime.now().isoformat(),
                            "pois": pois, "ttl_days": ttl_days}),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Polygon cache write failed: %s", exc)

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def _fetch_bbox(
        self,
        min_lat: float, min_lon: float,
        max_lat: float, max_lon: float,
    ) -> List[Dict]:
        """Query Overpass API for a bounding box with exponential-backoff retry."""
        query = self._build_bbox_query(min_lat, min_lon, max_lat, max_lon)

        for attempt in range(config.API_MAX_RETRIES):
            with self._endpoint_lock:
                endpoint = self.OVERPASS_ENDPOINTS[self._endpoint_idx % len(self.OVERPASS_ENDPOINTS)]
            try:
                self.rate_limiter.wait()
                resp = requests.post(
                    endpoint,
                    data={"data": query},
                    timeout=config.API_TIMEOUT,
                    headers={"User-Agent": "amenity-scorer-polygon/2.2 (research)"},
                )

                if resp.status_code == 429:
                    wait = 60 + (attempt * 15) + random.uniform(0, 5)
                    logger.warning("Rate limited (429) on %s. Rotating and waiting %.1fs (attempt %d)",
                                   endpoint, wait, attempt + 1)
                    with self._endpoint_lock:
                        self._endpoint_idx += 1
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                try:
                    data = resp.json()
                except Exception:
                    raise requests.exceptions.Timeout(
                        f"Malformed JSON from {endpoint} (possibly HTML error page)")

                if "remark" in data:
                    remark = data["remark"]
                    if "timeout" in remark.lower() or "runtime error" in remark.lower():
                        raise requests.exceptions.Timeout(f"Overpass remark: {remark}")

                elements = data.get("elements", [])
                pois = self._parse_elements(elements)
                logger.info("Fetched %d POIs from bbox query", len(pois))
                return pois

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                wait = (2 ** attempt) + random.uniform(1, 3)
                logger.warning("Timeout/Connection error: %s. Retry %d/%d in %.1fs",
                               exc, attempt + 1, config.API_MAX_RETRIES, wait)
                with self._endpoint_lock:
                    self._endpoint_idx += 1
                time.sleep(wait)

            except requests.exceptions.HTTPError as exc:
                code = exc.response.status_code
                if code in [500, 502, 503, 504]:
                    wait = (2 ** attempt) * 2 + random.uniform(1, 3)
                    logger.warning("HTTP %d (attempt %d/%d), waiting %.1fs",
                                   code, attempt + 1, config.API_MAX_RETRIES, wait)
                    time.sleep(wait)
                else:
                    logger.error("HTTP %d fatal: %s", code, exc)
                    break

            except Exception as exc:
                logger.error("Unexpected error: %s", exc, exc_info=True)
                break

        logger.error("All retries exhausted for bbox query")
        return []

    def _build_bbox_query(
        self,
        min_lat: float, min_lon: float,
        max_lat: float, max_lon: float,
    ) -> str:
        """Build an Overpass QL bbox query covering all relevant OSM tags."""
        bbox = f"{min_lat},{min_lon},{max_lat},{max_lon}"
        return f"""
        [out:json][timeout:120];
        (
          node["amenity"]({bbox});
          way["amenity"]({bbox});
          node["shop"]({bbox});
          way["shop"]({bbox});
          node["office"]({bbox});
          way["office"]({bbox});
          node["healthcare"]({bbox});
          way["healthcare"]({bbox});
          node["leisure"]({bbox});
          way["leisure"]({bbox});
          node["tourism"]({bbox});
          way["tourism"]({bbox});
          node["public_transport"]({bbox});
          node["railway"~"^(station|halt|subway|light_rail)$"]({bbox});
          node["craft"]({bbox});
          node["emergency"]({bbox});
          node["sport"]({bbox});
          node["building"~"^(commercial|office|retail|hospital|school|college|university|government|public|train_station|hotel|stadium|temple|church|mosque)$"]({bbox});
          node["shop"~"^(kirana|general|convenience|medical|chemist|beauty|hairdresser)$"]({bbox});
        );
        out center tags;
        """

    def _parse_elements(self, elements: List[Dict]) -> List[Dict]:
        """Convert raw Overpass elements to normalised POI dicts."""
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

            pois.append({
                "poi_type":      poi_type,
                "lat":           float(lat),
                "lon":           float(lon),
                "tags":          tags,
                # distance_km will be computed per sample point later
                "distance_km":   0.0,
                # Top-level fields required by FeatureExtractor (brand, temporal features)
                "name":          tags.get("name", ""),
                "brand":         tags.get("brand", ""),
                "operator":      tags.get("operator", ""),
                "opening_hours": tags.get("opening_hours", ""),
            })

        return pois

    def _resolve_poi_type(self, tags: Dict) -> Optional[str]:
        """
        Map OSM tags to a poi_type string matching config.CATEGORIES keys.
        Priority order: amenity > shop > office > healthcare > leisure > etc.
        """
        priority = ["amenity", "shop", "healthcare", "leisure", "tourism",
                    "public_transport", "railway", "office", "sport",
                    "emergency", "craft", "building"]
        for key in priority:
            val = tags.get(key)
            if val:
                # Namespace building tags to avoid conflict
                if key == "building":
                    return f"building_{val}"
                if key == "office":
                    return f"office_{val}"
                return val
        return None
