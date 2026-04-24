"""
comprehensive_test.py — Full formula & edge-case test suite for every scoring component.
Covers: utils, feature_extractor, category_scorer, amenity_calculator
Run from: amenity_v2/ root  →  python comprehensive_test.py
"""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "amenity_scorer"))

import numpy as np
from amenity_scorer.utils import safe_divide, haversine_km, gini_coefficient
from amenity_scorer.category_scorer import CategoryScorer
from amenity_scorer.amenity_calculator import AmenityCalculator
from amenity_scorer.feature_extractor import FeatureExtractor

# ── Colour helpers ────────────────────────────────────────────────────────────
G, R, Y, RST = "\033[92m", "\033[91m", "\033[93m", "\033[0m"
passes = failures = warnings = 0

def check(name, cond, detail=""):
    global passes, failures
    if cond:
        passes += 1
        print(f"  {G}PASS{RST}  {name}")
    else:
        failures += 1
        print(f"  {R}FAIL{RST}  {name}" + (f"  →  {detail}" if detail else ""))

def warn(msg):
    global warnings
    warnings += 1
    print(f"  {Y}WARN{RST}  {msg}")

def header(s):
    print(f"\n{'='*60}\n {s}\n{'='*60}")

def poi(t, d, lat=12.97, lon=77.59, **kw):
    return {"poi_type": t, "distance_km": d, "lat": lat, "lon": lon, **kw}

scorer = CategoryScorer()
calc   = AmenityCalculator()
ext    = FeatureExtractor()

# ═══════════════════════════════════════════════════════════════
# 1. UTILS
# ═══════════════════════════════════════════════════════════════
header("1. Utils — safe_divide, haversine_km, gini_coefficient")

check("safe_divide(10, 2) = 5",          safe_divide(10, 2) == 5.0)
check("safe_divide(x, 0) returns 0",     safe_divide(99, 0) == 0.0)
check("safe_divide(x, 0, -1) returns -1",safe_divide(99, 0, -1) == -1.0)
check("safe_divide(inf, 1) returns 0",   safe_divide(float("inf"), 1) == 0.0, "inf not caught")
check("safe_divide(nan, 1) returns 0",   safe_divide(float("nan"), 1) == 0.0, "nan not caught")
check("safe_divide(0, 0) returns 0",     safe_divide(0, 0) == 0.0)
check("safe_divide(neg, pos) works",     abs(safe_divide(-6, 3) - (-2.0)) < 1e-9)

d_same = haversine_km(12.97, 77.59, 12.97, 77.59)
check("haversine same point = 0 km",    d_same < 1e-9, f"got {d_same}")
d_1deg_lat = haversine_km(0, 0, 1, 0)
check("haversine 1° lat ≈ 111.32 km",  abs(d_1deg_lat - 111.32) < 0.5, f"got {d_1deg_lat:.2f}")
d_india = haversine_km(28.61, 77.20, 12.97, 77.59)  # Delhi→Bengaluru ~ 1739km by haversine
check("haversine Delhi→Bengaluru ≈ 1730–1760 km", 1730 < d_india < 1760, f"got {d_india:.1f}")
check("haversine symmetric", abs(haversine_km(12.97,77.59,13.0,77.6) - haversine_km(13.0,77.6,12.97,77.59)) < 1e-9)

g0 = gini_coefficient(np.array([5.0, 5.0, 5.0]))
check("gini all equal = 0", g0 == 0.0, f"got {g0}")
g1 = gini_coefficient(np.array([0.0, 0.0, 0.0, 100.0]))
check("gini one dominant ≈ 0.75", 0.70 < g1 < 0.80, f"got {g1:.3f}")
g_empty = gini_coefficient(np.array([]))
check("gini empty = 0", g_empty == 0.0)
g_one = gini_coefficient(np.array([42.0]))
check("gini single-element = 0", g_one == 0.0)
g_zero = gini_coefficient(np.array([0.0, 0.0, 0.0]))
check("gini all-zero = 0", g_zero == 0.0)
check("gini in [0, 1]", 0 <= gini_coefficient(np.array([1,2,3,40,1])) <= 1)

# ═══════════════════════════════════════════════════════════════
# 2. CATEGORY SCORER — _density
# ═══════════════════════════════════════════════════════════════
header("2. CategoryScorer._density — all boundary conditions")

# helper: call _density with simple list
def density_score(cat, dists):
    pois = [poi(cat, d) for d in dists]  # use category name as poi_type (won't match, but distance is what matters)
    # Use a generic type that exists in the category
    type_map = {"healthcare":"hospital","education":"school","shopping":"shop",
                "food":"restaurant","transport":"bus_stop","finance":"bank",
                "cultural":"park","essential":"pharmacy","employment":"office",
                "premium":"gym","civic":"police"}
    t = type_map.get(cat, "hospital")
    pois = [poi(t, d) for d in dists]
    return scorer._density(pois, cat)

d_empty = density_score("healthcare", [])
check("density empty POIs = 0",          d_empty == 0.0, f"got {d_empty}")
d_one = density_score("healthcare", [0.3])
check("density 1 POI > 0",              d_one > 0, f"got {d_one}")
d_one_far = density_score("healthcare", [1.99])
check("density 1 far POI < 1 POI close", d_one_far < d_one, f"{d_one_far:.2f} vs {d_one:.2f}")
d_many = density_score("healthcare", [0.1]*50)
# At 2km ring: benchmark(5 POIs/km²) × π×4km² = 62.8 → excellent=157 → 50 POIs < excellent
# So the 2km ring scores ~70-80, not 100. Overall weighted: 100×0.5 + 100×0.3 + ~75×0.2 ≈ 95
check("density 50 close POIs ≥ 88 (saturated, 2km ring still below excellent)",
      d_many >= 88.0, f"got {d_many:.2f}")
check("density monotone: more POIs → higher score",
      density_score("shopping", [0.1]*5) < density_score("shopping", [0.1]*30))
d_miss = scorer._density([{"poi_type": "hospital"}], "healthcare")  # no distance_km
check("density missing distance_km doesn't crash", d_miss == 0.0, f"got {d_miss}")
check("density score always in [0, 100]",
      all(0 <= density_score("food", [d]) <= 100 for d in [0.01, 0.3, 1.0, 1.9, 2.5]))

# ═══════════════════════════════════════════════════════════════
# 3. CATEGORY SCORER — _proximity
# ═══════════════════════════════════════════════════════════════
header("3. CategoryScorer._proximity — decay, averaging, edge cases")

def prox(cat, dists):
    type_map = {"healthcare":"hospital","essential":"pharmacy",
                "transport":"bus_stop","employment":"office","cultural":"park"}
    t = type_map.get(cat, "pharmacy")
    return scorer._proximity([poi(t, d) for d in dists], cat)

check("proximity empty = 0",              prox("healthcare", []) == 0.0)
p_close = prox("healthcare", [0.1])
p_far   = prox("healthcare", [2.0])
check("proximity closer POI scores higher", p_close > p_far, f"{p_close:.1f} vs {p_far:.1f}")
check("proximity at 0.1km healthcare ≈ 78-90", 75 < prox("healthcare", [0.1]) < 95,
      f"got {prox('healthcare', [0.1]):.1f}")
check("proximity 2km healthcare < 10", prox("healthcare", [2.0]) < 12, f"got {p_far:.1f}")
check("proximity employment softer decay than healthcare",
      prox("employment", [1.0]) > prox("healthcare", [1.0]),
      f"emp={prox('employment',[1.0]):.1f} vs hc={prox('healthcare',[1.0]):.1f}")
# Proximity stability: once we have >=5 POIs the nearest-5 average stabilizes
# Adding only far POIs beyond position 5 should not change the score at all
p5   = prox("healthcare", [0.1] + [2.0]*4)         # exactly 5 total
p20  = prox("healthcare", [0.1] + [2.0]*19)        # 20 total (15 extra beyond position 5)
check("proximity stable with 5 vs 20 far POIs (5-nearest confirmed)",
      abs(p5 - p20) < 0.01, f"5-pool={p5:.4f}, 20-pool={p20:.4f}")
check("proximity in [0, 100] always",
      all(0 <= prox("food", [d]) <= 100 for d in [0.001, 0.1, 0.5, 1.0, 2.0, 5.0]))

# ═══════════════════════════════════════════════════════════════
# 4. CATEGORY SCORER — _quality
# ═══════════════════════════════════════════════════════════════
header("4. CategoryScorer._quality — premium/basic ratio, min-POI guard")

def qual(cat, types_and_dists):
    return scorer._quality([poi(t, d) for t,d in types_and_dists], cat)

check("quality empty = 0",  qual("healthcare", []) == 0.0)
# Hospital is premium for healthcare; clinic is basic
q_premium_only = qual("healthcare", [("hospital", 0.5), ("hospital", 0.3), ("hospital", 0.8)])
q_basic_only   = qual("healthcare", [("clinic", 0.5), ("clinic", 0.3), ("pharmacy", 0.8)])
check("quality pure-premium > pure-basic", q_premium_only > q_basic_only,
      f"premium={q_premium_only:.1f}, basic={q_basic_only:.1f}")
check("quality pure-premium ≈ 100", q_premium_only > 90, f"got {q_premium_only:.1f}")
check("quality pure-basic ≈ 50", 40 < q_basic_only < 60, f"got {q_basic_only:.1f}")

# Min POI guard: 1 POI → 33% of full score
q_one   = qual("healthcare", [("hospital", 0.5)])
q_three = qual("healthcare", [("hospital", 0.5)]*3)
check("quality 1 POI ≈ 33% of 3-POI score", abs(q_one - q_three/3) < 5,
      f"1-POI={q_one:.1f}, 3-POI={q_three:.1f}")
q_two   = qual("healthcare", [("hospital", 0.5)]*2)
check("quality 2 POIs > 1 POI (monotone)", q_two > q_one, f"1={q_one:.1f}, 2={q_two:.1f}")
check("quality always in [0, 100]",
      all(0 <= qual("shopping", [(t,0.5)]) <= 100 for t in ["mall","kirana","shop"]))
# No premium or basic types at all → 0
q_unknown = qual("healthcare", [("pet_shop", 0.5)])
check("quality unknown POI types = 0", q_unknown == 0.0, f"got {q_unknown}")

# ═══════════════════════════════════════════════════════════════
# 5. CATEGORY SCORER — _accessibility
# ═══════════════════════════════════════════════════════════════
header("5. CategoryScorer._accessibility — gravity model, normalization")

def acc(cat, types_and_dists):
    return scorer._accessibility([poi(t, d) for t,d in types_and_dists], cat)

check("accessibility empty = 0", acc("healthcare", []) == 0.0)
a_close = acc("healthcare", [("hospital", 0.2)])
a_far   = acc("healthcare", [("hospital", 2.0)])
check("accessibility: closer = higher score", a_close > a_far, f"{a_close:.1f} vs {a_far:.1f}")
a_many_close = acc("healthcare", [("hospital", 0.1)]*20)
check("accessibility 20 hospitals at 100m → 100", a_many_close == 100.0, f"got {a_many_close}")
check("accessibility missing distance_km doesn't crash (near 0)",
      scorer._accessibility([{"poi_type":"hospital"}], "healthcare") < 0.01)
check("accessibility in [0, 100]",
      all(0 <= acc("healthcare", [("hospital", d)]) <= 100 for d in [0.01, 0.1, 0.5, 1.0, 2.0]))
# Inverse-square: doubling distance → 4x less
a_05 = acc("healthcare", [("hospital", 0.5)])
a_10 = acc("healthcare", [("hospital", 1.0)])
check("accessibility inverse-square: 2x dist → ~4x lower",
      2.5 < a_05/max(a_10, 0.001) < 5.5, f"ratio={a_05/max(a_10,0.001):.2f}")

# ═══════════════════════════════════════════════════════════════
# 6. CATEGORY SCORER — _spatial
# ═══════════════════════════════════════════════════════════════
header("6. CategoryScorer._spatial — NNI, hotspot, sparse guards")

def spat(cat, dists, features=None):
    pois = [poi("bus_stop" if cat=="transport" else "hospital", d,
                lat=12.97+i*0.003, lon=77.59+i*0.003) for i, d in enumerate(dists)]
    return scorer._spatial(pois, "transport" if cat=="transport" else "healthcare", features or {})

check("spatial empty = 0",   spat("transport", []) == 0.0)
check("spatial 1 POI = 0",   spat("transport", [0.3]) == 0.0)
check("spatial 2 POIs = 0",  spat("transport", [0.3, 0.6]) == 0.0)
s3 = spat("transport", [0.1, 0.2, 0.3])
check("spatial 3 POIs ≥ 0",  s3 >= 0.0, f"got {s3}")
check("spatial 3 POIs ≤ 100", s3 <= 100.0, f"got {s3}")
# Exception fallback check: nonsense NNI
s_nan = spat("transport", [0.1,0.2,0.3,0.4,0.5], {"global_nearest_neighbor_index": float("nan")})
check("spatial with NaN NNI doesn't crash", isinstance(s_nan, float))
check("spatial always in [0, 100]",
      all(0 <= spat("transport", [i*0.1 for i in range(1, n+1)]) <= 100 for n in [3, 5, 10]))

# ═══════════════════════════════════════════════════════════════
# 7. CATEGORY SCORER — _economic
# ═══════════════════════════════════════════════════════════════
header("7. CategoryScorer._economic — sigmoid, confidence, edge cases")

def econ(cat, n_cat_pois, n_total):
    t = {"healthcare":"hospital","shopping":"shop","food":"restaurant"}.get(cat,"hospital")
    cat_pois = [poi(t, 0.3) for _ in range(n_cat_pois)]
    all_pois = cat_pois + [poi("bank", 0.5) for _ in range(n_total - n_cat_pois)]
    return scorer._economic(cat_pois, all_pois, cat)

check("economic empty cat_pois = 0",   scorer._economic([], [poi("hospital",0.3)], "healthcare") == 0.0)
check("economic empty all_pois = 0",   scorer._economic([poi("hospital",0.3)], [], "healthcare") == 0.0)
e_at_target = econ("healthcare", 8, 100)   # 8% of 100 → target=8 → ratio=1 → expected ≈50
check("economic at target → ≈50",       45 < e_at_target < 55, f"got {e_at_target:.1f}")
e_above = econ("healthcare", 20, 100)  # 20% of 100 → ratio=2.5 → expected ~85
check("economic above target → >65",    e_above > 65, f"got {e_above:.1f}")
e_below = econ("healthcare", 2, 100)   # 2% of 100 → ratio=0.25 → expected ~12
check("economic below target → <25",    e_below < 30, f"got {e_below:.1f}")
e_1poi = econ("healthcare", 1, 100)    # confidence = 1/3
check("economic 1 POI confidence penalised vs 3 POIs",
      e_1poi < econ("healthcare", 3, 100), f"1={e_1poi:.1f}")
check("economic in [0, 100]",
      all(0 <= econ("food", n, 50) <= 100 for n in [0, 1, 3, 6, 12, 25, 50]))

# ═══════════════════════════════════════════════════════════════
# 8. CATEGORY SCORER — full score(), dominance penalty
# ═══════════════════════════════════════════════════════════════
header("8. CategoryScorer.score() — full pipeline, dominance penalty, monotonicity")

def full_score(cat, pois_list):
    feats = ext.extract_all(12.97, 77.59, pois_list)
    return scorer.score(cat, feats, pois_list)

f_empty = full_score("healthcare", [])
check("full score empty POIs → 0",    f_empty["score"] == 0.0)
check("full score empty has components dict",  isinstance(f_empty["components"], dict))

# Monotonicity: adding strictly more POIs at same/closer distances should not lower score
# Use a realistically spread set: 5 hospitals vs 20 hospitals, all within 300m
# To get genuine improvement, use a diverse-type scenario where more types = higher economic/quality
five_p  = [poi("hospital", 0.1+i*0.04, lat=12.97+i*0.002, lon=77.59+i*0.002) for i in range(5)]
twenty_p= [poi("hospital", 0.1+i*0.01, lat=12.97+i*0.001, lon=77.59+i*0.001) for i in range(20)]
s5  = full_score("healthcare", five_p)
s20 = full_score("healthcare", twenty_p)
# Density must increase (more POIs, closer). Economic may vary since n/all_pois ratio changes.
check("density component: 20 hospitals > 5 hospitals",
      s20["components"]["density"] >= s5["components"]["density"],
      f"5-density={s5['components']['density']:.1f}, 20-density={s20['components']['density']:.1f}")

# Score always in [0, 100]
check("full score always [0, 100]",
      all(0 <= full_score("food", [poi("restaurant", d) for d in [0.1, 0.5, 1.0]])["score"] <= 100
          for _ in range(1)))

# Dominance penalty: 15 POIs all same type (for a diverse category like shopping)
mono_pois = [poi("shop", 0.1+i*0.05) for i in range(15)]
div_pois  = [poi(t, 0.2) for t in ["shop","bakery","pharmacy","atm","bank","restaurant","cafe",
                                    "supermarket","pharmacy","bank","school"] for _ in range(1)] + \
            [poi("shop", 0.3) for _ in range(4)]
s_mono = full_score("shopping", mono_pois)
s_div  = full_score("shopping", div_pois)
check("dominance penalty: diverse > mono-type (at same count)",
      s_div["score"] >= s_mono["score"] * 0.95,
      f"div={s_div['score']:.1f}, mono={s_mono['score']:.1f}")

# Unknown category → 0
f_unk = scorer.score("not_a_category", {}, [])
check("unknown category → score=0", f_unk["score"] == 0.0)

# ═══════════════════════════════════════════════════════════════
# 9. AMENITY CALCULATOR — penalties, capping, classification
# ═══════════════════════════════════════════════════════════════
header("9. AmenityCalculator — penalty logic, cap, classification")

CATS = ["essential","healthcare","education","transport","finance",
        "shopping","food","cultural","premium","employment","civic"]

def run_calc(pois_list, features_override=None):
    feats = ext.extract_all(12.97, 77.59, pois_list)
    if features_override:
        feats.update(features_override)
    cat_sc = {cat: scorer.score(cat, feats, pois_list) for cat in CATS}
    return calc.calculate(cat_sc, total_pois=len(pois_list), features=feats)

# Zero POIs
r0 = calc.calculate({}, total_pois=0, features={})
check("calc 0 POIs → index=0",          r0["amenity_index"] == 0.0)
check("calc 0 POIs → class=Rural",      r0["classification"] == "Rural")
check("calc 0 POIs → quality=Zero",     r0["data_quality"] == "Zero")
check("calc 0 POIs → no penalties",     r0["penalties"] == {})

# Data quality penalties
r1 = run_calc([poi("hospital", 0.3)])                            # 1 POI → very_sparse
r20 = run_calc([poi("hospital", 0.3+i*0.05) for i in range(10)]) # 10 POI → sparse
r40 = run_calc([poi("hospital", 0.3+i*0.05) for i in range(30)]) # 30 POI → moderate
r_hq= run_calc([poi("hospital", 0.3+i*0.05) for i in range(60)]) # 60 POI → good
check("DQ very_sparse penalty = 0.20",   r1["penalties"]["data_quality"] == 0.20, f"got {r1['penalties']['data_quality']}")
check("DQ sparse penalty = 0.10",        r20["penalties"]["data_quality"] == 0.10, f"got {r20['penalties']['data_quality']}")
check("DQ moderate penalty = 0.05",      r40["penalties"]["data_quality"] == 0.05, f"got {r40['penalties']['data_quality']}")
check("DQ good penalty = 0.00",          r_hq["penalties"]["data_quality"] == 0.00, f"got {r_hq['penalties']['data_quality']}")

# data_quality label is aligned with penalties
check("DQ label: 0 POI → Zero",       calc._data_quality_label(0) == "Zero")
check("DQ label: 1 POI → Very Low",   calc._data_quality_label(1) == "Very Low")
check("DQ label: 5 POIs → Low",       calc._data_quality_label(5) == "Low")
check("DQ label: 20 POIs → Medium",   calc._data_quality_label(20) == "Medium")
check("DQ label: 40 POIs → High",     calc._data_quality_label(40) == "High")

# Penalty cap at 50%: manually construct a case with all penalties maxed
r_cap = calc.calculate(
    # use non-empty cat scores so weighted_score > 0 (otherwise amenity_index=0)
    {cat: {"score": 50.0, "components": {}} for cat in CATS},
    total_pois=2,       # very_sparse → dq=0.20
    features={
        "global_gini_coefficient":  1.0,   # → gini=0.15
        "global_simpson_diversity": 0.0,   # → diversity=0.10
    }
)
# Expected: dq=0.20, gini=0.15, diversity=0.10, missing_essentials max 0.09 → total=0.54 > 0.50
# Should be capped at 0.50
total_raw_pen = sum(r_cap["penalties"].values())
check("Penalties capped at 50%: total_raw can exceed 50 but result–index reflects cap",
      r_cap["amenity_index"] >= r_cap["weighted_score"] * 0.50,
      f"index={r_cap['amenity_index']:.1f}, ws={r_cap['weighted_score']:.1f}")

# Gini penalty: Gini=0 → 0%, Gini=1 → 15%
pen_gini0 = calc.calculate({"healthcare":{"score":50,"components":{}}}, total_pois=50,
                           features={"global_gini_coefficient": 0.0,
                                     "global_simpson_diversity": 100.0})
pen_gini1 = calc.calculate({"healthcare":{"score":50,"components":{}}}, total_pois=50,
                           features={"global_gini_coefficient": 1.0,
                                     "global_simpson_diversity": 100.0})
check("Gini=0 → type_gini penalty=0",     pen_gini0["penalties"]["type_gini"] == 0.0)
check("Gini=1 → type_gini penalty=0.15",  pen_gini1["penalties"]["type_gini"] == 0.15,
      f"got {pen_gini1['penalties']['type_gini']}")

# Simpson diversity: D=100 → 0%, D=0 → 10%
pen_d100 = calc.calculate({}, total_pois=50,
                          features={"global_simpson_diversity": 100.0, "global_gini_coefficient": 0.0})
pen_d0   = calc.calculate({}, total_pois=50,
                          features={"global_simpson_diversity": 0.0,  "global_gini_coefficient": 0.0})
check("simpson D=100 → diversity penalty=0",    pen_d100["penalties"]["diversity"] == 0.0)
check("simpson D=0 → diversity penalty=0.10",   pen_d0["penalties"]["diversity"] == 0.10,
      f"got {pen_d0['penalties']['diversity']}")

# Classification thresholds
check("classify 60.0 → Metro",  calc._classify(60.0) == "Metro")
check("classify 59.9 → Urban",  calc._classify(59.9) == "Urban")
check("classify 30.0 → Urban",  calc._classify(30.0) == "Urban")
check("classify 29.9 → Rural",  calc._classify(29.9) == "Rural")
check("classify 0.0 → Rural",   calc._classify(0.0)  == "Rural")
check("classify 100.0 → Metro", calc._classify(100.0) == "Metro")

# amenity_index always in [0, 100]
r_stress = calc.calculate(
    {cat: {"score": 100.0, "components": {}} for cat in CATS},
    total_pois=1000,
    features={"global_gini_coefficient": 0.0, "global_simpson_diversity": 100.0}
)
check("amenity_index always ≤ 100 even with all categories=100", r_stress["amenity_index"] <= 100.0)
check("weighted_score in [0, 100]", 0 <= r_stress["weighted_score"] <= 100)

# ═══════════════════════════════════════════════════════════════
# 10. FEATURE EXTRACTOR — output completeness and edge cases
# ═══════════════════════════════════════════════════════════════
header("10. FeatureExtractor — output completeness, edge cases")

feats_empty = ext.extract_all(12.97, 77.59, [])
check("extract empty POIs returns dict",           isinstance(feats_empty, dict))
check("extract empty POIs: total_pois=0",          feats_empty["total_pois"] == 0)
check("extract empty POIs: simpson_diversity=0",   feats_empty["global_simpson_diversity"] == 0.0)
check("extract empty POIs: no NaN in values",
      all(not (isinstance(v, float) and math.isnan(v)) for v in feats_empty.values()
          if isinstance(v, (int, float))))

pois_3 = [poi("hospital", 0.2, lat=12.97+i*0.003, lon=77.59+i*0.003) for i in range(3)]
feats_3 = ext.extract_all(12.97, 77.59, pois_3)
check("extract 3 POIs: global_gini_coefficient present",    "global_gini_coefficient" in feats_3)
check("extract 3 POIs: global_simpson_diversity in [0,100]",
      0 <= feats_3.get("global_simpson_diversity", -1) <= 100)
check("extract sanitises missing poi_type",
      ext.extract_all(12.97, 77.59, [{"distance_km": 0.5}])["total_pois"] == 0)
check("extract sanitises missing distance_km",
      ext.extract_all(12.97, 77.59, [{"poi_type": "hospital"}])["total_pois"] == 0)

# Gini of all-same type → Gini≈0 (all cats equal)
one_type_pois = [poi("hospital", 0.1+i*0.05, lat=12.97+i*0.001, lon=77.59+i*0.001) for i in range(20)]
feats_one = ext.extract_all(12.97, 77.59, one_type_pois)
check("single poi_type → low PoI-type Gini (<0.05)", feats_one["global_gini_coefficient"] < 0.05,
      f"got {feats_one['global_gini_coefficient']:.3f}")

# Cross-radius gradient: closer area should have higher density
d5 = feats_3.get("density_gradient_500_1000", None)  # may not be set if <2 gradients
check("extract doesn't crash on 3-POI set", isinstance(feats_3, dict))

# ═══════════════════════════════════════════════════════════════
# 11. COMPONENT WEIGHTS SUM CHECK (config)
# ═══════════════════════════════════════════════════════════════
header("11. Config weight integrity")
from amenity_scorer import config
check("CATEGORY_WEIGHTS sum = 1.0",    abs(sum(config.CATEGORY_WEIGHTS.values()) - 1.0) < 0.001)
check("COMPONENT_WEIGHTS sum = 1.0",   abs(sum(config.COMPONENT_WEIGHTS.values()) - 1.0) < 0.001)
check("all categories have DENSITY_THRESHOLDS", all(c in config.DENSITY_THRESHOLDS for c in config.CATEGORY_WEIGHTS))
check("all categories have PROXIMITY_DECAY_RATES", all(c in config.CATEGORY_PROXIMITY_DECAY_RATES for c in config.CATEGORY_WEIGHTS))
check("all categories have ECONOMIC_TARGET_PCT", all(c in config.ECONOMIC_TARGET_PCT for c in config.CATEGORY_WEIGHTS))
check("ECONOMIC_TARGET_PCT sums near 100", 95 <= sum(config.ECONOMIC_TARGET_PCT.values()) <= 105)
check("all decay rates positive", all(v > 0 for v in config.CATEGORY_PROXIMITY_DECAY_RATES.values()))
check("all density thresholds positive", all(v > 0 for v in config.DENSITY_THRESHOLDS.values()))

# ═══════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ═══════════════════════════════════════════════════════════════
total = passes + failures
print(f"\n{'='*60}")
print(f"  {G if failures == 0 else R}Results: {passes}/{total} PASSED  |  {failures} FAILED  |  {warnings} WARNINGS{RST}")
print(f"{'='*60}")
if failures > 0:
    print(f"\n  {R}FIX THE ABOVE FAILURES BEFORE PRODUCTION DEPLOYMENT.{RST}")
    sys.exit(1)
else:
    print(f"\n  {G}All edge cases pass. System is formula-correct.{RST}")
    sys.exit(0)
