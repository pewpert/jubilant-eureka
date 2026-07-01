"""
e-housing.jp scraper.

e-housing is an English-first, expat-focused Tokyo rental aggregator. It is the
odd one out among our sources and the easiest to parse reliably:

  - Tech: Next.js, SERVER-RENDERED. The search results are embedded in the
    initial HTML as React Server Component (RSC) streaming chunks
    (`self.__next_f.push([1,"...json..."])`). We decode those chunks and read the
    listing objects straight out of the JSON — no DOM scraping, no JS execution
    or hydration wait needed for the search page.
  - Each property object is already structured: rent_amount (yen int), size_sqm,
    layout, bed_rooms, deposit/key_money, lat/long, ward, multilingual building
    and station names, and per-station walking distance. So unlike the JP portals
    we don't regex free-form Japanese text — we map fields directly.
  - It re-aggregates other portals (uses English building names). That makes
    cross-source dedup matter; the manager's coordinate-based fuzzy dedup uses the
    lat/long we capture here.

Detail pages (/properties/{slug}) are NOT server-rendered — their amenity values
load via XHR after hydration — so we do NOT enrich from them. Parking stays
"unknown" (the moto-parking filter already treats that as "not stated"). The
list page already gives us everything else, so e-housing needs no detail fetch.

Search URL (verified live 2026-06-28):
  https://e-housing.jp/rent
    ?wards=11&wards=10        ← e-housing numeric ward ids (repeatable) — NOT Suumo codes
    &price_from=100000        ← rent in YEN
    &price_to=120000
    &area_from=25             ← size m²
    &area_to=40
    &walking_distance_to=10   ← max walk minutes
    &layout=1LDK,1DK          ← layouts, COMMA-joined (repeated/[] forms reset to all)
    &page=2
"""

import re
import json
import logging
from typing import AsyncIterator

from playwright.async_api import Page

from app.scrapers.base import BaseScraper
from app.scrapers.contract import RawListing
from app.scrapers.normalize import common_search_params
from app.models.search import SearchCriteria, FloorPlan

logger = logging.getLogger(__name__)

EHOUSING_BASE = "https://e-housing.jp/rent"
EHOUSING_ORIGIN = "https://e-housing.jp"

# e-housing's own numeric ward ids (≠ Suumo ward codes). 16 of 23 wards exist —
# central/popular only; the rest (Adachi, Edogawa, Katsushika, Arakawa, Sumida,
# Taito, Nerima) aren't on e-housing and are skipped with a log line.
EHOUSING_WARD_IDS: dict[str, int] = {
    "minato": 1,
    "shibuya": 2,
    "shinjuku": 3,
    "meguro": 4,
    "setagaya": 5,
    "chuo": 6,
    "bunkyo": 7,
    "chiyoda": 8,
    "shinagawa": 9,
    "nakano": 10,
    "suginami": 11,
    "ota": 12,
    "toshima": 13,
    "koto": 14,
    "kita": 18,
    "itabashi": 21,
}

# Our FloorPlan enum → e-housing's layout token. e-housing uses the same
# "1LDK"/"1DK" notation; "4LDK+" maps to "4LDK".
FLOOR_PLAN_LAYOUTS = {
    FloorPlan.R1: "1R",
    FloorPlan.K1: "1K",
    FloorPlan.DK1: "1DK",
    FloorPlan.LDK1: "1LDK",
    FloorPlan.K2: "2K",
    FloorPlan.DK2: "2DK",
    FloorPlan.LDK2: "2LDK",
    FloorPlan.K3: "3K",
    FloorPlan.DK3: "3DK",
    FloorPlan.LDK3: "3LDK",
    FloorPlan.LDK4_PLUS: "4LDK",
}


def _decode_rsc(html: str) -> str:
    """
    Concatenate and JSON-unescape every `self.__next_f.push([1,"..."])` chunk into
    one decoded blob. Next.js streams the page payload as a sequence of these
    escaped-string chunks; joining them reconstructs the full RSC text.
    """
    blob = ""
    for chunk in re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.DOTALL):
        try:
            blob += json.loads('"' + chunk + '"')
        except Exception:
            blob += chunk
    return blob


def _extract_property_objects(blob: str) -> list[dict]:
    """
    Pull each property record out of the decoded RSC blob.

    A real property record reliably contains the substring
    `"rent_amount":<digits>,"slug":"` (the i18n label dict that also has a
    "rent_amount" key has a STRING value, so it never matches the digit anchor).
    We anchor on that, then expand to the enclosing `{...}` by brace-matching
    backward then forward. Brace-walking from a bare key would grab a nested
    object (e.g. name_langs); anchoring on the rent_amount+slug PAIR lands us
    inside the property object every time.
    """
    objects: list[dict] = []
    for m in re.finditer(r'"rent_amount":\s*\d+,\s*"slug":"', blob):
        anchor = m.start()
        # Walk backward to the record's opening brace.
        depth = 0
        start = None
        for j in range(anchor, -1, -1):
            ch = blob[j]
            if ch == "}":
                depth += 1
            elif ch == "{":
                if depth == 0:
                    start = j
                    break
                depth -= 1
        if start is None:
            continue
        # Walk forward to the matching close brace.
        depth = 0
        end = None
        for k in range(start, len(blob)):
            if blob[k] == "{":
                depth += 1
            elif blob[k] == "}":
                depth -= 1
                if depth == 0:
                    end = k
                    break
        if end is None:
            continue
        try:
            obj = json.loads(blob[start:end + 1])
        except Exception:
            continue
        if "rent_amount" in obj and "slug" in obj:
            objects.append(obj)
    return objects


def _lang(d: dict | None, *keys: str) -> str | None:
    """Pull a value from a *_langs dict, preferring the given keys in order."""
    if not isinstance(d, dict):
        return None
    for k in keys:
        v = d.get(k)
        if v:
            return v
    return None


def _nearest_station(train_stations: list) -> tuple[str | None, str | None, int | None]:
    """
    Return (station_ja, line_ja, walk_minutes) for the CLOSEST station.

    Station name uses the Japanese form so it matches the offline commute table's
    keys. Walk distance is meta_data.pivot_walking_distance_minutes.
    """
    best: tuple[int, str | None, str | None] | None = None
    for st in train_stations or []:
        if not isinstance(st, dict):
            continue
        md = st.get("meta_data") or {}
        walk = md.get("pivot_walking_distance_minutes")
        if walk is None:
            continue
        station = _lang(st.get("name_langs"), "ja", "en") or st.get("name")
        lines = st.get("trainLines") or []
        line = None
        if lines and isinstance(lines[0], dict):
            line = _lang(lines[0].get("name_langs"), "ja", "en") or lines[0].get("name")
        if best is None or walk < best[0]:
            best = (walk, station, line)
    if best is None:
        return None, None, None
    return best[1], best[2], best[0]


class EhousingScraper(BaseScraper):
    source_name = "ehousing"

    # ------------------------------------------------------------------ #
    # URL building                                                         #
    # ------------------------------------------------------------------ #

    def _ward_ids(self) -> list[int]:
        ids: list[int] = []
        for slug in self.criteria.wards:
            wid = EHOUSING_WARD_IDS.get(slug)
            if wid is None:
                logger.info("[ehousing] ward %r not covered by e-housing — skipping", slug)
                continue
            ids.append(wid)
        return ids

    # Rent is in YEN on e-housing (criteria is 万円). 'page' added last after layout.
    _PARAM_NAMES = {
        "rent_min": "price_from", "rent_max": "price_to",
        "size_min": "area_from", "size_max": "area_to", "walk": "walking_distance_to",
    }

    def build_search_url(self, page_num: int = 1) -> str:
        c = self.criteria
        params: list[tuple[str, str]] = [("wards", str(wid)) for wid in self._ward_ids()]
        params += common_search_params(c, self._PARAM_NAMES, rent_in_yen=True)
        if c.floor_plans:
            params.append(("layout", ",".join(FLOOR_PLAN_LAYOUTS[fp] for fp in c.floor_plans)))
        if page_num > 1:
            params.append(("page", str(page_num)))

        qs = "&".join(f"{k}={v}" for k, v in params)
        return f"{EHOUSING_BASE}?{qs}" if qs else EHOUSING_BASE

    # ------------------------------------------------------------------ #
    # Block detection                                                      #
    # ------------------------------------------------------------------ #

    def is_blocked(self, html: str | None) -> bool:
        """
        A real e-housing results page embeds the RSC payload with property
        records. We treat the page as blocked/broken if the payload is missing —
        i.e. there's no `rent_amount` data anchor and no empty-results marker.
        """
        if not html or len(html) < self._MIN_RESULTS_BYTES:
            return True
        if "__next_f" not in html:
            return True
        return False

    # ------------------------------------------------------------------ #
    # Scrape loop                                                          #
    # ------------------------------------------------------------------ #

    async def scrape(self) -> AsyncIterator[dict]:
        """
        One paginated search URL carries all selected wards (repeated `wards`
        param). Fetch each page via the shared resilient primitive, decode the
        RSC payload, yield listings until the embedded total is exhausted.
        """
        if self.criteria.wards and not self._ward_ids():
            logger.warning("[ehousing] none of the selected wards are covered by e-housing — skipping source")
            return

        seen_urls: set[str] = set()
        context = await self._new_context()
        page = await self._new_page(context)

        try:
            for page_num in range(1, self.criteria.max_pages + 1):
                url = self.build_search_url(page_num)
                logger.info("[ehousing] Scraping page %d → %s", page_num, url)

                html = await self.fetch_page(page, url)
                if html is None:
                    if page_num == 1:
                        self.blocked = True
                    break

                listings, has_more = self._parse_with_meta(html)
                logger.info("[ehousing] Page %d → %d listings (has_more=%s)", page_num, len(listings), has_more)

                found_new = False
                for listing in listings:
                    listing["source"] = self.source_name
                    src_url = listing.get("source_url", "")
                    if src_url and src_url in seen_urls:
                        continue
                    if src_url:
                        seen_urls.add(src_url)
                    found_new = True
                    yield listing

                if not listings or not found_new or not has_more:
                    break
        finally:
            await context.close()

    # ------------------------------------------------------------------ #
    # Parsing (pure — testable from a string)                              #
    # ------------------------------------------------------------------ #

    def parse_html(self, html: str) -> list[dict]:
        listings, _ = self._parse_with_meta(html)
        return listings

    def _parse_with_meta(self, html: str) -> tuple[list[dict], bool]:
        """Return (listings, has_more_pages)."""
        blob = _decode_rsc(html or "")
        if not blob:
            return [], False

        objects = _extract_property_objects(blob)
        results = [self._map_property(o) for o in objects]

        # Pagination from propertiesMeta: {"total":N,"per_page":50,"current_page":C,"last_page":L}
        has_more = False
        m = re.search(r'"current_page":\s*(\d+),"last_page":\s*(\d+)', blob)
        if m:
            has_more = int(m.group(1)) < int(m.group(2))
        return results, has_more

    def _map_property(self, o: dict) -> dict:
        slug = o.get("slug") or ""
        source_url = f"{EHOUSING_ORIGIN}/properties/{slug}" if slug else ""

        building_name = _lang(o.get("name_langs"), "en", "ja") or o.get("name")
        address = _lang(o.get("address_langs"), "en", "ja") or o.get("address") or o.get("obscured_address")

        station, line, walk = _nearest_station(o.get("trainStations") or [])

        ward = o.get("ward") if isinstance(o.get("ward"), dict) else {}
        ward_slug = ward.get("slug")

        rent = o.get("rent_amount")
        # discounted_rent_amount comes as a string ("220000") when present.
        disc = o.get("discounted_rent_amount")
        if disc:
            try:
                disc_int = int(disc)
                if 0 < disc_int < (rent or 10 ** 12):
                    rent = disc_int
            except (TypeError, ValueError):
                pass

        return RawListing(
            source_url=source_url,
            source=self.source_name,
            title=building_name or slug or "",
            building_name=building_name,
            rent=int(rent) if rent is not None else None,
            management_fee=_as_int(o.get("management_fee")),
            deposit=_as_int(o.get("security_deposit")),
            key_money=_as_int(o.get("key_money")),
            address=address,
            ward=ward_slug,
            nearest_station=station,
            nearest_line=line,
            walk_minutes=walk,
            latitude=_as_float(o.get("latitude")),
            longitude=_as_float(o.get("longitude")),
            floor_plan=o.get("layout"),
            size_m2=_as_float(o.get("size_sqm")),
            building_type=None,
            image_url=o.get("featured_image_url"),
        ).to_dict()


def _as_int(v) -> int | None:
    try:
        return int(v) if v is not None and str(v) != "" else None
    except (TypeError, ValueError):
        return None


def _as_float(v) -> float | None:
    try:
        return float(v) if v is not None and str(v) != "" else None
    except (TypeError, ValueError):
        return None
