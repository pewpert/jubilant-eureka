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

## Current Status (April 6 2026)

### What works
- Full Docker stack runs locally on Mac (Postgres, Redis, FastAPI, Celery worker, Playwright)
- **Homes.co.jp scraper confirmed working**: 117 raw listings for Suginami + Nakano, 2 pages
- **Chintai.net scraper confirmed working**: 112 raw listings for same criteria
- Both scrapers iterate all selected wards and dedup by URL
- Post-scrape filter pipeline working: rent, size, walk, building_age, floor_plan all enforced
- Per-source scrape stats tracked through the pipeline (`scrape_stats` JSONB on `search_jobs`)
- Debug endpoint `GET /api/search/{id}/debug` returning per-source breakdown
- `ScrapeDebugPanel` component: collapsible, shows per-source raw/passed/excluded counts
- Frontend redesigned: rose-700 brand, Inter font, Tokyo Rooms header, compact filter bar
- Number input sticky-zero bug fixed (string state approach)
- Max size field added to search form
- Rent min > max validation with inline error
- Ward picker collapsed into a dropdown popover
- `backend/test_filters.py` written — 8 test cases for all filter types
- HTML debug snapshots saved to `/tmp/debug_{source}_p{n}.html` on each scrape run

### Suumo status — IP-blocked (temporary)
Suumo returns their rate-limit page ("アクセス集中に関するお詫び", 1525 bytes) from Docker on this machine.
This is a **temporary IP block** caused by repeated test requests during development.
- The scraper code is correct (same structure as before, warmup visit added)
- It will work from a fresh IP / Railway.app cloud deployment
- Do NOT attempt to repeatedly test Suumo from Docker locally — this extends the block
- Wait ~24h or use a VPN/proxy to test

### What needs fixing (priority order)
1. **Chintai filter mismatch** — Chintai passes 0 listings for base case (rent 10–12万, 1LDK/1DK, Suginami+Nakano). The site returns 112 raw but all excluded by rent (103) + floor_plan (6) + size (3). The URL params `yen_from/yen_to/madori` are sent but the site may not honour them strictly for all result types. Post-filter is correctly excluding them. **This means post-filter IS working but the results are overly narrow — may need to widen criteria in testing, or the filter params need verification.**

2. **Duplicate listings** — base case returns same building multiple times (e.g. 東交ビル ×2, マスコットパレス ×4). The URL-based dedup works within a source but Homes returns multiple units per building as separate dict entries with the same `source_url` (detail link). Need to verify if each unit has a unique URL or if dedup logic needs a composite key.

3. **Vercel Root Directory** — in the Vercel dashboard go to
   Settings → General → Root Directory → set to `frontend` → Save → Redeploy.

4. **Cloud backend** — backend only runs locally. Railway.app (~$5/mo) is the recommended
   next step for a fully public deployment.

### Quick test commands

```bash
# Test Homes + Chintai end-to-end (bypasses Celery)
docker compose exec worker python -c "
import asyncio
from app.models.search import SearchCriteria, Source, FloorPlan, WalkMinutes
from app.scrapers.manager import run_all_scrapers
async def test():
    c = SearchCriteria(wards=['suginami','nakano'], rent_min=10.0, rent_max=12.0,
        size_min_m2=25.0, floor_plans=[FloorPlan.LDK1, FloorPlan.DK1],
        walk_minutes=WalkMinutes.TEN, sources=[Source.HOMES, Source.CHINTAI], max_pages=2)
    listings, stats = await run_all_scrapers(c)
    print(f'raw={stats[\"total_raw\"]} passed={stats[\"total_passed\"]}')
    for src, s in stats['per_source'].items():
        print(f'  [{src}] raw={s[\"raw_count\"]} passed={s[\"passed_count\"]} excl={s[\"excluded_by\"]}')
asyncio.run(test())
"

# Run filter test suite
docker compose exec worker python test_filters.py

# Trigger via API
curl -X POST http://localhost:8000/api/search/ \
  -H "Content-Type: application/json" \
  -d '{"wards":["suginami","nakano"],"rent_min":10,"rent_max":12,"floor_plans":["1LDK","1DK"],"walk_minutes":10,"size_min_m2":25,"sources":["homes","chintai"],"max_pages":2}'
docker compose logs worker --tail=100 -f
```

### Files added/changed (April 5–6 2026)
| File | Change |
|---|---|
| `backend/app/scrapers/chintai.py` | **Full rewrite** — correct URL `/tokyo/area/{ward_code}/list/`, params `yen_from/yen_to/menseki_from/tsukin/madori`, multi-ward iteration, fixed l-table parsing for station/walk/age, cassette_detail tbody unit rows |
| `backend/app/scrapers/homes.py` | Multi-ward iteration via `_build_url_for_ward()`, URL-based dedup, `build_search_url` refactored |
| `backend/app/scrapers/suumo.py` | Homepage warmup visit before search, omit default params (no `et=9999` etc.) |
| `backend/app/scrapers/manager.py` | Per-source stats, building_age post-filter, returns `tuple[list, dict]` |
| `backend/app/tasks/scrape.py` | Unpacks tuple, persists `scrape_stats` |
| `backend/app/db/models.py` | Added `scrape_stats` JSONB column |
| `backend/app/models/listing.py` | Added `ExclusionBreakdown`, `SourceDebugStats`, `DebugResponse`, `scrape_stats` on `SearchJobOut` |
| `backend/app/api/routes/search.py` | Added `GET /{job_id}/debug` endpoint |
| `backend/test_filters.py` | **New** — 8 filter test cases |
| `frontend/src/lib/api.ts` | New debug types + `getJobDebug()` |
| `frontend/src/components/ScrapeDebugPanel.tsx` | **New** — collapsible debug panel |
| `frontend/src/components/ListingsTable.tsx` | Alternating rows, sticky header, rose-700 rent, "View →" links |
| `frontend/src/components/SearchForm.tsx` | String-state inputs, max size field, rent validation, ward popover, rose-700 |
| `frontend/src/app/layout.tsx` | Rose-700 header, 🏯 Tokyo Rooms branding, Inter font |
| `frontend/src/app/page.tsx` | Hero section, debug panel wired in |
| `frontend/tailwind.config.ts` | Inter font variable |
