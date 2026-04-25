# Amenity Scoring System

Calculates an India-calibrated amenity index (0–100) for any location using OpenStreetMap POI data.

---

### 🐳 High-Performance Mode (Recommended)
For large-scale batch processing, we recommend setting up a local Overpass API instance.
See **[DOCKER_SETUP.md](./DOCKER_SETUP.md)** for instructions.

---

## Setup (Windows)

**Requirement:** Python 3.9+

Run once from the project root:
```
setup.bat
```
This creates the virtual environment and installs all dependencies.

---

## Running

All commands are run from the `amenity_scorer/` directory with the venv active.

**Activate venv first (every new terminal session):**
```
venv\Scripts\activate
set PYTHONIOENCODING=utf-8
```

**Single location:**
```bash
cd amenity_scorer
python main.py --lat 18.9057 --lon 72.8101
```

**Batch processing** (CSV must have `lat` and `lon` columns):
```bash
cd amenity_scorer
python main.py --input ../data/location.csv --output ../results/amenity_scores --workers 2
```
If a batch run is interrupted, re-run the same command — already-processed rows are skipped automatically.

---

## Validating the Setup

Run the test suite from the project root to confirm everything works:
```bash
python test_suite.py
```
Expected output: `RESULT: ALL TESTS PASSED` (includes a live API call — requires internet).

---

## Output Files

| File | Contents |
|---|---|
| `amenity_scores.csv` | One row per location, all scores |
| `amenity_scores.json` | Full hierarchical detail per location |
| `amenity_scores.jsonl` | Line-delimited JSON, appended live |

---

## Score Classification

| Score | Label |
|---|---|
| 60 – 100 | Metro |
| 30 – 59 | Urban |
| 0 – 29 | Rural |

---

## Notes

- Scores reflect OSM mapping coverage. Areas with sparse OSM data will score lower regardless of physical amenities present.
- The `cache/` directory stores API responses for 7 days. Delete it to force a fresh fetch.
- For large batches (100k+ points), use `--workers 2` and run overnight to stay within Overpass API fair-use limits (~1 req/s per IP).

