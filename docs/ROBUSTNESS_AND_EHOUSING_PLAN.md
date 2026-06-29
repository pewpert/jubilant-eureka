# Robustness + e-housing.jp Integration — Implementation Plan

**Status:** IMPLEMENTED 2026-06-29 (all six items). Verified offline against saved fixtures
(18 passing tests); one live end-to-end run still pending (no Docker in the build session).
See CLAUDE.md "Current Status (Jun 29 2026)" for the as-built summary. Written 2026-06-29.
**Scope:** Make the scraping architecture robust enough to add new sites cheaply,
then add e-housing.jp as the first source written against the hardened interface.
**Decisions locked with Daniel:**
- e-housing scope: **full parity** (search + detail-equivalent), **use the free extras**
  (`build_date`→`built_year`, foreigner-friendly). Skip persisting lat/long *as columns*
  for now — but capture it in the raw dict so fuzzy dedup can use it in-memory.
- e-housing parking enrichment: **skipped** — its detail page is client-rendered (amenity
  values load via XHR after hydration; not in SSR HTML). Parking stays `"unknown"`, which
  the moto-parking toggle already treats as "not stated."
- **Top robustness priority: DB migrations (Alembic).** Do this first.

---

## 0. Why this plan exists

Adding a 4th site to the current code means copy-pasting a ~400-line scraper and four
near-identical helper functions, then discovering six latent fault lines the hard way.
This document orders the work so each new site after e-housing is cheap, and so e-housing
itself proves the abstractions hold.

The architecture's **good bones** (keep these):
- One listing-dict shape every scraper emits → downstream (dedup/filter/commute/persist) is
  source-agnostic.
- Column-whitelist insert (`tasks/scrape.py`) → scrapers may emit extra keys safely.
- `gather(..., return_exceptions=True)` per-source isolation → one scraper failing ≠ job fail.

The **fault lines** (this plan addresses them):
1. Block/Firecrawl fallback logic is hardcoded in Suumo; Homes/Chintai each reinvent a
   weaker block check. e-housing would be a 4th copy.
2. `_parse_yen`/`_parse_size`/`_parse_walk` are copy-pasted in every scraper.
3. The scraper-output dict is an implicit contract (convention, not schema).
4. **No DB migrations** — every new column needs `docker compose down -v` (destroys data).
5. Cross-source dedup keys on building-name string; e-housing uses English names for
   re-aggregated Suumo/Homes listings → silent duplicates.
6. Parsing is welded to live Playwright `Page` objects → not unit-testable offline.

---

## 1. PRIORITY 1 — DB migrations with Alembic

**Problem.** CLAUDE.md documents the current reality: any new column requires
`docker compose down -v && up --build` + reseed. That wipes Postgres. Acceptable for 3
controlled sources; unacceptable now that this is being treated as a product and e-housing
introduces new data worth persisting.

**Change.**
- Add `alembic` to `backend/requirements.txt`.
- `alembic init backend/alembic`; point `sqlalchemy.url` at the sync DB URL already derived
  in `tasks/scrape.py` (`+psycopg2`). Wire `target_metadata = Base.metadata` from
  `app.db.database`.
- Generate the **baseline** migration from the current models (autogenerate, then verify it
  matches the live schema — the live DB already has the 8 amenity/commute columns, so the
  baseline must be marked as already-applied via `alembic stamp head` on existing volumes).
- Replace "tables auto-create on boot" with `alembic upgrade head` in the backend entrypoint
  (keep `create_all` only as a dev fallback, or remove it to avoid drift).
- Update CLAUDE.md + README: new column = new migration, not a volume reset.

**Acceptance.** Add a throwaway nullable column via a migration, `alembic upgrade head`,
confirm it appears with **no data loss**. Then revert.

**Risk.** Autogenerate can miss/extra-detect things (JSON columns, server defaults). Verify
the baseline diff by hand against `db/models.py` before committing.

---

## 2. PRIORITY 2 — Lift block/fallback into BaseScraper

**Problem.** Resilience is per-site luck. Suumo has the good live-first→Firecrawl→
`_looks_blocked` loop; Homes/Chintai have weaker inline checks; e-housing needs a *different*
"blocked" signature again (Next.js: missing RSC payload / tiny HTML, not a Japanese phrase).

**Change.** Add to `BaseScraper`:
```python
def is_blocked(self, html: str | None) -> bool: ...        # per-site override; default heuristic
async def fetch_page(self, page, url) -> str | None:        # owns: live → is_blocked → Firecrawl → telemetry
def parse_html(self, html: str) -> list[dict]: ...          # per-site; pure string→dicts (see §5)
```
`fetch_page` centralizes: live `goto` + retry, `is_blocked` check, per-page Firecrawl
fallback, `mark_blocked` telemetry, `/tmp` HTML snapshot. The default `scrape()` loop becomes
`for page in pages: html = fetch_page(...); yield from parse_html(html)`. Suumo's bespoke loop
collapses into overriding `is_blocked` + `parse_html`; the warmup-homepage step stays as a
Suumo override hook.

**Acceptance.** Suumo/Homes/Chintai behavior unchanged (same listing counts on the base
case), but each scraper's `scrape()` override is gone or trivial.

---

## 3. PRIORITY 3 — Typed listing contract + normalization helpers

**Problem.** 20-key dict assembled by hand in each scraper; four copies of yen/size/walk
parsers; a forgotten key is only caught at DB insert.

**Change.**
- `scrapers/normalize.py`: single `parse_yen`, `parse_size`, `parse_walk`, `parse_floor`,
  `parse_building_age`. Delete the per-scraper copies.
- `scrapers/contract.py`: a `RawListing` dataclass (or Pydantic model) with every field +
  safe defaults (`features=[]`, parking=`"unknown"`, etc.) and a `.to_dict()`. Scrapers build
  `RawListing(...)` instead of a bare dict. The contract is the **single source of truth** for
  what a listing is — new fields (lat/long, source_provider) get added here once.
- Keep `to_dict()` output identical to today's dict so the pipeline and column-whitelist insert
  are untouched.

**Acceptance.** All three existing scrapers emit via `RawListing`; base-case listing counts
and field values unchanged.

---

## 4. PRIORITY 4 — Cross-source fuzzy dedup (e-housing forces this)

**Problem.** e-housing re-aggregates Suumo/Homes/etc. and uses **English** building names.
Current dedup key (`building_name + station + rent + size + floor`) won't collapse
"Harmony Residence Nakano" against "ハーモニーレジデンス中野" → the same flat shows twice.

**Change.** Add a second dedup key that doesn't depend on name strings:
`(rent, round(size_m2), floor, round(lat,4), round(lng,4))` when coordinates exist (e-housing
provides them; others don't, so this only fires when at least one side is e-housing and the
other can be matched by rent+size+floor). Keep the existing exact key as the primary; add the
coordinate key as a secondary collapse. **Do not** over-merge: different floors stay separate
(existing, deliberate behavior). Log when a fuzzy-merge fires so it's auditable.

**Acceptance.** A known overlapping listing (find one present on both Suumo and e-housing for
the base case) appears **once** in results, with a log line naming the merge.

**Note.** This needs lat/long in the in-memory dict (not necessarily a DB column). Capture it
in `RawListing` even though we're not persisting it yet (decision: skip the column).

---

## 5. PRIORITY 5 — Parse-from-string + offline fixtures

**Problem.** Parsers are coupled to live `Page` objects → can't unit-test → selector/RSC
regressions are only caught by running a full live scrape.

**Change.**
- Every scraper's `parse_html(html: str) -> list[dict]` is pure (Suumo already half-does this
  with `_parse_html`). Playwright's only job is to fetch the string.
- Save one HTML fixture per site under `backend/tests/fixtures/` (a real saved search page).
- `backend/tests/test_parsers.py`: feed each fixture to its parser, assert expected listing
  count + spot-check fields. e-housing's RSC parser especially needs this (brittle internal
  format).

**Acceptance.** `pytest backend/tests/test_parsers.py` passes offline (no network), covering
all four sites.

---

## 6. Add e-housing.jp scraper (against the hardened interface)

Written **after** §2–§5 so it's the proof the abstractions hold. If sequencing changes to
"ship first," this section still stands alone — it just won't get the shared base-class help.

### 6a. Verified facts (from live probing 2026-06-28)
- **Tech:** Next.js, server-rendered. Listing data is embedded in the initial HTML as RSC
  streaming chunks (`self.__next_f.push([1,"...json..."])`). **No JS execution / DOM wait
  needed** for the *search* page — decode the chunks and parse JSON.
- **Detail page** (`/properties/{slug}`): data is NOT in SSR (numeric rent/build_date/features
  absent); loads via XHR after hydration. → we do not enrich from it (decision).
- **Search URL:** `https://e-housing.jp/rent?<params>`
  | Param | Meaning | Notes |
  |---|---|---|
  | `wards=11&wards=10` | ward (repeatable) | **e-housing's own numeric ids ≠ Suumo codes** |
  | `price_from` / `price_to` | rent in **yen** | |
  | `area_from` / `area_to` | size m² | |
  | `walking_distance_to` | max walk minutes | (`walking_distance` alone does nothing) |
  | `layout=1LDK,1DK` | layout | **comma-joined**; `[]`/repeated forms reset to all |
  | `page=2` | pagination | ~50/page; `propertiesMeta.{total,per_page,current_page,last_page}` in payload |
- **Ward id map** (16 of 23 wards exist; central/popular only — no Adachi/Edogawa/etc.):
  minato=1, shibuya=2, shinjuku=3, meguro=4, setagaya=5, chuo=6, bunkyo=7, chiyoda=8,
  shinagawa=9, nakano=10, suginami=11, ota=12, toshima=13, koto=14, kita=18, itabashi=21.
  (Confirm the remaining wards by listing `{"id":N,"slug":...}` pairs on a full unfiltered page.)
- **Per-listing JSON fields:** `slug`, `name` (+ `name_langs.{en,ja,ko,zh_cn,zh_tw}` — use
  `en`), `address`, `obscured_address`, `rent_amount` (yen int), `management_fee`,
  `security_deposit`, `key_money`, `discounted_rent_amount`, `size_sqm`, `layout`, `bed_rooms`,
  `latitude`, `longitude`, `ward.{id,slug}`, `room_number`, `build_date` (→ `built_year`),
  stations array with `pivot_walking_distance_minutes` + multilingual station/line names,
  `featured_image_url`.
- **Base case** (Suginami+Nakano, ¥100–120k, 1LDK/1DK, ≥25m², ≤10min) → **27 listings**,
  all parsed cleanly.

### 6b. Files to change
| File | Change |
|---|---|
| `backend/app/scrapers/ehousing.py` | **New.** `EhousingScraper(BaseScraper)`: `build_search_url` (yen, comma-layouts, ward-id map), `EHOUSING_WARD_IDS`, `parse_html` (decode RSC → JSON → `RawListing`), `is_blocked` (missing payload / tiny HTML), `has_next_page` (current vs last page from `propertiesMeta`). `parse_detail` inherits base no-op. |
| `backend/app/models/search.py` | Add `Source.EHOUSING = "ehousing"`. |
| `backend/app/scrapers/manager.py` | Register in `SCRAPERS`; `SOURCE_LABELS["ehousing"] = "e-housing.jp"`. |
| `frontend/src/components/SearchForm.tsx` | Add e-housing source checkbox. |
| `frontend/src/lib/api.ts` | Add `"ehousing"` to the source union/type if enumerated. |
| `backend/tests/fixtures/ehousing_rent.html` | Saved search page fixture. |
| `backend/tests/test_parsers.py` | e-housing parse assertions (expect 27 on the base-case fixture). |

### 6c. RSC parsing approach (don't brace-walk)
The reliable method: split the page on `self.__next_f.push([1,"..."])`, JSON-unescape each
chunk, concatenate, then locate property records by their stream segment and `json.loads`
whole arrays — **not** regex `rfind("{")` brace-matching (that grabs nested `name_langs`
objects, proven during probing). Map each record:
- `rent` ← `rent_amount`; `management_fee` ← `management_fee`; deposit/key_money direct.
- `size_m2` ← `size_sqm`; `floor_plan` ← `layout`.
- `built_year` ← parse year from `build_date`; `earthquake_standard` via existing inference.
- `nearest_station`/`walk_minutes` ← station with smallest `pivot_walking_distance_minutes`
  (use `name_langs.ja` for station so it matches the commute table keys).
- `nearest_line` ← that station's line name.
- `source_url` ← `https://e-housing.jp/properties/{slug}`.
- `latitude`/`longitude` ← keep in the dict for fuzzy dedup (not persisted).
- `building_name` ← `name_langs.en`.
- parking fields ← left at defaults (`"unknown"`).

### 6d. Commute-table caveat
The offline commute table (`data/commute.py`) is keyed on Japanese station names and covers
~20 Suginami/Nakano stations. e-housing's stations come with `name_langs.ja` — use that key.
Stations outside the table → `commute_*` = None (no penalty), same as today. Add new station
rows when searching wards beyond the current set.

---

## 7. Suggested execution order

1. **Alembic baseline** (§1) — do first; unblocks safe schema change forever.
2. **Base-class fetch/block** (§2) — highest code-leverage; makes §6 trivial to make resilient.
3. **Contract + normalize** (§3) — small, mechanical, de-risks §6's dict assembly.
4. **Parse-from-string + fixtures** (§5) — enables testing §6 offline.
5. **e-housing scraper** (§6) — written against the clean interface.
6. **Fuzzy dedup** (§4) — last, because it needs e-housing's coordinates to be worth doing.

If the priority later flips to "ship e-housing fast," do §6 in the *current* pattern first
(copy-paste a scraper), then 1→2→3→5→4 as a follow-up; accept temporary duplication.

---

## 8. Out of scope (noted, not planned here)
- e-housing detail-page amenity enrichment (would need JS hydration / reverse-engineering the
  XHR endpoint) — deferred by decision.
- Persisting lat/long / `source_provider` as DB columns — deferred; captured in-memory only.
- A map UI / exact Maps-API commute routing — explicitly declined previously.
- Grouping multi-unit buildings into one UI row — pre-existing backlog item, unrelated.
