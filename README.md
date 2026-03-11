# Amenity Scoring System (v2.2)

A production-ready, mathematically rigorous system for calculating amenity index scores for any location in India based on Points of Interest (POI) data natively sourced from OpenStreetMap.

## What's New in v2.2?
- **Flawless Mathematical Pipeline**: 109 out of 109 edge-case tests pass, ensuring 100% stable division, bounded indices [0,100], and crash-free handling of zero POIs.
- **Robust Proximity Averaging**: Distance metrics now stabilize strictly on the **5 nearest POIs**, preventing sprawling catchment edges from skewing expected travel times.
- **Accurate Density Saturation**: Multi-radius calculations precisely handle suburban and rural drops without breaking scaling constraints.
- **Penalty Caps**: Extreme penalties (Gini imbalance, lacking diversity) are mathematically capped at 50% to organically differentiate between 'Rural' and 'Uninhabited'.

---

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/amenity_scorer.git
cd amenity_scorer

# Install dependencies (requires Python 3.9+)
pip install -r amenity_scorer/requirements.txt
```

### Single Location Debug

```bash
cd amenity_scorer
python main.py --lat 18.9057 --lon 72.8101
```

### Batch Processing

```bash
cd amenity_scorer
python main.py --input ../data/location.csv --output ../results/amenity_scores --workers 4
```

---

## How It Works

### Step 1: Fetch POIs
The system queries OpenStreetMap's Overpass API to fetch all amenities within **2km**. It uses local JSON caching with a 30-day TTL to prevent API ratelimiting.

**Categories Analyzed** (11 total):
Essential, Healthcare, Education, Transport, Finance, Shopping, Food, Cultural, Premium, Employment, Civic.

### Step 2: Extract Spatial Features
For each location, the system extracts critical mathematical features:
- **Weighted Composite Density**: Measured across 500m (50% weight), 1km (30%), and 2km (20%) radiuses. 
- **Nearest Distance**: Actual Euclidean haversine decay to nearest service.
- **Average Proximity**: Averaged strictly across top-5 closest services.
- **Gini Coefficient**: To detect spatial inequality (e.g., all shops in a single mall vs spread across neighborhoods).
- **Simpson's Diversity**: Identifying mono-use (industrial) vs mixed-use combinations.

### Step 3: Algorithm Component Weighting
Each category scores [0-100] based on 6 core pillars:
- **Density (25%)**
- **Proximity (20%)**
- **Quality (20%)** 
- **Accessibility (15%)** — Inverse-square gravity decay.
- **Spatial (10%)** — Nearest Neighbor distribution metrics.
- **Economic (10%)** — Local vibrancy estimates.

### Step 4: The Final Aggregation
Categories are multiplied by Configured Weights (e.g., Essential=24%, Healthcare=17%, Premium=3%). 

### Step 5: The Penalty System
Additive penalties (max capped at 50%) are applied to prevent "POI Spamming" from artificially inflating scores.
1. **Data Quality**: Sparse mappings (<20 POIs) incur structured penalties.
2. **Gini (Sprawl)**: Highly clustered, car-dependent zones are penalized.
3. **Diversity Guard**: Lack of mixed-use infrastructure drops the score.
4. **Missing Essentials**: Absence of 'Healthcare' or 'Transport' hurts livability deeply.

### Step 6: Final Classification
- **Metro (60-100)**: Exceptionally dense, walkable, mature infrastructure.
- **Urban (30-59.9)**: Standard suburban or developing area.
- **Rural (<30)**: High sprawl, unmapped, or severely lacking essential infrastructure.

---

## Known Proxy Limitations (Important for Production)
While mathematically robust, this is an algorithmic **proxy model**. 
1. **OSM Mapping Bias**: The system evaluates *mapped* amenities. Affluent technical hubs often have 100% of POIs mapped, while hyper-dense low-income areas might have 10% mapped. "Rural" classifications in city centers heavily indicate missing data, not necessarily unlivable environments.
2. **Artificial Structural Tuning**: Component weight distributions (e.g., Proximity vs Density) rely on subjective human tuning aligned with urban planning theory, not machine learning correlations.
3. **Google API Caps**: If migrating from OSM to Google Places API, Google's hard 60-result limit on density queries fundamentally breaks this algorithm's math. Keep OSM or switch to Overture Maps for true spatial density processing.

---

## Project Structure

```text
amenity_v2/
├── amenity_scorer/
│   ├── main.py                     # Primary CLI
│   ├── config.py                   # Master definitions & Weights
│   ├── feature_extractor.py        # 100+ feature spatial models
│   ├── category_scorer.py          # The 6 core Pillars
│   ├── amenity_calculator.py       # The Penalty System
│   └── poi_fetcher.py              # OSM API and caching
├── data/                           # Ignored source CSVs
├── results/                        # Ignored output JSON/CSVs
├── standalone_amenity_pipeline.ipynb # Single-file executable Jupyter notebook
└── comprehensive_test.py           # 109-test CI logic validation
```

---

## License
MIT License
