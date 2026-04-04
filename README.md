# Tokyo Apartment Search

A web application that aggregates Tokyo rental listings from Suumo, LIFULL HOME'S, and Chintai based on user-specified criteria.

**Live demo (frontend only):** `jubilant-eureka-rho.vercel.app`

---

## What it does

1. User submits search criteria (ward, rent range, room type, walk time to station)
2. Backend enqueues a Celery job
3. Celery worker launches headless Chromium (via Playwright) and scrapes rental portals
4. Results are stored in Postgres and returned to the frontend

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
│   │   ├── db/
│   │   │   ├── database.py     # SQLAlchemy async engine + session
│   │   │   └── models.py       # SearchJob, Listing ORM models
│   │   ├── models/
│   │   │   ├── search.py       # SearchCriteria Pydantic model
│   │   │   └── listing.py      # ListingOut, SearchJobOut Pydantic models
│   │   ├── scrapers/
│   │   │   ├── base.py         # BaseScraper (Playwright lifecycle, retry logic)
│   │   │   ├── homes.py        # LIFULL HOME'S scraper ← active development
│   │   │   ├── suumo.py        # Suumo scraper (selectors need updating)
│   │   │   ├── chintai.py      # Chintai scraper (selectors need updating)
│   │   │   └── manager.py      # Runs all scrapers concurrently
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
│       │   ├── SearchForm.tsx  # Criteria input form
│       │   └── ListingCard.tsx # Individual listing display
│       └── lib/
│           ├── api.ts          # API client (submitSearch, pollUntilDone)
│           └── demo-data.ts    # 5 hardcoded seed listings
├── scripts/
│   └── init-db.sql             # Postgres schema init (runs at container start)
├── CLAUDE.md                   # Agent context — read this first
├── docker-compose.yml
└── vercel.json
```

---

## Key commands

```bash
# Rebuild after code changes
docker compose down && docker compose up --build

# View worker logs (scraper activity)
docker compose logs worker --tail=100 -f

# Test the scraper directly (bypasses Celery — use this to debug zero results)
docker compose exec worker python test_scraper.py
docker compose exec worker python test_scraper.py kita

# Inspect what HTML the scraper actually received
docker compose exec worker python debug_html.py

# Trigger a search via API
curl -X POST http://localhost:8000/api/search/ \
  -H "Content-Type: application/json" \
  -d '{"wards":["suginami"],"rent_min":10,"rent_max":12,"floor_plans":["1LDK"],"walk_minutes":10,"sources":["homes"],"max_pages":1}'

# Check job status
curl http://localhost:8000/api/search/<job_id>/status
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
| `FIRECRAWL_API_KEY` | _(empty)_ | Future: Firecrawl fallback scraper |
| `NEXT_PUBLIC_DEMO_MODE` | `true` | Set to `false` to use live backend |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL from frontend |

---

## Current status

See `CLAUDE.md` for detailed current status, known issues, and next steps. That file is kept up to date as the project evolves.

---

## Maintaining this README

**When to update this file:**
- New scripts or commands are added
- Project structure changes (new files/directories)
- Setup steps change
- Environment variables are added or renamed

Keep it accurate — a wrong README is worse than none.
