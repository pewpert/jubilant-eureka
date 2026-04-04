# Tokyo Apartment Search — Agent Context

**For new Claude Code sessions: read this file first, then `README.md`.**

This file is the authoritative source of truth for project state, decisions made, and what to do next.
It also doubles as the base case test scenario for the application.

## Maintaining this file
- Update the **Current Status** section at the end of every coding session.
- When a "needs fixing" item is resolved, move it to "What works" and note the date.
- When adding new scripts, commands, or files, add them to the relevant section here AND to `README.md`.
- Keep `README.md` in sync for structural changes (new files, commands, env vars).
- Do not let either file go stale — stale docs cause the next agent to repeat work already done.

---

---

## Project Purpose

A web application that lets users specify apartment search criteria for Tokyo, Japan,
then scrapes and aggregates results from major rental portals (Suumo, Homes, Chintai).

---

## Base Case Search Scenario

Use these criteria to test the application end-to-end:

| Criterion | Value |
|---|---|
| Monthly budget | ¥100,000–¥120,000 (hard ceiling) |
| Layout | 1LDK or 1DK only |
| Size | 25–30 m² preferred; up to 40 m² acceptable |
| Walk to nearest station | ≤ 10 minutes |
| Commute to Shinjuku | ≤ 40 minutes |
| Character | Residential neighbourhood with budget supermarket nearby |
| Tokyo Station access | Important — needed for Shinkansen north |
| Earthquake standard | Prefer post-1981 buildings (新耐震基準) |
| Foreigner acceptance | Note if stated (外国人入居可) |

### In-app form settings for base case
- **Wards**: Suginami, Nakano (start here; expand to Kita, Nerima if needed)
- **Rent**: 10.0–12.0 万円
- **Room type**: 1LDK, 1DK
- **Min size**: 25 m²
- **Walk to station**: within 10 min
- **Building age**: within 40 yrs (to bias toward post-1981)
- **Pages per site**: 3

---

## Key Findings from Manual Research (April 2026)

### Best Zone: Suginami-ku — Shin-Koenji / Koenji corridor

**Why this area works:**
- **Marunouchi Line** (新高円寺 station): Direct to Shinjuku (~14 min) AND Tokyo Station
  (~30 min) with zero transfers — the only single line hitting both hubs
- **JR Chuo Line** (高円寺 station): Shinjuku in ~9 min (Rapid), Tokyo Station ~22 min
- Residential character; multiple budget supermarkets (Gyomu Super, OK Supermarket)
- Good mix of post-1981 buildings at budget-range prices

### Areas not yet searched (potential next steps)
- **Nakano** (中野) — JR Chuo line, slightly cheaper than Koenji; station code `nakano_00758-st`
- **Asagaya** (阿佐ヶ谷) — one stop west of Koenji; quieter; code `asagaya_00760-st`
- **Ogikubo** (荻窪) — end of Marunouchi line + JR Chuo; potentially cheaper
- **Nerima-ku / Itabashi-ku** — further out, verify Shinjuku commute time

---

## Confirmed Listings (April 2026 — seed data)

These 5 listings are pre-loaded as seed data in the database for testing.

| Property | Rent | Mgmt | Layout | m² | Station | Walk | → Shinjuku | → Tokyo Stn | Initial Cost Est. | EQ Standard |
|---|---|---|---|---|---|---|---|---|---|---|
| プラムガーデン | ¥100,000 | +¥3,000 | 1LDK | 30 | 新高円寺 (Marunouchi) | 5 min | ~14 min | ~30 min | ~¥410,000 | ✓ Post-1981 |
| 三井マンション | ¥92,000 | ¥0 | 1LDK | 33 | 新高円寺 (Marunouchi) | 9 min | ~14 min | ~30 min | ~¥248,000 | ⚠️ Pre-1981 |
| エクセレンスハイツ | ¥94,000 | +¥1,000 | 1LDK | 30 | 高円寺 (JR Chuo) | 10 min | ~9 min | ~22 min | ~¥390,000 | ✓ Post-1981 |
| 東交ビル | ¥112,000 | +¥3,000 | 1LDK | 48 | 新高円寺 (Marunouchi) | 3 min | ~14 min | ~30 min | ~¥450,000 | ⚠️ Pre-1981 |
| B・キャッスル十条 | ~¥105,000* | +¥4,000 | 1LDK | 52 | 東十条/十条 (dual) | 6–7 min | ~15 min | ~22 min | ~¥426,000* | ✓ Post-1981 |

*Rent estimated — not confirmed from listing.

### Direct listing links (homes.co.jp — may expire)
- プラムガーデン: https://www.homes.co.jp/chintai/room/ea5b82044b28d7e4f6f95930e49a0b716ae9bf60/
- 三井マンション: https://www.homes.co.jp/chintai/room/1658ec076eb2f71203bdac0ffaa71ccfa7375e67/
- エクセレンスハイツ: https://www.homes.co.jp/chintai/b-31035960093672/
- 東交ビル: https://www.homes.co.jp/chintai/b-1092810076883/
- B・キャッスル十条: https://www.homes.co.jp/chintai/room/b953dff2d373750fd31689dfcbfcb9bbe78e2d3d/

---

## Homes.co.jp Scraper Notes

### Correct URL pattern (station-based)
```
https://www.homes.co.jp/chintai/theme/14130/tokyo/[STATION_CODE]-st/list/?cb=10.0&ct=12.0&mb=25&mt=40&et=10
```

- `theme/14130` = 1LDK special feature filter (important — without this, results are mixed)
- `cb` / `ct` = rent in 万円 units (10.0 = ¥100,000)
- `mb` / `mt` = size in m²
- `et` = max walk to station in minutes

### Correct URL pattern (ward-based fallback)
```
https://www.homes.co.jp/chintai/theme/14130/tokyo/[WARD-NAME]-city/list/?cb=10.0&ct=12.0&mb=25&mt=40&et=10
```
Example: `suginami-city` for Suginami Ward (杉並区), `kita-city` for Kita Ward (北区)

### Known station codes
| Station | Line | Code |
|---|---|---|
| 中野 | JR Chuo / Tozai | `nakano_00758-st` |
| 阿佐ヶ谷 | JR Chuo/Sobu | `asagaya_00760-st` |
| 新高円寺 / 高円寺 | Marunouchi / JR Chuo | Use `suginami-city` ward search |
| 十条 / 東十条 | Saikyo / Keihin-Tohoku | Use `kita-city` ward search |

### Anti-scraping notes
- Homes.co.jp blocks most scrapers. The `?sort=fee` URL param doesn't work — sorting is JS-driven.
- Use Playwright (already configured) with realistic Japanese locale headers.
- If blocked, try adding `Referer: https://www.homes.co.jp` header.

---

## Initial Cost Formula

```
Est. Initial Cost = (deposit_months × rent)
                  + (key_money_months × rent)
                  + (agency_fee = 1 month rent × 1.1)
                  + ¥100,000 misc
```

Misc covers: lock replacement, fire insurance, guarantor company fee.

---

## Japanese Apartment Terminology

| Japanese | Romaji | Meaning |
|---|---|---|
| 1LDK | — | 1 bedroom + Living/Dining/Kitchen (larger living area) |
| 1DK | — | 1 bedroom + Dining/Kitchen (smaller combined space) |
| 敷金 | Shikikin | Refundable security deposit (typically 0–2 months rent) |
| 礼金 | Reikin | Non-refundable "key money" gift to landlord (0–2 months) |
| 仲介手数料 | Chūkai tesūryō | Agency fee (typically 1 month + 10% tax) |
| 管理費 | Kanrihi | Monthly management/maintenance fee |
| 新耐震基準 | Shin-taishin kijun | Post-1981 earthquake standard (current building code) |
| 旧耐震基準 | Kyū-taishin kijun | Pre-1981 earthquake standard (older, higher seismic risk) |
| 外国人入居可 | Gaikokujin nyūkyo ka | Foreigners accepted |

---

## Shinkansen Connectivity from Tokyo Station

| Destination | Line | Est. Travel Time |
|---|---|---|
| Gala Yuzawa (ski) | Joetsu Shinkansen | ~75 min |
| Zao Onsen (ski) | Tohoku Shinkansen → Shiroishi-Zao | ~100 min |
| Appi Kogen (ski) | Tohoku Shinkansen → Hanamaki | ~2.5 hrs |
| Hakkoda (backcountry) | Tohoku Shinkansen → Shin-Aomori | ~3.5–4 hrs |

---

## Output Files

| File | Purpose |
|---|---|
| `workspace/japan_apartment_comparison.html` | HTML comparison table of confirmed listings |
| `scripts/seed_listings.py` | Inserts confirmed listings into DB for testing |

---

## Development Notes

- Branch: `claude/apartment-search-tokyo-Qm6m6`
- Stack: FastAPI + Celery + Redis + Postgres + Next.js 14
- Run: `cp .env.example .env && docker compose up --build`
- API docs: http://localhost:8000/docs
- Frontend (live mode): `cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8000 NEXT_PUBLIC_DEMO_MODE=false npm run dev`
- Frontend (demo mode): `cd frontend && npm run dev`
- Seed DB: `docker compose exec backend python seed_listings.py`
- To add Firecrawl later: set `FIRECRAWL_API_KEY` in `.env`

---

## Current Status (April 4 2026)

### What works
- Full Docker stack runs locally on Mac (Postgres, Redis, FastAPI, Celery worker, Playwright)
- Playwright/Chromium installed at Docker build time (not downloaded at startup)
- Frontend ↔ backend connection confirmed working (CORS fixed for ports 3000–3002)
- Search submits a job and polls for results correctly
- Vercel frontend deployed at: `jubilant-eureka-rho.vercel.app` (demo mode)
- Demo mode shows 5 confirmed seed listings without needing backend
- HTML debug snapshots saved to `/tmp/debug_{source}_p{n}.html` on each scrape run

### What needs fixing (priority order)
1. **Scrapers return zero results** — the pipeline runs end-to-end but no listings are extracted.
   Root cause not yet confirmed; two likely candidates:
   - **CSS selectors are stale** — homes.co.jp changes markup. The selectors were updated
     (April 4) with 7 fallback strategies + attribute wildcards, but haven't been verified
     against live HTML yet.
   - **Sites blocking Playwright** — getting a CAPTCHA/empty page instead of listings.
   **Immediate next step:** run `test_scraper.py` (see Debug section below) and paste output.

2. **Vercel Root Directory** — in the Vercel dashboard go to
   Settings → General → Root Directory → set to `frontend` → Save → Redeploy.
   (Without this, Vercel tries to build from repo root and fails.)

3. **Cloud backend** — backend only runs locally. Railway.app (~$5/mo) is the recommended
   next step for a fully public deployment.

### Debug workflow for zero results

```bash
# Step 1 — pull latest code and restart
cd ~/Desktop/jubilant-eureka
git pull
docker compose down && docker compose up --build -d

# Step 2 — run standalone scraper test (bypasses Celery entirely)
docker compose exec worker python test_scraper.py

# If it prints listings → scraper works, Celery connection is the issue
# If it prints "No listing selector matched" + class list → paste that output,
#   update selectors in backend/app/scrapers/homes.py to match

# Step 3 — inspect raw HTML if needed
docker compose exec worker python debug_html.py

# Step 4 — trigger via API and watch logs
curl -X POST http://localhost:8000/api/search/ \
  -H "Content-Type: application/json" \
  -d '{"wards":["suginami"],"rent_min":10,"rent_max":12,"floor_plans":["1LDK"],"walk_minutes":10,"sources":["homes"],"max_pages":1}'

docker compose logs worker --tail=100 -f
```

### Files added/changed this session (April 4)
| File | Change |
|---|---|
| `backend/test_scraper.py` | **New** — standalone scraper test, bypasses Celery |
| `backend/app/scrapers/homes.py` | Expanded to 7 CSS selector strategies; logs class names on failure |
| `backend/app/scrapers/base.py` | Added 2.5s extra wait after page load for JS hydration |
| `docker-compose.yml` | Removed obsolete `version` attribute |
| `README.md` | **New** — human-readable setup guide |
| `CLAUDE.md` | Added maintenance instructions + refreshed status |
