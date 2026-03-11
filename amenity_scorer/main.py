"""
main.py — CLI entry point for the Amenity Scoring System.

Usage:
    # Single location
    python main.py --lat 19.194 --lon 73.085

    # First 50 locations from CSV
    python main.py --input ../data/location.csv --output ../results/amenity_scores --limit 50

    # Full batch, 4 parallel workers
    python main.py --input ../data/location.csv --output ../results/amenity_scores --workers 4

Output files (auto-created / appended for resume):
    results/amenity_scores.csv    — one row per location, all scores
    results/amenity_scores.jsonl  — one JSON object per line (full detail)
    results/amenity_scores.json   — pretty-printed array (written at the end)
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd
from tqdm import tqdm

import config
from amenity_calculator import AmenityCalculator
from category_scorer import CategoryScorer
from feature_extractor import FeatureExtractor
from poi_fetcher import POIFetcher
from utils import setup_logging

logger = setup_logging()

_LAT_MIN, _LAT_MAX = 6.5, 35.5
_LON_MIN, _LON_MAX = 68.0, 97.5

# CSV columns written per row
_BASE_COLS = [
    "address", "latitude", "longitude", "amenity_index", "classification",
    "data_quality", "total_pois", "processing_time_s",
]
_CAT_COLS = [f"{c}_score" for c in config.CATEGORY_WEIGHTS]
_ALL_COLS  = _BASE_COLS + _CAT_COLS


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class AmenityPipeline:
    """End-to-end pipeline: fetch POIs → extract features → score → index."""

    def __init__(self):
        self.poi_fetcher = POIFetcher(logger)
        self.extractor   = FeatureExtractor()
        self.scorer      = CategoryScorer()
        self.calculator  = AmenityCalculator()
        logger.info("AmenityPipeline initialised (v%s)", config.VERSION)

    def process(self, lat: float, lon: float) -> Dict:
        """Score a single location. Returns a full result dict."""
        start = time.time()
        try:
            _validate_coords(lat, lon)

            try:
                pois = self.poi_fetcher.fetch(lat, lon, max_radius_km=2.0)
            except Exception as exc:
                logger.error("POI fetch failed (%.4f, %.4f): %s", lat, lon, exc)
                pois = []

            if len(pois) < 10:
                logger.warning("Only %d POIs at (%.4f, %.4f) - data quality may be poor",
                               len(pois), lat, lon)

            try:
                features = self.extractor.extract_all(lat, lon, pois)
            except Exception as exc:
                logger.error("Feature extraction failed: %s", exc)
                features = {"latitude": lat, "longitude": lon, "total_pois": len(pois)}

            category_scores: Dict = {}
            for cat in config.CATEGORY_WEIGHTS:
                try:
                    category_scores[cat] = self.scorer.score(cat, features, pois)
                except Exception as exc:
                    logger.error("Scoring failed for %s: %s", cat, exc)
                    category_scores[cat] = {"score": 0.0, "components": {}}

            try:
                index = self.calculator.calculate(
                    category_scores, total_pois=len(pois), features=features
                )
            except Exception as exc:
                logger.error("Index calculation failed: %s", exc)
                index = {
                    "amenity_index": 0.0, "classification": "Error",
                    "data_quality": "Error", "penalties": {}, "weighted_score": 0.0,
                }

            elapsed = round(time.time() - start, 3)
            return {
                "location":        {"latitude": lat, "longitude": lon},
                "amenity_index":   index,
                "category_scores": category_scores,
                "features":        features,
                "metadata": {
                    "processing_time_s": elapsed,
                    "total_pois":        len(pois),
                    "num_features":      len(features),
                    "status":            "success",
                },
            }

        except Exception as exc:
            logger.error("Critical error at (%.4f, %.4f): %s", lat, lon, exc)
            return _error_result(lat, lon, exc, time.time() - start)

    def process_batch(
        self,
        input_file: str,
        output_stem: str,
        limit: Optional[int] = None,
        parallel: bool = True,
        n_workers: int = 4,
    ) -> None:
        """
        Process locations from a CSV and write live output to:
          <output_stem>.csv   — appended after every row (resume-safe)
          <output_stem>.jsonl — appended after every row (resume-safe)
          <output_stem>.json  — pretty-printed array written at the end

        Supports resume: rows already in the CSV are skipped.
        """
        csv_path   = Path(output_stem + ".csv")
        jsonl_path = Path(output_stem + ".jsonl")
        json_path  = Path(output_stem + ".json")

        # Load input
        df = pd.read_csv(input_file)
        lat_col  = next((c for c in df.columns if "lat" in c.lower()), None)
        lon_col  = next((c for c in df.columns if "lon" in c.lower()), None)
        addr_col = next((c for c in df.columns if "addr" in c.lower() or c.lower() == "address"), None)
        if not lat_col or not lon_col:
            raise ValueError("Cannot find latitude/longitude columns in input CSV")

        all_locations: List[Tuple[float, float, str]] = [
            (float(row[lat_col]), float(row[lon_col]),
             str(row.get(addr_col, "")) if addr_col else "")
            for _, row in df.iterrows()
        ]
        if limit:
            all_locations = all_locations[:limit]

        # Resume: find already-processed coordinates
        processed = _load_processed_set(csv_path)
        locations = [
            (lat, lon, addr) for lat, lon, addr in all_locations
            if (round(lat, 6), round(lon, 6)) not in processed
        ]

        if not locations:
            logger.info("All %d locations already processed. Nothing to do.", len(all_locations))
            return

        logger.info(
            "Processing %d/%d locations (skipped %d already done) | "
            "mode=%s workers=%d",
            len(locations), len(all_locations), len(processed),
            "parallel" if parallel else "sequential", n_workers,
        )

        # Initialise CSV header if new file
        if not csv_path.exists():
            pd.DataFrame(columns=_ALL_COLS).to_csv(csv_path, index=False)

        all_results: List[Dict] = []

        def _handle(result: Dict, address: str = "") -> None:
            """Write one result to CSV and JSONL immediately (live output)."""
            result["location"]["address"] = address
            _append_csv(result, csv_path)
            _append_jsonl(result, jsonl_path)
            all_results.append(result)
            _print_live(result)

        with tqdm(total=len(locations), desc="Scoring", unit="loc",
                  bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]") as pbar:

            if parallel and n_workers > 1:
                with ThreadPoolExecutor(max_workers=min(n_workers, 8)) as pool:
                    futures = {
                        pool.submit(self.process, lat, lon): (lat, lon, addr)
                        for lat, lon, addr in locations
                    }
                    for fut in as_completed(futures):
                        lat, lon, addr = futures[fut]
                        result = fut.result()
                        _handle(result, addr)
                        pbar.update(1)
            else:
                for lat, lon, addr in locations:
                    result = self.process(lat, lon)
                    _handle(result, addr)
                    pbar.update(1)

        # Write final pretty JSON
        _write_json(all_results, json_path)

        logger.info(
            "Batch complete. %d locations processed.\n"
            "  CSV   -> %s\n  JSONL -> %s\n  JSON  -> %s",
            len(all_results), csv_path, jsonl_path, json_path,
        )


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _append_csv(result: Dict, path: Path) -> None:
    """Append one result row to CSV immediately (live)."""
    try:
        loc = result["location"]
        row = {
            "address":           loc.get("address", ""),
            "latitude":          loc["latitude"],
            "longitude":         loc["longitude"],
            "amenity_index":     result["amenity_index"]["amenity_index"],
            "classification":    result["amenity_index"]["classification"],
            "data_quality":      result["amenity_index"].get("data_quality", ""),
            "total_pois":        result["metadata"]["total_pois"],
            "processing_time_s": result["metadata"]["processing_time_s"],
        }
        for cat in config.CATEGORY_WEIGHTS:
            row[f"{cat}_score"] = result["category_scores"].get(cat, {}).get("score", 0.0)

        pd.DataFrame([row]).reindex(columns=_ALL_COLS, fill_value=0.0).to_csv(
            path, mode="a", header=False, index=False
        )
    except Exception as exc:
        logger.error("CSV append failed: %s", exc)


def _append_jsonl(result: Dict, path: Path) -> None:
    """Append one result as a JSON line immediately (live)."""
    try:
        loc = result["location"]
        slim = {
            "address":         loc.get("address", ""),
            "location":        {"latitude": loc["latitude"], "longitude": loc["longitude"]},
            "amenity_index":   result["amenity_index"],
            "category_scores": result["category_scores"],  # Full dict including components
            "metadata":        result["metadata"],
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(slim, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.error("JSONL append failed: %s", exc)


def _write_json(results: List[Dict], path: Path) -> None:
    """Write all results as a pretty-printed JSON array."""
    try:
        slim_results = [
            {
                "address":         r["location"].get("address", ""),
                "location":        {"latitude": r["location"]["latitude"],
                                    "longitude": r["location"]["longitude"]},
                "amenity_index":   r["amenity_index"],
                "category_scores": r["category_scores"],  # Full dict including components
                "metadata":        r["metadata"],
            }
            for r in results
        ]
        path.write_text(
            json.dumps(slim_results, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.error("JSON write failed: %s", exc)


def _print_live(result: Dict) -> None:
    """Print a one-line live score to the terminal."""
    loc   = result["location"]
    idx   = result["amenity_index"]
    meta  = result["metadata"]
    addr  = loc.get("address", f"{loc['latitude']:.4f},{loc['longitude']:.4f}")
    score = idx.get("amenity_index", 0.0)
    cls   = idx.get("classification", "?").ljust(6)
    pois  = meta.get("total_pois", 0)
    t     = meta.get("processing_time_s", 0.0)
    tqdm.write(
        f"  {addr[:50]:<50} | Score: {score:5.1f} | {cls} | POIs: {pois:4d} | {t:.1f}s"
    )


def _load_processed_set(csv_path: Path) -> Set[Tuple[float, float]]:
    """Return set of (lat, lon) already written to the CSV."""
    if not csv_path.exists():
        return set()
    try:
        df = pd.read_csv(csv_path, usecols=["latitude", "longitude"])
        return {(round(r.latitude, 6), round(r.longitude, 6)) for r in df.itertuples()}
    except Exception:
        return set()


def _validate_coords(lat: float, lon: float) -> None:
    if not (_LAT_MIN <= lat <= _LAT_MAX):
        raise ValueError(f"Latitude {lat} outside India ({_LAT_MIN}-{_LAT_MAX})")
    if not (_LON_MIN <= lon <= _LON_MAX):
        raise ValueError(f"Longitude {lon} outside India ({_LON_MIN}-{_LON_MAX})")


def _error_result(lat: float, lon: float, exc: Exception, elapsed: float) -> Dict:
    return {
        "location":        {"latitude": lat, "longitude": lon},
        "amenity_index":   {
            "amenity_index": 0.0, "classification": "Error",
            "data_quality": "Error", "penalties": {}, "weighted_score": 0.0,
        },
        "category_scores": {},
        "features":        {},
        "metadata": {
            "processing_time_s": round(elapsed, 3),
            "total_pois":        0,
            "num_features":      0,
            "status":            "error",
            "error":             str(exc),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Amenity Scoring System — India-calibrated OSM amenity index",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--lat",   type=float, help="Latitude  (single-location mode)")
    mode.add_argument("--input", metavar="CSV", help="Input CSV file (batch mode)")

    p.add_argument("--lon",        type=float, help="Longitude (required with --lat)")
    p.add_argument("--output",     metavar="STEM",
                   help="Output file stem (batch mode). Produces STEM.csv, STEM.jsonl, STEM.json")
    p.add_argument("--limit",      type=int, default=None,
                   help="Process only the first N rows (default: all)")
    p.add_argument("--workers",    type=int, default=4,
                   help="Parallel workers for batch (default: 4)")
    p.add_argument("--sequential", action="store_true",
                   help="Disable parallel processing")
    return p


def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    if args.lat is not None and args.lon is None:
        parser.error("--lon is required when using --lat")
    if args.input and not args.output:
        parser.error("--output STEM is required in batch mode")

    pipeline = AmenityPipeline()

    try:
        if args.lat is not None:
            result = pipeline.process(args.lat, args.lon)
            idx    = result["amenity_index"]
            print(f"\n{'='*62}")
            print(f"  Location   : ({args.lat}, {args.lon})")
            print(f"  Score      : {idx['amenity_index']:.1f} / 100")
            print(f"  Class      : {idx['classification']}")
            print(f"  Data Qual  : {idx.get('data_quality','')}")
            print(f"  POIs       : {result['metadata']['total_pois']}")
            print(f"  Time       : {result['metadata']['processing_time_s']:.2f}s")
            print(f"\n  Category Scores:")
            for cat, data in result["category_scores"].items():
                print(f"    {cat:<14}: {data['score']:5.1f}")
            print(f"\n  Penalties  : {idx.get('penalties', {})}")
            print(f"{'='*62}\n")

            if args.output:
                stem = args.output
                _append_csv(result, Path(stem + ".csv"))
                _append_jsonl(result, Path(stem + ".jsonl"))
                _write_json([result], Path(stem + ".json"))
                print(f"Saved to {stem}.csv / .jsonl / .json")

        else:
            pipeline.process_batch(
                args.input,
                args.output,
                limit=args.limit,
                parallel=not args.sequential,
                n_workers=args.workers,
            )

    except KeyboardInterrupt:
        print("\nInterrupted. Progress saved — re-run the same command to resume.")
        sys.exit(0)
    except Exception as exc:
        print(f"\nError: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
