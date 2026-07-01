# TODO — Tokyo Apartment Search

Open items surfaced across sessions. Done items live in CLAUDE.md "Current Status".

## Now / high value
- [ ] **Refresh the Google Maps API key.** It's expired (`maps_directions` returns
      "API key is expired"). Blocks getting *authoritative* transit times. Once
      renewed: replace the hand-interpolated `STATION_TO_HUB` times in
      `backend/app/data/commute.py` with exact Maps transit times in one pass, and
      we could route door-to-door from the building address instead of nearest
      station. Until then commute times are ±1–2 min interpolations.
- [ ] **"All 23 wards" search is a ~5-min serial crawl with no partial results.**
      Empty wards → each JP scraper loops all 23 wards sequentially (~14s/ward for
      Chintai), and nothing shows until every source finishes. Pick a fix:
      cap default wards / stream partial results / better progress UI.
      (Diagnosed; decision pending — see chat.)

## Backlog
- [x] **`is_recently_blocked` dead code** — removed (commit 801674a).
- [x] **`build_search_url` duplication** — consolidated into
      `normalize.common_search_params` (commit 3ca8dce). URLs byte-identical.
- [x] **`test_filters.py`** pytest pollution — fixed via `pytest.ini` testpaths
      (commit 801674a).
- [ ] **Expand commute table further** if searching new wards (Kita/Itabashi north,
      eastern Tokyo). Currently covers the Suginami/Nakano/Setagaya corridor only;
      out-of-area stations show "—". Maps API would make this universal.

## Deploy / ops (not code)
- [ ] **Vercel Root Directory** → set to `frontend` in Settings → General → Redeploy.
- [ ] **Cloud backend** — backend only runs locally. Railway.app (~$5/mo) recommended.

## Known, low priority
- [ ] **Chintai narrow results** — passes few/0 for the tight base case; raw results
      are correctly excluded by post-filter (rent/floor_plan/size). Verify the
      `yen_from/yen_to/madori` URL params are honoured, or just widen test criteria.
- [ ] **Multi-unit buildings show one row per unit** (by design — Daniel chose "keep
      separate rows"). Future: group-by-building in the UI ("4 units, ¥126k–129k").
