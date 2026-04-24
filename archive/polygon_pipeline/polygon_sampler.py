"""
polygon_sampler.py — Load pincode polygons from GeoJSON and generate
                     representative sample points inside each polygon.

Supports both Polygon and MultiPolygon geometry types.
Uses a grid-based Poisson disk-like approach for even spatial coverage.
"""

import json
import math
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_geojson(path: str) -> Dict[str, dict]:
    """
    Load GeoJSON and return a dict: {pincode_str: feature_dict}.
    Uses the 'Pincode' property as the key.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    index: Dict[str, dict] = {}
    for feat in data["features"]:
        pincode = str(feat["properties"].get("Pincode", "")).strip()
        if pincode:
            index[pincode] = feat
    return index


def get_polygon_bbox(geometry: dict) -> Tuple[float, float, float, float]:
    """Return (min_lon, min_lat, max_lon, max_lat) for a geometry."""
    coords = _all_coords(geometry)
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return min(lons), min(lats), max(lons), max(lats)


def sample_points_in_polygon(geometry: dict, n_points: int = 12) -> List[Tuple[float, float]]:
    """
    Generate up to n_points (lat, lon) sample points inside the polygon.

    Strategy:
      1. Get bounding box
      2. Create a dense candidate grid
      3. Keep only candidates that fall inside the polygon
      4. If fewer than n_points pass, use the centroid + any valid points
      5. Shuffle and return up to n_points

    Returns list of (lat, lon) tuples.
    """
    bbox = get_polygon_bbox(geometry)
    min_lon, min_lat, max_lon, max_lat = bbox

    # Build a grid of candidate points (~5x the needed count for rejection)
    candidates = _grid_candidates(min_lon, min_lat, max_lon, max_lat, n_points * 6)

    inside = [pt for pt in candidates if _point_in_geometry(pt[0], pt[1], geometry)]

    if len(inside) < 3:
        # Fallback: use centroid (always valid structurally even if sparse)
        cx, cy = _centroid_of_geometry(geometry)
        inside = [(cx, cy)]

    random.shuffle(inside)
    result = inside[:n_points]

    # Return as (lat, lon)
    return [(pt[1], pt[0]) for pt in result]


def centroid_of_geometry(geometry: dict) -> Tuple[float, float]:
    """Return (lat, lon) centroid of a geometry."""
    cx, cy = _centroid_of_geometry(geometry)
    return (cy, cx)  # (lat, lon)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _grid_candidates(
    min_lon: float, min_lat: float,
    max_lon: float, max_lat: float,
    target_n: int,
) -> List[Tuple[float, float]]:
    """Generate a regular grid of (lon, lat) points in the bbox."""
    span_lon = max_lon - min_lon
    span_lat = max_lat - min_lat
    if span_lon == 0 or span_lat == 0:
        return [(min_lon, min_lat)]

    n_side = max(2, math.ceil(math.sqrt(target_n)))
    step_lon = span_lon / n_side
    step_lat = span_lat / n_side

    pts = []
    for i in range(n_side):
        for j in range(n_side):
            lon = min_lon + (i + 0.5) * step_lon
            lat = min_lat + (j + 0.5) * step_lat
            pts.append((lon, lat))
    return pts


def _all_coords(geometry: dict) -> List[List[float]]:
    """Flatten all coordinate pairs from any geometry type."""
    gtype = geometry["type"]
    coords = geometry["coordinates"]
    if gtype == "Polygon":
        return [pt for ring in coords for pt in ring]
    elif gtype == "MultiPolygon":
        return [pt for poly in coords for ring in poly for pt in ring]
    return []


def _centroid_of_geometry(geometry: dict) -> Tuple[float, float]:
    """Return (lon, lat) centroid of the geometry's bounding box."""
    min_lon, min_lat, max_lon, max_lat = get_polygon_bbox(geometry)
    return ((min_lon + max_lon) / 2, (min_lat + max_lat) / 2)


def _point_in_polygon(lon: float, lat: float, ring: List[List[float]]) -> bool:
    """Ray-casting algorithm for point-in-polygon test."""
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _point_in_geometry(lon: float, lat: float, geometry: dict) -> bool:
    """Test if a (lon, lat) point lies inside a Polygon or MultiPolygon."""
    gtype = geometry["type"]
    coords = geometry["coordinates"]

    if gtype == "Polygon":
        # Must be inside outer ring and outside all hole rings
        if not _point_in_polygon(lon, lat, coords[0]):
            return False
        for hole in coords[1:]:
            if _point_in_polygon(lon, lat, hole):
                return False
        return True

    elif gtype == "MultiPolygon":
        for polygon in coords:
            if _point_in_polygon(lon, lat, polygon[0]):
                in_hole = any(_point_in_polygon(lon, lat, h) for h in polygon[1:])
                if not in_hole:
                    return True
        return False

    return False
