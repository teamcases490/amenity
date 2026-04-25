# 🐳 Local Overpass API Setup Guide (India)

This guide explains how to set up a dedicated, high-performance local Overpass API instance using Docker and a local OSM PBF extract.

## 📋 Prerequisites
1. **Docker Desktop** installed and running.
2. **India OSM PBF File**: Download `india-latest.osm.pbf` from [Geofabrik](http://download.geofabrik.de/asia/india.html) and place it in the project root.
3. **Disk Space**: Ensure at least **25 GB** of free space on your `C:` drive.

---

## 🚀 Step 1: Initialize the Container
Run the following command in PowerShell from the project root. This command mounts your local PBF file and converts it automatically.

```powershell
docker run -d `
  --name overpass_india `
  -p 12345:80 `
  -e OVERPASS_META=yes `
  -e OVERPASS_MODE=init `
  -e OVERPASS_PLANET_URL=file:///india.osm.pbf `
  -e OVERPASS_DIFF_URL=https://download.geofabrik.de/asia/india-updates/ `
  -e OVERPASS_PLANET_PREPROCESS="mv /db/planet.osm.bz2 /db/temp.pbf && osmium cat -o /db/planet.osm.bz2 /db/temp.pbf && rm /db/temp.pbf" `
  -v "${PWD}/india-260423.osm.pbf:/india.osm.pbf:ro" `
  -v overpass_india_db:/db `
  wiktorn/overpass-api
```

> [!NOTE]
> This process takes **30–60 minutes** to build the database. You can track progress with: `docker logs -f overpass_india`

---

## 🔐 Step 2: Fix File Permissions
Once the logs say `Overpass container initialization complete. Exiting.`, you must fix the internal permissions so the web server can read the database.

1. **Start the container**:
   ```powershell
   docker start overpass_india
   ```

2. **Run the permission fix**:
   ```powershell
   docker exec --user root overpass_india chown -R overpass:overpass /db
   docker exec --user root overpass_india chmod -R 777 /db
   ```

3. **Restart to apply**:
   ```powershell
   docker restart overpass_india
   ```

---

## 🧪 Step 3: Verify the Setup
Run this command to test if the local API returns data:

```powershell
curl "http://localhost:12345/api/interpreter?data=[out:json];node(13.033,77.602,13.04,77.61);out;"
```
If you see a JSON response with `"elements": [...]`, it is working!

---

## ⚙️ Step 4: Update Python Config
Ensure your `amenity_scorer/config.py` is pointed to the local endpoint:

```python
OSM_OVERPASS_URL = "http://localhost:12345/api/interpreter"
REQUESTS_PER_SECOND = 0  # No limit needed for local!
```
