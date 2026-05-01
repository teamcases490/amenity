# 🐳 Local Overpass API — Complete Setup Guide (India)

Run a **local Overpass API** using Docker so the road-network and amenity pipelines
never hit public rate limits. This is a one-time setup; after the first run the
database persists in a Docker volume and starts in seconds.

---

## 📋 Prerequisites

| Requirement | Details |
|---|---|
| Docker Desktop | Installed, running, and signed in |
| Disk Space | At least **25 GB free** (DB takes ~20 GB after indexing) |
| RAM | At least **8 GB** recommended (16 GB for faster indexing) |
| Python | 3.10+ with project `requirements.txt` installed |

---

## 📥 Step 0 — Download the India OSM PBF File

This is a **one-time download** (~700 MB–1.5 GB depending on version).

**Option A — Browser:**
1. Go to: <https://download.geofabrik.de/asia/india.html>
2. Download **`india-latest.osm.pbf`**
3. Place it in a dedicated folder — for example:
   ```
   C:\overpass\india-latest.osm.pbf
   ```

**Option B — PowerShell:**
```powershell
mkdir C:\overpass
curl -L -o C:\overpass\india-latest.osm.pbf https://download.geofabrik.de/asia/india-latest.osm.pbf
```

> [!IMPORTANT]
> **Geofabrik does NOT offer an `.osm.bz2` file for India.** Only `.osm.pbf`
> is available. The `wiktorn/overpass-api` image cannot read `.pbf` files
> directly, so **you must convert it to `.osm.bz2` first** (Step 1 below).
> This is a known limitation — skipping this step causes a `bunzip2 error`.

---

## 🔄 Step 1 — Convert PBF → osm.bz2

The Docker image requires a compressed XML file (`.osm.bz2`), not the binary PBF
format. Use `osmium` (already inside the Docker image) to convert — no extra
installs needed.

```powershell
cd C:\overpass

docker run --rm `
  -v "${PWD}:/work" `
  wiktorn/overpass-api `
  osmium cat /work/india-latest.osm.pbf -o /work/india.osm.bz2 --overwrite
```

This takes **45-60 minutes** and produces `india.osm.bz2` (~3–4 GB).

Confirm it was created:
```powershell
dir C:\overpass\india.osm.bz2
```
You should see a file larger than 3 GB.

> [!NOTE]
> The conversion only needs to be done once. You can delete `india.osm.bz2`
> after the database is built (Step 2) to reclaim disk space.

---

## 🚀 Step 2 — Initialize the Overpass Database

Run from the folder containing `india.osm.bz2`:

```powershell
cd C:\overpass

docker run -d `
  --name overpass_india `
  -p 12345:80 `
  -e OVERPASS_META=yes `
  -e OVERPASS_MODE=init `
  -e OVERPASS_PLANET_URL=file:///work/india.osm.bz2 `
  -v "${PWD}:/work:ro" `
  -v overpass_india_db:/db `
  wiktorn/overpass-api
```

### What each flag does

| Flag | Purpose |
|---|---|
| `-p 12345:80` | Exposes API at `http://127.0.0.1:12345` |
| `OVERPASS_META=yes` | Stores full metadata (needed for some queries) |
| `OVERPASS_MODE=init` | Builds the database from scratch |
| `OVERPASS_PLANET_URL=file:///work/india.osm.bz2` | Reads the local bz2 file |
| `-v "${PWD}:/work:ro"` | Mounts current folder (read-only) into container |
| `-v overpass_india_db:/db` | Persists database in a named Docker volume |

### Watch progress

```powershell
docker logs -f overpass_india
```

**Phase 1** — File reading (~1–2 min): you will see a curl progress bar reaching 100%.  
**Phase 2** — Database indexing (~30–90 min): logs go quiet. This is normal.  
**Phase 3** — Area generation (~5–10 min): lines like `After 0h1m0s: in "make-area"...`  

Wait until you see:
```
Overpass container initialization complete. Exiting.
```

> [!IMPORTANT]
> The container **exits with code 0** after init. This is expected — it is NOT a crash.
> Verify with: `docker ps -a --filter "name=overpass_india"` → you should see `Exited (0)`.

---

## 🔐 Step 3 — Fix Permissions and Start the API

After init the container has exited. Run these commands to fix internal file
permissions and start the persistent API server:

```powershell
docker start overpass_india
docker exec --user root overpass_india chown -R overpass:overpass /db
docker exec --user root overpass_india chmod -R 755 /db
docker restart overpass_india
```

---

## 🧪 Step 4 — Verify the Setup

```powershell
# Check API status
curl "http://127.0.0.1:12345/api/status"
```

Expected output:
```
Connected as: anonymous
Current time: ...
Rate limit: 0
```

Test a real data query (Mumbai area):
```powershell
curl "http://127.0.0.1:12345/api/interpreter?data=[out:json];node(19.07,72.87,19.08,72.88);out;"
```

You should see `"elements": [...]` with many nodes. If so, **setup is complete**. ✅

---

## ⚙️ Step 5 — Python Configuration

The  pipeline are pre-configured. Verify these settings after cloning:

```python
OSM_OVERPASS_URL = "http://127.0.0.1:12345/api/interpreter"
REQUESTS_PER_SECOND = 0  # No limit needed for local!
```

> [!WARNING]
> **Three critical rules for the Overpass URL with OSMnx:**
>
> 1. Use `127.0.0.1` — NOT `localhost` (Windows may resolve via IPv6 → 403 error)
> 2. Use `.../api` — NOT `.../api/interpreter` (OSMnx 2.x appends `/interpreter` automatically — adding it yourself creates a double path → 404)
> 3. Do NOT add `[date:"..."]` to `overpass_settings` — local instances have no historical data; date filters return empty results

---

## 🔁 Step 6 — Day-to-Day Usage

The database is saved permanently in the `overpass_india_db` Docker volume.
You never need to re-run the init again.

```powershell
# Start before running any pipeline
docker start overpass_india

# Stop when done for the day
docker stop overpass_india
```

---

## 🆕 First-Time Clone Checklist

After cloning the repository, do this before running any pipeline:

- [ ] Docker Desktop is installed and running
- [ ] Downloaded `india-latest.osm.pbf` from Geofabrik
- [ ] Converted PBF → `india.osm.bz2` using the osmium command (Step 1)
- [ ] Ran the `docker run` init command and waited for `initialization complete` (Step 2)
- [ ] Ran the permission-fix commands (Step 3)
- [ ] Verified with `curl http://127.0.0.1:12345/api/status` (Step 4)
- [ ] Deleted OSMnx cache if running after a URL change: `del data\cache\*`
- [ ] Installed Python deps: `pip install -r requirements.txt`

---

## 🐛 Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `bunzip2 error: not a bzip2 file` | Used PBF directly instead of bz2 | Follow Step 1 — convert PBF → bz2 first |
| `HTTP 404` on `/interpreter` | OSMnx URL missing `/api` | Set `overpass_url = "http://127.0.0.1:12345/api"` |
| `HTTP 403 Forbidden` | Using `localhost` on Windows | Use `127.0.0.1` instead |
| All scores = 0.0 | Poisoned OSMnx cache from bad URL | Delete `data/cache/` folder, then re-run |
| All scores = 0.0 | Date filter in `overpass_settings` | Remove `[date:"..."]` — use `[timeout:90]` only |
| Pipeline resumed with zero data | Bad checkpoint file | Delete `processing_checkpoint.pkl`, re-run |
| Container exits immediately | Init still running — this is normal | `docker logs overpass_india` to check |
| `Exited (0)` in docker ps | Init completed successfully | Run the Step 3 permission-fix commands |
| `Exited (1)` in docker ps | Container crashed | `docker logs overpass_india` to diagnose |
| Port 12345 already in use | Another service using that port | Change to `-p 12346:80` and update all configs |
| Disk full during init | DB requires ~20 GB | Free disk space; delete `india.osm.bz2` after init |
| Query returns empty elements | Location is outside India bounds | Check lat/lon coordinates |
