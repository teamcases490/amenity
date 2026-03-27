# Amenity Scoring System

A system for calculating amenity index scores for any location in India based on Points of Interest (POI) data sourced from OpenStreetMap.

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/teamcases490/amenity.git
cd amenity_scorer

# Install dependencies (requires Python 3.9+)
pip install -r amenity_scorer/requirements.txt
```

### Single Location Review

```bash
cd amenity_scorer
python main.py --lat 18.9057 --lon 72.8101
```

### Batch Processing

```bash
cd amenity_scorer
python main.py --input ../data/location.csv --output ../results/amenity_scores --workers 4
```

## How It Works

1. **Fetch POIs**: The system queries OpenStreetMap's Overpass API to fetch amenities within 2km. It caches responses locally to reduce API loads.
2. **Extract Spatial Features**: Extracts statistical features such as distance to nearest service, average proximity of nearest amenities, and density distributions at specific radii.
3. **Algorithm Component Weighting**: Scores each category based on density, proximity, quality, accessibility, spatial clustering, and economic indicators.
4. **Final Aggregation**: Weights the category scores into a final composite index.
5. **Score Adjustments**: Applies penalties for sparse mapping coverage, mono-use areas, or absence of primary essentials like healthcare and transport.
6. **Classification**:
   - **Metro (60-100)**: Dense infrastructure.
   - **Urban (30-59.9)**: Standard or developing area.
   - **Rural (<30)**: Low mapped density or lacking core amenities.

## Proxy Limitations

- **OSM Mapping Bias**: The system evaluates mapped amenities. Areas with sparse OpenStreetMap coverage will score artificially low, even if amenities exist physically.
- **Component Weights**: Category weights align with urban planning proxy targets for India.

## Project Structure

```text
amenity_v2/
├── amenity_scorer/
│   ├── main.py                     # Primary CLI
│   ├── config.py                   # Master definitions & Weights
│   ├── feature_extractor.py        # Feature spatial models
│   ├── category_scorer.py          # Category scoring components
│   ├── amenity_calculator.py       # Final score and penalty adjustments
│   └── poi_fetcher.py              # OSM API and caching
├── data/                           # Source CSV data
├── results/                        # Output JSON/CSVs
├── standalone_amenity_pipeline.ipynb # Single-file executable Jupyter notebook
└── comprehensive_test.py           # CI logic validation
```

