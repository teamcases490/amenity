"""
run_polygon_batch.py — Phase 2 polygon-based amenity scoring pipeline.
                       ISOLATION: does NOT modify any file in amenity_scorer/.

Usage (run from amenity_v2/ root):
    python polygon_pipeline/run_polygon_batch.py                     # full run / auto-resume
    python polygon_pipeline/run_polygon_batch.py --limit 20          # test first 20 pincodes
    python polygon_pipeline/run_polygon_batch.py --workers 4         # parallel threads
    python polygon_pipeline/run_polygon_batch.py --points 16         # 16 sample points per polygon
    python polygon_pipeline/run_polygon_batch.py --filter-csv data/matched_50k_pincode_centroids.csv

Outputs (results/ dir, written live — resume-safe):
    results/polygon_scores.csv    — fixed-column summary (one row per pincode)
    results/polygon_scores.jsonl  — deep JSON-lines per pincode
    results/polygon_scores.json   — full pretty-printed array (written at end)

Resume:
    Already-processed pincodes are identified from the CSV 'pincode' column.
    Safe to Ctrl+C and re-run at any time — no data is duplicated or lost.
"""

import argparse
import json
import logging
import os
import sys
import time
import threading
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
from tqdm import tqdm

# ── path setup ───────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT / "amenity_scorer"))
sys.path.insert(0, str(_HERE))         # polygon_pipeline modules

import config
from utils import setup_logging
from category_scorer import CategoryScorer
from amenity_calculator import AmenityCalculator

from polygon_sampler import load_geojson, sample_points_in_polygon, get_polygon_bbox, centroid_of_geometry
from poi_polygon_fetcher import PolygonPOIFetcher
from local_feature_computer import compute_features_for_point, aggregate_point_features, _attach_distances

# ── logging ──────────────────────────────────────────────────────────────────
logger = setup_logging("polygon_pipeline")

# ── fixed output schema ───────────────────────────────────────────────────────
_BASE_COLS = [
    "pincode", "office_name", "circle",
    "centroid_lat", "centroid_lon",
    "n_sample_points", "n_pois_in_bbox",
    "amenity_index", "classification", "data_quality",
    "total_pois_used", "processing_time_s",
]
_CAT_COLS  = [f"{c}_score" for c in config.CATEGORY_WEIGHTS]
_ALL_COLS  = _BASE_COLS + _CAT_COLS

# ── thread-safe locks ─────────────────────────────────────────────────────────
_write_lock    = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# Per-pincode processing
# ─────────────────────────────────────────────────────────────────────────────

def process_pincode(
    task: Dict,
    fetcher: PolygonPOIFetcher,
    scorer: CategoryScorer,
    calculator: AmenityCalculator,
    n_points: int,
) -> Dict:
    """
    Full Phase 2 pipeline for one pincode:
      1. Compute bbox from the polygon geometry
      2. ONE Overpass query for all POIs inside the buffered bbox (cached)
      3. Sample n_points grid points inside the polygon using ray-casting
      4. For each point: filter POIs ≤ 2km, compute features (pure numpy math)
      5. Aggregate feature dicts across all sample points (mean/max/std)
      6. Pick the richest sample point's POI list as representative for the scorer
      7. Score and calculate amenity index
    """
    pincode  = task["pincode"]
    geometry = task["geometry"]
    props    = task["properties"]

    start = time.time()

    # ── 1. Polygon bbox ───────────────────────────────────────────────────────
    try:
        min_lon, min_lat, max_lon, max_lat = get_polygon_bbox(geometry)
        centroid_lat, centroid_lon = centroid_of_geometry(geometry)
    except Exception as exc:
        logger.error("Bbox/centroid failed for %s: %s", pincode, exc)
        return _error_result(pincode, props, 0.0, 0.0, n_points)

    # ── 2. Fetch POIs (one API call, cached) ─────────────────────────────────
    try:
        all_pois = fetcher.fetch_for_bbox(
            min_lat, min_lon, max_lat, max_lon,
            pincode=pincode,
            buffer_km=0.5,
        )
    except Exception as exc:
        logger.error("POI fetch failed for %s: %s", pincode, exc)
        all_pois = []

    # ── 3. Sample points inside polygon ─────────────────────────────────────
    try:
        sample_pts = sample_points_in_polygon(geometry, n_points=n_points)
    except Exception as exc:
        logger.warning("Sampling failed for %s (%s), using centroid.", pincode, exc)
        sample_pts = []

    if not sample_pts:
        sample_pts = [(centroid_lat, centroid_lon)]

    # ── 4 & 5. Compute features per point, aggregate ─────────────────────────
    per_point_feats: List[Dict] = []
    per_point_pois:  List[List] = []

    for (slat, slon) in sample_pts:
        try:
            relevant = _attach_distances(slat, slon, all_pois, max_radius_km=2.0)
            feats    = compute_features_for_point(slat, slon, all_pois, max_radius_km=2.0)
        except Exception as exc:
            logger.warning("Feature compute failed at (%.4f, %.4f) for %s: %s",
                           slat, slon, pincode, exc)
            relevant = []
            feats    = {"latitude": slat, "longitude": slon, "total_pois": 0}
        per_point_feats.append(feats)
        per_point_pois.append(relevant)

    agg_features = aggregate_point_features(per_point_feats)

    # ── 6. Representative POI list = richest sample point ───────────────────
    best_idx = max(range(len(per_point_pois)), key=lambda i: len(per_point_pois[i]))
    representative_pois = per_point_pois[best_idx]
    total_pois_used     = len(representative_pois)

    # ── 7. Score ─────────────────────────────────────────────────────────────
    try:
        cat_scores = {
            cat: scorer.score(cat, agg_features, representative_pois)
            for cat in config.CATEGORY_WEIGHTS
        }
    except Exception as exc:
        logger.error("Scoring failed for %s: %s", pincode, exc)
        cat_scores = {cat: {"score": 0.0, "components": {}} for cat in config.CATEGORY_WEIGHTS}

    try:
        index = calculator.calculate(cat_scores, total_pois=total_pois_used, features=agg_features)
    except Exception as exc:
        logger.error("Index calc failed for %s: %s", pincode, exc)
        index = {"amenity_index": 0.0, "classification": "Error",
                 "data_quality": "Error", "penalties": {}, "weighted_score": 0.0}

    elapsed = round(time.time() - start, 2)

    # ── Build outputs ─────────────────────────────────────────────────────────
    csv_row = {
        "pincode":            pincode,
        "office_name":        str(props.get("Office_Name", "")),
        "circle":             str(props.get("Circle", "")),
        "centroid_lat":       round(centroid_lat, 6),
        "centroid_lon":       round(centroid_lon, 6),
        "n_sample_points":    len(sample_pts),
        "n_pois_in_bbox":     len(all_pois),
        "amenity_index":      index.get("amenity_index", 0.0),
        "classification":     index.get("classification", "Unknown"),
        "data_quality":       index.get("data_quality", ""),
        "total_pois_used":    total_pois_used,
        "processing_time_s":  elapsed,
    }
    for cat in config.CATEGORY_WEIGHTS:
        csv_row[f"{cat}_score"] = round(cat_scores.get(cat, {}).get("score", 0.0), 4)

    jsonl_record = {
        "pincode":              pincode,
        "office_name":          str(props.get("Office_Name", "")),
        "circle":               str(props.get("Circle", "")),
        "centroid":             {"lat": centroid_lat, "lon": centroid_lon},
        "bbox":                 {"min_lat": min_lat, "min_lon": min_lon,
                                 "max_lat": max_lat, "max_lon": max_lon},
        "n_sample_points":      len(sample_pts),
        "sample_points":        [{"lat": p[0], "lon": p[1]} for p in sample_pts],
        "n_pois_in_bbox":       len(all_pois),
        "total_pois_used":      total_pois_used,
        "amenity_index":        index,
        "category_scores":      cat_scores,
        "aggregated_features":  {k: round(float(v), 6) for k, v in agg_features.items()
                                  if isinstance(v, (int, float))},
        "processing_time_s":    elapsed,
    }

    tqdm.write(
        f"  {pincode:<10} | Score: {index.get('amenity_index', 0):5.1f}"
        f" | {index.get('classification', '?'):<8}"
        f" | bbox POIs: {len(all_pois):4d}"
        f" | used: {total_pois_used:4d}"
        f" | pts: {len(sample_pts):2d}"
        f" | {elapsed:.1f}s"
    )

    return {"success": True, "pincode": pincode, "csv_row": csv_row, "jsonl_record": jsonl_record}


def _error_result(pincode: str, props: dict, lat: float, lon: float, n_points: int) -> Dict:
    """Return a minimal failed result so the worker does not crash the pool."""
    csv_row = {"pincode": pincode, "office_name": str(props.get("Office_Name", "")),
               "circle": str(props.get("Circle", "")),
               "centroid_lat": lat, "centroid_lon": lon, "n_sample_points": 0,
               "n_pois_in_bbox": 0, "amenity_index": 0.0, "classification": "Error",
               "data_quality": "Error", "total_pois_used": 0, "processing_time_s": 0.0}
    for cat in config.CATEGORY_WEIGHTS:
        csv_row[f"{cat}_score"] = 0.0
    return {"success": True, "pincode": pincode, "csv_row": csv_row,
            "jsonl_record": {**csv_row, "error": True}}


# ─────────────────────────────────────────────────────────────────────────────
# Resume helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_processed_pincodes(csv_path: Path) -> Set[str]:
    """
    Load the set of already-processed pincodes from the output CSV.

    Robust to:
      - Empty or truncated files
      - Rows where pincode is NaN or float (e.g. '110001.0')
      - Partial writes from a previous interrupted run
    """
    if not csv_path.exists():
        return set()
    try:
        df = pd.read_csv(csv_path, usecols=["pincode"], dtype=str,
                         on_bad_lines="skip")
        pincodes = set()
        for raw in df["pincode"].dropna().tolist():
            raw = raw.strip()
            if raw and raw.lower() not in ("nan", "pincode"):
                try:
                    pincodes.add(str(int(float(raw))))
                except ValueError:
                    pincodes.add(raw)
        return pincodes
    except Exception as exc:
        logger.error("Could not read existing CSV for resume (will restart): %s", exc)
        return set()


def _ensure_csv_header(csv_path: Path) -> None:
    """Write CSV header only if the file does not yet exist or is empty."""
    if csv_path.exists() and csv_path.stat().st_size > 0:
        return
    pd.DataFrame(columns=_ALL_COLS).to_csv(csv_path, index=False)


# ─────────────────────────────────────────────────────────────────────────────
# Batch runner
# ─────────────────────────────────────────────────────────────────────────────

def run_batch(
    geojson_path: str,
    output_stem: str,
    n_points: int = 16,
    limit: Optional[int] = None,
    n_workers: int = 4,
    filter_pincodes: Optional[Set[str]] = None,
) -> None:
    csv_path   = Path(output_stem + ".csv")
    jsonl_path = Path(output_stem + ".jsonl")
    json_path  = Path(output_stem + ".json")

    csv_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Load GeoJSON ──────────────────────────────────────────────────────────
    logger.warning("Loading GeoJSON from %s ...", geojson_path)
    geojson_index = load_geojson(geojson_path)
    logger.warning("Loaded %d pincode polygons.", len(geojson_index))

    # ── Build task list ───────────────────────────────────────────────────────
    all_tasks: List[Dict] = []
    for pc, feat in geojson_index.items():
        if filter_pincodes is None or pc in filter_pincodes:
            all_tasks.append({
                "pincode":    pc,
                "geometry":   feat["geometry"],
                "properties": feat["properties"],
            })

    if filter_pincodes is not None:
        logger.warning("Filtered to %d pincodes from input CSV.", len(all_tasks))

    if limit:
        all_tasks = all_tasks[:limit]

    total = len(all_tasks)

    # ── Resume ────────────────────────────────────────────────────────────────
    processed = _load_processed_pincodes(csv_path)
    pending   = [t for t in all_tasks if t["pincode"] not in processed]

    logger.warning(
        "Resume check: %d total | %d already done | %d remaining | %d workers | %d pts",
        total, len(processed), len(pending), n_workers, n_points,
    )

    if not pending:
        logger.warning("All pincodes already processed. Nothing to do.")
        return

    # ── Ensure header ─────────────────────────────────────────────────────────
    _ensure_csv_header(csv_path)

    # ── Shared objects (instantiated once, reused across threads) ────────────
    fetcher    = PolygonPOIFetcher()
    scorer     = CategoryScorer()
    calculator = AmenityCalculator()

    completed_this_session: List[Dict] = []

    def _worker(task: Dict) -> Dict:
        time.sleep(random.uniform(0.1, 1.5))    # stagger to avoid burst
        return process_pincode(task, fetcher, scorer, calculator, n_points)

    # ── Main loop ─────────────────────────────────────────────────────────────
    with tqdm(total=total, desc="Polygon Scoring", unit="pc",
              dynamic_ncols=True) as pbar:
        pbar.update(len(processed))

        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            futures = {pool.submit(_worker, t): t["pincode"] for t in pending}

            for fut in as_completed(futures):
                try:
                    result = fut.result()
                except Exception as exc:
                    pc = futures.get(fut, "unknown")
                    logger.error("Worker crashed for %s: %s", pc, exc, exc_info=True)
                    pbar.update(1)
                    continue

                if result.get("success"):
                    with _write_lock:
                        # ── CSV append (always reindexed to fixed schema) ──────
                        pd.DataFrame([result["csv_row"]]).reindex(
                            columns=_ALL_COLS, fill_value=0.0
                        ).to_csv(csv_path, mode="a", header=False, index=False)

                        # ── JSONL append ──────────────────────────────────────
                        with open(jsonl_path, "a", encoding="utf-8") as jf:
                            jf.write(
                                json.dumps(result["jsonl_record"], ensure_ascii=False) + "\n"
                            )

                    completed_this_session.append(result["jsonl_record"])

                pbar.update(1)

    # ── Final JSON: read all JSONL (includes previous sessions) ─────────────
    logger.warning("Writing final JSON from complete JSONL...")
    try:
        all_records = []
        if jsonl_path.exists():
            with open(jsonl_path, encoding="utf-8") as jf:
                for line in jf:
                    line = line.strip()
                    if line:
                        try:
                            all_records.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        json_path.write_text(
            json.dumps(all_records, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as exc:
        logger.error("Final JSON write failed: %s", exc)

    logger.warning(
        "Polygon pipeline complete. %d processed this session | %d total in outputs.\n"
        "  CSV   -> %s\n  JSONL -> %s\n  JSON  -> %s",
        len(completed_this_session), len(all_records) if 'all_records' in dir() else '?',
        csv_path, jsonl_path, json_path,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(
        description="Phase 2 polygon-based amenity scoring pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--geojson",    default="data/All_India_pincode_Boundary-19312.geojson",
                   help="Pincode boundary GeoJSON file")
    p.add_argument("--output",     default="results/polygon_scores",
                   help="Output stem (produces .csv / .jsonl / .json)")
    p.add_argument("--filter-csv", default=None,
                   help="Restrict to pincodes present in this CSV ('Pincode' column)")
    p.add_argument("--points",     type=int, default=16,
                   help="Sample points per polygon (default 16 — optimal)")
    p.add_argument("--workers",    type=int, default=4,
                   help="Parallel threads (default 4; keep ≤ 6 to avoid 429s)")
    p.add_argument("--limit",      type=int, default=None,
                   help="Restrict to first N pincodes (testing only)")
    args = p.parse_args()

    filter_pincodes: Optional[Set[str]] = None
    if args.filter_csv:
        try:
            df_f = pd.read_csv(args.filter_csv, dtype=str)
            col  = next(
                (c for c in df_f.columns if c.lower() == "pincode" or "pincode" in c.lower()),
                None,
            )
            if col is None:
                raise ValueError(f"No 'Pincode' column found in {args.filter_csv}")
            filter_pincodes = set()
            for raw in df_f[col].dropna().tolist():
                raw = raw.strip()
                try:
                    filter_pincodes.add(str(int(float(raw))))
                except ValueError:
                    filter_pincodes.add(raw)
            logger.warning("Filter CSV loaded: %d unique pincodes.", len(filter_pincodes))
        except Exception as exc:
            logger.error("Failed to load --filter-csv: %s", exc)

    run_batch(
        geojson_path    = args.geojson,
        output_stem     = args.output,
        n_points        = args.points,
        limit           = args.limit,
        n_workers       = args.workers,
        filter_pincodes = filter_pincodes,
    )


if __name__ == "__main__":
    main()
