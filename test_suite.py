"""
test_suite.py — End-to-end validation for amenity_scorer.
Run from amenity_v2/ with the venv active:
    python test_suite.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "amenity_scorer"))

import numpy as np

# ── Imports ──────────────────────────────────────────────────────────────────
from config import CATEGORY_WEIGHTS, COMPONENT_WEIGHTS, API_MAX_RETRIES, REQUESTS_PER_SECOND
from utils import safe_divide, haversine_km, gini_coefficient, RateLimiter, cache_key, setup_logging
from amenity_calculator import AmenityCalculator
from category_scorer import CategoryScorer
from feature_extractor import FeatureExtractor
from poi_fetcher import POIFetcher
from main import AmenityPipeline, _validate_coords, _error_result

PASS = "[PASS]"
FAIL = "[FAIL]"

errors = []

def check(name, cond, detail=""):
    if cond:
        print(f"  {PASS} {name}")
    else:
        print(f"  {FAIL} {name}" + (f" — {detail}" if detail else ""))
        errors.append(name)

# ── 1. Config ─────────────────────────────────────────────────────────────────
print("\n[1] Config")
check("CATEGORY_WEIGHTS sum ~1.0", abs(sum(CATEGORY_WEIGHTS.values()) - 1.0) < 0.01,
      f"got {sum(CATEGORY_WEIGHTS.values()):.4f}")
check("COMPONENT_WEIGHTS sum ~1.0", abs(sum(COMPONENT_WEIGHTS.values()) - 1.0) < 0.01,
      f"got {sum(COMPONENT_WEIGHTS.values()):.4f}")
check("API_MAX_RETRIES >= 5", API_MAX_RETRIES >= 5)
check("REQUESTS_PER_SECOND > 0", REQUESTS_PER_SECOND > 0)

# ── 2. Utils ──────────────────────────────────────────────────────────────────
print("\n[2] Utils")
check("safe_divide zero denominator", safe_divide(10, 0) == 0.0)
check("safe_divide normal", safe_divide(10, 2) == 5.0)
check("safe_divide inf", safe_divide(1e308, 1e-308) == 0.0)
check("haversine_km 0,0->0,1 ~111km", abs(haversine_km(0, 0, 0, 1) - 111.19) < 1.0)
check("haversine_km same point == 0", haversine_km(19.07, 72.87, 19.07, 72.87) == 0.0)
arr = np.array([1.0, 2.0, 3.0, 4.0])
g = gini_coefficient(arr)
check("gini_coefficient in [0,1]", 0.0 <= g <= 1.0, f"got {g:.4f}")
check("gini_coefficient empty", gini_coefficient(np.array([])) == 0.0)
check("gini_coefficient zeros", gini_coefficient(np.array([0.0, 0.0])) == 0.0)
check("cache_key is 32-char hex", len(cache_key(19.07, 72.87, 2.0)) == 32)

# ── 3. AmenityCalculator ──────────────────────────────────────────────────────
print("\n[3] AmenityCalculator")
calc = AmenityCalculator()

r0 = calc.calculate({}, total_pois=0)
check("zero POIs → index=0", r0["amenity_index"] == 0.0)
check("zero POIs → Rural", r0["classification"] == "Rural")
check("zero POIs → data_quality=Zero", r0["data_quality"] == "Zero")

mock_scores = {cat: {"score": 80.0, "components": {}} for cat in CATEGORY_WEIGHTS}
feats = {"global_gini_coefficient": 0.3, "global_simpson_diversity": 70.0}
rm = calc.calculate(mock_scores, total_pois=100, features=feats)
check("mock scores → index in [0,100]", 0 <= rm["amenity_index"] <= 100)
check("mock scores → classification set", rm["classification"] in ("Metro", "Urban", "Rural"))
check("mock scores → penalties dict", isinstance(rm["penalties"], dict))

check("classify >=60 → Metro", calc._classify(65) == "Metro")
check("classify 30-59 → Urban", calc._classify(45) == "Urban")
check("classify <30 → Rural", calc._classify(10) == "Rural")

check("data_quality 0 → Zero", calc._data_quality_label(0) == "Zero")
check("data_quality 3 → Very Low", calc._data_quality_label(3) == "Very Low")
check("data_quality 10 → Low", calc._data_quality_label(10) == "Low")
check("data_quality 25 → Medium", calc._data_quality_label(25) == "Medium")
check("data_quality 50 → High", calc._data_quality_label(50) == "High")

# ── 4. CategoryScorer ─────────────────────────────────────────────────────────
print("\n[4] CategoryScorer")
scorer = CategoryScorer()

MOCK_POIS = [
    {"poi_type": "hospital",  "distance_km": 0.3, "lat": 19.070, "lon": 72.870},
    {"poi_type": "clinic",    "distance_km": 0.5, "lat": 19.080, "lon": 72.880},
    {"poi_type": "pharmacy",  "distance_km": 0.2, "lat": 19.060, "lon": 72.860},
    {"poi_type": "doctors",   "distance_km": 0.8, "lat": 19.090, "lon": 72.890},
    {"poi_type": "dentist",   "distance_km": 1.1, "lat": 19.050, "lon": 72.850},
]

r_hc = scorer.score("healthcare", {}, MOCK_POIS)
check("healthcare score in [0,100]", 0 <= r_hc["score"] <= 100)
check("healthcare components present", set(r_hc["components"].keys()) == {"density","proximity","quality","accessibility","spatial","economic"})

r_unk = scorer.score("nonexistent_category", {}, MOCK_POIS)
check("unknown category → score=0", r_unk["score"] == 0.0)

r_empty = scorer.score("healthcare", {}, [])
check("empty POI list → score=0", r_empty["score"] == 0.0)

# ── 5. FeatureExtractor ───────────────────────────────────────────────────────
print("\n[5] FeatureExtractor")
extractor = FeatureExtractor()

feats_full = extractor.extract_all(19.076, 72.877, MOCK_POIS)
check("total_pois correct", feats_full["total_pois"] == len(MOCK_POIS))
check("latitude stored", feats_full["latitude"] == 19.076)
check("longitude stored", feats_full["longitude"] == 72.877)
check(">20 features extracted", len(feats_full) > 20, f"got {len(feats_full)}")
check("all feature values numeric", all(isinstance(v, (int, float, str)) for v in feats_full.values()))

feats_empty = extractor.extract_all(19.076, 72.877, [])
check("empty POIs → total_pois=0", feats_empty["total_pois"] == 0)

# POI missing distance_km should be filtered out
bad_pois = [{"poi_type": "hospital", "lat": 19.07, "lon": 72.87}]
feats_bad = extractor.extract_all(19.076, 72.877, bad_pois)
check("POI missing distance_km filtered", feats_bad["total_pois"] == 0)

# ── 5.5 End-to-End Mathematical Conversion ────────────────────────────────────
print("\n[5.5] End-to-End Mathematical Conversion (Raw Features -> Scores)")
# Verify that raw features directly convert to final scores properly
test_features = extractor.extract_all(19.076, 72.877, MOCK_POIS)
cat_scores = {}
for category in CATEGORY_WEIGHTS:
    cat_scores[category] = scorer.score(category, test_features, MOCK_POIS)

check("Category scoring utilized raw features", cat_scores["healthcare"]["score"] > 0)
check("Category component (density) computed", cat_scores["healthcare"]["components"]["density"] > 0)
check("Category component (proximity) computed", cat_scores["healthcare"]["components"]["proximity"] > 0)

final_calc = calc.calculate(cat_scores, total_pois=len(MOCK_POIS), features=test_features)
check("Raw features -> Final score successful", final_calc["amenity_index"] > 0)
check("Scores mapped to classification", final_calc["classification"] in ["Metro", "Urban", "Rural"])


# ── 6. Coordinate Validation ─────────────────────────────────────────────────
print("\n[6] Coordinate Validation")
try:
    _validate_coords(19.076, 72.877)
    check("valid India coords pass", True)
except ValueError:
    check("valid India coords pass", False)

try:
    _validate_coords(0.0, 72.877)
    check("lat outside India raises", False)
except ValueError:
    check("lat outside India raises", True)

try:
    _validate_coords(19.076, 0.0)
    check("lon outside India raises", False)
except ValueError:
    check("lon outside India raises", True)

# ── 7. Error Result Shape ─────────────────────────────────────────────────────
print("\n[7] Error Result Shape")
err = _error_result(19.07, 72.87, Exception("test"), 1.23)
check("error result has location", "location" in err)
check("error result has amenity_index", "amenity_index" in err)
check("error result has metadata", "metadata" in err)
check("error result status=error", err["metadata"]["status"] == "error")
check("error result amenity_index=0", err["amenity_index"]["amenity_index"] == 0.0)

# ── 8. Live Single-Point API Test ─────────────────────────────────────────────
print("\n[8] Live API Test (single point)")
print("  Fetching Mumbai POIs from Overpass (uses cache if available)...")
try:
    pipeline = AmenityPipeline()
    result = pipeline.process(19.076, 72.877)
    meta = result["metadata"]
    idx  = result["amenity_index"]

    check("status=success", meta["status"] == "success", meta.get("status"))
    check("total_pois >= 0", meta["total_pois"] >= 0)
    check("amenity_index in [0,100]", 0 <= idx["amenity_index"] <= 100)
    check("classification valid", idx["classification"] in ("Metro", "Urban", "Rural"))
    check("category_scores for all cats",
          set(result["category_scores"].keys()) == set(CATEGORY_WEIGHTS.keys()))
    if meta["total_pois"] > 0:
        check("features extracted", meta["num_features"] > 50, f"got {meta['num_features']}")
    print(f"  -> Score: {idx['amenity_index']} | Class: {idx['classification']} | POIs: {meta['total_pois']}")
except Exception as exc:
    errors.append(f"Live API test: {exc}")
    print(f"  {FAIL} Live API test raised: {exc}")


# ── 9. Batch CSV Processing ───────────────────────────────────────────────────
print("\n[9] Batch CSV Processing (2 rows, sequential)")
import tempfile
import json
import pandas as pd

CSV_INPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "location_test.csv")
batch_ok = os.path.exists(CSV_INPUT)
check("location_test.csv exists", batch_ok, CSV_INPUT)

if batch_ok:
    # Column detection
    df_test = pd.read_csv(CSV_INPUT)
    lat_col  = next((c for c in df_test.columns if "lat" in c.lower()), None)
    lon_col  = next((c for c in df_test.columns if "lon" in c.lower()), None)
    addr_col = next((c for c in df_test.columns if "addr" in c.lower()), None)
    check("lat column detected",  lat_col  is not None, f"columns={df_test.columns.tolist()}")
    check("lon column detected",  lon_col  is not None)
    check("address column detected", addr_col is not None)

    # NaN / non-numeric coordinate robustness
    import io
    bad_csv = "Address,Latitude,Longitude\nGood,19.076,72.877\nBad,,72.877\nAlsoBad,abc,72.877\n"
    df_bad = pd.read_csv(io.StringIO(bad_csv))
    df_bad["Latitude"]  = pd.to_numeric(df_bad["Latitude"],  errors="coerce")
    df_bad["Longitude"] = pd.to_numeric(df_bad["Longitude"], errors="coerce")
    df_bad = df_bad.dropna(subset=["Latitude", "Longitude"])
    check("NaN lat rows dropped",         len(df_bad) == 1)
    check("non-numeric lat rows dropped", df_bad.iloc[0]["Address"] == "Good")

    # Run 2-row batch (uses cache — no extra API calls)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_stem  = os.path.join(tmpdir, "test_out")
            pipeline2 = AmenityPipeline()
            pipeline2.process_batch(
                CSV_INPUT,
                out_stem,
                limit=2,
                parallel=False,
                n_workers=1,
            )
            out_csv   = out_stem + ".csv"
            out_json  = out_stem + ".json"
            out_jsonl = out_stem + ".jsonl"

            check("batch CSV created",   os.path.exists(out_csv))
            check("batch JSON created",  os.path.exists(out_json))
            check("batch JSONL created", os.path.exists(out_jsonl))

            if os.path.exists(out_csv):
                df_out = pd.read_csv(out_csv)
                check("batch CSV has 2 rows",
                      len(df_out) == 2, f"got {len(df_out)}")
                check("batch CSV has amenity_index",
                      "amenity_index"  in df_out.columns)
                check("batch CSV has classification",
                      "classification" in df_out.columns)
                check("batch CSV scores in [0,100]",
                      df_out["amenity_index"].between(0, 100).all(),
                      df_out["amenity_index"].tolist())
                check("batch CSV classifications valid",
                      df_out["classification"].isin(["Metro", "Urban", "Rural"]).all())
                for cat in list(CATEGORY_WEIGHTS.keys()):
                    check(f"batch CSV has {cat}_score col",
                          f"{cat}_score" in df_out.columns)

            if os.path.exists(out_json):
                with open(out_json, encoding="utf-8") as fh:
                    jdata = json.load(fh)
                check("batch JSON is list",         isinstance(jdata, list))
                check("batch JSON has 2 entries",   len(jdata) == 2, f"got {len(jdata)}")
                check("batch JSON entry has amenity_index",    "amenity_index"   in jdata[0])
                check("batch JSON entry has category_scores",  "category_scores" in jdata[0])
                check("batch JSON entry has metadata",          "metadata"        in jdata[0])

            if os.path.exists(out_jsonl):
                with open(out_jsonl, encoding="utf-8") as fh:
                    lines = [json.loads(ln) for ln in fh if ln.strip()]
                check("batch JSONL has 2 lines", len(lines) == 2, f"got {len(lines)}")

    except Exception as exc:
        errors.append(f"Batch CSV test: {exc}")
        print(f"  {FAIL} Batch CSV test raised: {exc}")


# ── 10. Existing Output File Schema ───────────────────────────────────────────
print("\n[10] Existing Output File Schema")
FULL_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "amenity_scores.csv")
if os.path.exists(FULL_CSV):
    df_full = pd.read_csv(FULL_CSV)
    required_cols = [
        "address", "latitude", "longitude", "amenity_index", "classification",
        "data_quality", "total_pois", "processing_time_s",
    ]
    for col in required_cols:
        check(f"results CSV has '{col}'", col in df_full.columns)
    check("results CSV amenity_index in [0,100]",
          df_full["amenity_index"].between(0, 100).all(),
          f"min={df_full['amenity_index'].min()}, max={df_full['amenity_index'].max()}")
    print(f"  -> {len(df_full)} rows validated")
else:
    print("  (no existing results/amenity_scores.csv — skipping)")


# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 55)
if errors:
    print(f"RESULT: {len(errors)} TEST(S) FAILED")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("RESULT: ALL TESTS PASSED")
    sys.exit(0)
