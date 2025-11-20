# Django + OSRM Routing

Self-hosted OSRM (MLD, Iran extract) + Django backend for geocoding and routing, with a minimal OpenLayers frontend.

## Prerequisites
- Docker Desktop (Windows/macOS/Linux)
- Python 3.11+ (optional, if running Django locally)

## Quick Start

1) Create backend/.env

```bash
mkdir -p backend
cat > backend/.env <<'EOF'
SECRET_KEY=dev-secret
DEBUG=1
ALLOWED_HOSTS=*
OSRM_BASE_URL=http://osrm:5000
NOMINATIM_BASE_URL=https://nominatim.openstreetmap.org
HTTP_TIMEOUT_S=10
CACHE_TTL_S=300
USER_AGENT="route-app/1.0 (contact: your-email@example.com)"
NOMINATIM_EMAIL=your-email@example.com
EOF
```

2) Build OSRM dataset (one-time)

- Windows (Git Bash)

```bash
cd osrm
mkdir -p data
curl -L https://download.geofabrik.de/asia/iran-latest.osm.pbf -o data/iran.osm.pbf

# 1) Disable Git Bash path conversion for this shell
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

# 2) Use absolute Windows path for the mount (-v)
docker run --rm -t -v "/d/code/route/osrm/data:/data" osrm/osrm-backend:latest \
  osrm-extract -p /opt/car.lua /data/iran.osm.pbf

docker run --rm -t -v "/d/code/route/osrm/data:/data" osrm/osrm-backend:latest \
  osrm-partition /data/iran.osrm

docker run --rm -t -v "/d/code/route/osrm/data:/data" osrm/osrm-backend:latest \
  osrm-customize /data/iran.osrm

cd ..
```

- Linux/macOS

```bash
cd osrm
mkdir -p data
curl -L https://download.geofabrik.de/asia/iran-latest.osm.pbf -o data/iran.osm.pbf

docker run --rm -t -v "$(pwd)/data:/data" osrm/osrm-backend:latest \
  osrm-extract -p /opt/car.lua /data/iran.osm.pbf

docker run --rm -t -v "$(pwd)/data:/data" osrm/osrm-backend:latest \
  osrm-partition /data/iran.osrm

docker run --rm -t -v "$(pwd)/data:/data" osrm/osrm-backend:latest \
  osrm-customize /data/iran.osrm

cd ..
```

3) Start services

```bash
docker compose up -d osrm
docker compose up -d django
```

4) Open the app

Visit `http://localhost:8000`.

- Type an origin (e.g., 'Tehran Sa'adat Abad') and four destinations (e.g., four delivery stops).
- Click **Rank destinations** to calculate OSRM distances and view the ordered list (nearest -> farthest) with distance/time.

## Endpoints
- `GET /api/geocode?q=...&limit=5` - uses Nominatim to return candidates
- `GET /api/route?origin=lat,lon&destination=lat,lon&profile=car&overview=full` - queries OSRM and returns GeoJSON route and summary
- `POST /api/rank-destinations` - accepts an origin plus four destinations and responds with the ranking (distance + duration) derived from OSRM routes.

## Configuration
Environment variables (see `backend/backend/settings.py`):
- `OSRM_BASE_URL` (default `http://osrm:5000`)
- `NOMINATIM_BASE_URL` (default `https://nominatim.openstreetmap.org`)
- `USER_AGENT` (please set to your contact for Nominatim usage policy)
- `NOMINATIM_EMAIL` (optional but recommended when calling the public Nominatim instance)

Optional (timeouts, cache TTL, etc.) can be set via `.env` in `backend/`.

## Development (local Django without Docker)
```bash
cd backend
python -m venv venv
venv\Scripts\activate # on Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```
Ensure OSRM is running (via `docker compose up osrm`) and `OSRM_BASE_URL` points to it.

## Testing
```bash
cd backend
pytest -q
```

## Notes
- OSRM data will be stored in `osrm/data`. Re-run `make all` to refresh.
- Respect Nominatim's usage policy: add a valid `USER_AGENT`, set `NOMINATIM_EMAIL`, and avoid aggressive polling or consider hosting your own Nominatim instance.

### Optional: Using make (if installed)
If you have GNU Make, you can simplify step 2:
```bash
cd osrm
make all   # download + extract + partition + customize
cd ..
```
