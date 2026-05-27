# Tokyo Apartment Search

A web application that aggregates Tokyo rental listings from Suumo, LIFULL HOME'S, and Chintai based on user-specified criteria.

**Live demo (frontend only):** `jubilant-eureka-rho.vercel.app`

---

## What it does

1. User submits search criteria (ward, rent range, room type, walk time, sources,
   and an optional "motorcycle parking only" toggle)
2. Backend enqueues a Celery job
3. Celery worker launches headless Chromium (via Playwright) and scrapes Suumo,
   LIFULL HOME'S, and Chintai concurrently (Suumo falls back to Firecrawl when blocked)
4. Results are filtered (rent/size/walk/age/floor-plan), **deduplicated**, and the
   surviving listings are **enriched** by fetching each detail page for parking
   (motorcycle/bicycle/car), foreigner-OK, and earthquake standard
5. Each listing gets an **offline commute estimate** (walk + train) to Tokyo Station
   and Shinjuku
6. Results are stored in Postgres and returned to the frontend (sortable by rent,
   size, walk, parking, or commute; exportable to CSV)

### Feature implementation map (where each lives)

| Feature | Implementation |
|---|---|
| Multi-source scraping | `backend/app/scrapers/{suumo,homes,chintai}.py`, orchestrated by `manager.py` |
| Suumo block handling | `suumo.py` `_looks_blocked()` + live-first / per-page Firecrawl fallback (`firecrawl.py`) |
| Post-scrape filters | `manager.py` `run_all_scrapers()` (rent/size/walk/building_age/floor_plan) |
| Dedup | `manager.py` — drops TRUE exact-dupes (building+station+rent+size+floor), keeps different units |
| Detail-page enrichment | `base.py` `enrich_listings()` + per-scraper `parse_detail()`; shared parser `detail_features.py` |
| Parking / foreigner / earthquake | `detail_features.py` `parse_detail_features()` → 3-state parking, bool foreigner, new/old EQ |
| Top-N enrichment | `manager.py` `_enrich_filtered()` — cheapest listings enriched first, capped by `max_detail_fetches` |
| Moto-parking filter | `models/search.py` `moto_parking_only` flag → post-enrichment filter in `manager.py` |
| Commute estimate | `backend/app/data/commute.py` `estimate_commute()` (offline station→hub table), attached in `manager.py` |
| Results UI (columns/sort/CSV) | `frontend/src/components/ListingsTable.tsx` |
| Search form (incl. moto toggle) | `frontend/src/components/SearchForm.tsx` |

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), Tailwind CSS |
| Backend API | FastAPI (Python 3.12) |
| Job queue | Celery + Redis |
| Database | PostgreSQL 16 |
| Scraping | Playwright (headless Chromium) + BeautifulSoup |
| Local dev | Docker Compose (5 services) |
| Frontend hosting | Vercel (free tier, demo mode) |

---

## Quick start (local, Docker)

**Prerequisites:** Docker Desktop, Git

```bash
git clone <repo-url>
cd jubilant-eureka
cp .env.example .env          # defaults are fine for local dev
docker compose up --build
```

Services:
- Frontend → http://localhost:3000
- API → http://localhost:8000
- API docs → http://localhost:8000/docs

**First run — seed the database with 5 confirmed listings:**

```bash
docker compose exec backend python seed_listings.py
```

---

## Running without Docker (frontend only)

```bash
cd frontend
npm install
npm run dev        # demo mode on by default — no backend needed
```

Open http://localhost:3000. Shows 5 hardcoded listings from April 2026 research.

To connect to a running backend:

```bash
NEXT_PUBLIC_DEMO_MODE=false NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

---

## Project structure

```
jubilant-eureka/
├── backend/
│   ├── app/
│   │   ├── api/routes/         # FastAPI route handlers
│   │   │   ├── search.py       # POST /api/search, GET /api/search/{id}/status
│   │   │   └── listings.py     # GET /api/listings
│   │   ├── data/
│   │   │   └── commute.py      # Offline station→Tokyo/Shinjuku commute table + estimate_commute()
│   │   ├── db/
│   │   │   ├── database.py     # SQLAlchemy async engine + session
│   │   │   └── models.py       # SearchJob, Listing ORM (incl. parking/EQ/commute columns)
│   │   ├── models/
│   │   │   ├── search.py       # SearchCriteria (incl. enrich_details, max_detail_fetches, moto_parking_only)
│   │   │   └── listing.py      # ListingOut, SearchJobOut, Debug models
│   │   ├── scrapers/
│   │   │   ├── base.py             # BaseScraper (Playwright lifecycle, retry, enrich_listings())
│   │   │   ├── homes.py            # LIFULL HOME'S scraper (+ parse_detail)
│   │   │   ├── suumo.py            # Suumo scraper (+ parse_detail, _looks_blocked, Firecrawl fallback)
│   │   │   ├── chintai.py          # Chintai scraper (+ parse_detail)
│   │   │   ├── detail_features.py  # Shared detail-page parser: parking/foreigner/earthquake
│   │   │   ├── firecrawl.py        # Firecrawl fallback + Redis block-memory/cache
│   │   │   ├── transport.py        # parse_transport(): line/station/walk from text
│   │   │   └── manager.py          # Concurrent scrape, filter, dedup, enrich, commute
│   │   ├── tasks/
│   │   │   ├── celery_app.py   # Celery factory
│   │   │   └── scrape.py       # scrape_apartments Celery task
│   │   ├── config.py           # Settings (reads .env)
│   │   └── main.py             # FastAPI app + CORS config
│   ├── seed_listings.py        # Insert 5 confirmed listings into DB
│   ├── test_scraper.py         # Run scraper directly (bypasses Celery)
│   ├── debug_html.py           # Inspect /tmp/debug_*.html snapshots
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── page.tsx        # Main search page (demo mode aware)
│       │   └── layout.tsx
│       ├── components/
│       │   ├── SearchForm.tsx       # Criteria input form (+ 🏍 moto-parking-only toggle)
│       │   ├── ListingsTable.tsx    # Results table: columns, sort, filters, favorites, CSV/JSON export
│       │   ├── ScrapeDebugPanel.tsx # Per-source raw/passed/excluded debug panel
│       │   ├── ThemeProvider.tsx    # Dark-mode context
│       │   └── ThemeToggle.tsx      # Light/dark toggle
│       └── lib/
│           ├── api.ts          # API client + Listing/SearchCriteria types
│           └── demo-data.ts    # 5 hardcoded seed listings (demo mode)
├── scripts/
│   └── init-db.sql             # Postgres schema init (runs at container start)
├── CLAUDE.md                   # Agent context — read this first
├── docker-compose.yml
└── vercel.json
```

---

## Key commands

```bash
# Reload code after a SCRAPER/PIPELINE change — Celery does NOT hot-reload.
# The API (uvicorn --reload) picks up changes automatically; the worker does not.
docker compose restart worker

# Full rebuild (e.g. after a DB SCHEMA change — there is no migration tooling,
# so new columns require a volume reset). Re-seed afterwards.
docker compose down -v && docker compose up --build
docker compose exec backend python seed_listings.py

# View worker logs (scraper activity)
docker compose logs worker --tail=100 -f

# Trigger a search via API (incl. enrichment + moto-parking-only)
curl -X POST http://localhost:8000/api/search/ \
  -H "Content-Type: application/json" \
  -d '{"wards":["suginami","nakano"],"rent_min":0,"rent_max":14,"size_min_m2":25,
       "walk_minutes":10,"sources":["suumo","homes","chintai"],"max_pages":2,
       "enrich_details":true,"max_detail_fetches":60,"moto_parking_only":false}'

# Check status, then fetch results
curl http://localhost:8000/api/search/<job_id>/status
curl http://localhost:8000/api/search/<job_id>/results
curl http://localhost:8000/api/search/<job_id>/debug   # per-source raw/passed/excluded

# If Suumo skips the live attempt, clear the stale block flag (Redis survives down -v):
docker compose exec redis redis-cli DEL blocked:suumo
```

---

## Environment variables

Copy `.env.example` to `.env`. For local dev all defaults work as-is.

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_DB` | `tokyo_apartments` | Database name |
| `POSTGRES_USER` | `appuser` | DB user |
| `POSTGRES_PASSWORD` | `apppassword` | DB password |
| `PROXY_URL` | _(empty)_ | HTTP proxy for scraper (optional) |
| `FIRECRAWL_API_KEY` | _(empty)_ | **Active** — Firecrawl fallback for Suumo when blocked. Without it, Suumo returns little/nothing when its live site is throttled. |
| `NEXT_PUBLIC_DEMO_MODE` | `true` | Set to `false` to use live backend |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL from frontend |

---

## Current status

See `CLAUDE.md` for detailed current status, known issues, and next steps. That file is kept up to date as the project evolves.

---

## Working in VS Code — Git workflow

VS Code edits your **local folder** (`~/Desktop/jubilant-eureka`). You need to pull from GitHub before starting and push after finishing to keep everything in sync.

**Before you start coding:**
```bash
cd ~/Desktop/jubilant-eureka
git pull origin claude/apartment-search-tokyo-Qm6m6
```

**After making changes in VS Code:**

Option A — terminal:
```bash
git add .
git commit -m "describe what you changed"
git push origin claude/apartment-search-tokyo-Qm6m6
```

Option B — VS Code Source Control panel (left sidebar, branch icon):
1. Click the `+` next to changed files to stage them
2. Type a commit message in the box at the top
3. Click **Commit**, then **Sync Changes** (or **Push**)

**Check which branch you're on:**
```bash
git branch
```
Should show `* claude/apartment-search-tokyo-Qm6m6`. If not:
```bash
git checkout claude/apartment-search-tokyo-Qm6m6
```

**VS Code tip:** install the **GitLens** extension — it shows you the current branch and sync status in the status bar at the bottom of the window at all times.

---

## Maintaining this README

**When to update this file:**
- New scripts or commands are added
- Project structure changes (new files/directories)
- Setup steps change
- Environment variables are added or renamed

Keep it accurate — a wrong README is worse than none.
