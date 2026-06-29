"""
Suumo (suumo.com) scraper.

Suumo is Japan's largest rental portal. Key characteristics:
  - Server-side rendered search results (SSR) — HTML is mostly static,
    which is actually good for us (no need to wait for React hydration).
  - Anti-bot: Cloudflare + rate limiting. We work around it with:
      * Realistic User-Agent & headers (set in base)
      * navigator.webdriver spoofing (set in base)
      * Random delays between pages
      * Respecting the pagination structure (don't jump URLs randomly)
  - Listings are rendered as "cassette" cards (.cassetteitem).
  - Each cassette = one building, which can have multiple room rows.

URL structure:
  https://suumo.jp/jj/chintai/ichiran/FR301FC001/
    ?ar=030          ← Kanto area
    &bs=040          ← Rental
    &ta=13           ← Tokyo prefecture
    &sc=13113        ← Ward code (repeatable)
    &cb=8.0          ← Min rent in 万円 (8.0 = ¥80,000)
    &ct=20.0         ← Max rent in 万円
    &mb=20           ← Min size m²
    &mt=9999999      ← Max size m²
    &et=10           ← Max walk to station (minutes)
    &cn=10           ← Max building age (years)
    &md=04&md=07     ← Room types (04=1LDK, 07=2LDK, etc.)
    &page=2          ← Pagination

Floor plan codes:
  01=1R, 02=1K, 03=1DK, 04=1LDK, 05=2K, 06=2DK,
  07=2LDK, 08=3K, 09=3DK, 10=3LDK, 11=4K+
"""

import re
import logging
from urllib.parse import urlencode

from playwright.async_api import Page
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper
from app.scrapers.transport import parse_transport
from app.scrapers.detail_features import parse_detail_features
from app.scrapers.normalize import (
    parse_yen as _parse_yen,
    parse_size as _parse_size,
    parse_walk as _parse_walk,
    parse_floor as _parse_floor,
    parse_building_age as _parse_building_age,
)
from app.scrapers.contract import RawListing
from app.models.search import SearchCriteria, FloorPlan, WalkMinutes

logger = logging.getLogger(__name__)

SUUMO_BASE = "https://suumo.jp/jj/chintai/ichiran/FR301FC001/"

FLOOR_PLAN_CODES = {
    FloorPlan.R1: "01",
    FloorPlan.K1: "02",
    FloorPlan.DK1: "03",
    FloorPlan.LDK1: "04",
    FloorPlan.K2: "05",
    FloorPlan.DK2: "06",
    FloorPlan.LDK2: "07",
    FloorPlan.K3: "08",
    FloorPlan.DK3: "09",
    FloorPlan.LDK3: "10",
    FloorPlan.LDK4_PLUS: "11",
}


# Phrases Suumo serves on its various block / error / rate-limit pages. Suumo
# uses several depending on the kind of throttling, so we match a set rather
# than one string. Seen in the wild:
#   "アクセス集中に関するお詫び"   — explicit rate-limit apology page
#   "ページを表示できません"        — generic "cannot display page" block
#   "アクセスが集中"               — variant wording
_BLOCK_PHRASES = (
    "アクセス集中に関するお詫び",
    "ページを表示できません",
    "アクセスが集中",
    "現在アクセスしにくい状況",
)


def _looks_blocked(html: str | None) -> bool:
    """
    True if the HTML is a Suumo block/error page rather than real results.

    A genuine results page always contains the `.cassetteitem` listing card
    marker. We treat the page as blocked if that marker is absent AND either a
    known block phrase is present or the page is suspiciously small. Checking
    for cassetteitem first avoids false positives on real pages that happen to
    contain a block phrase somewhere (e.g. in a help link).
    """
    if not html:
        return True
    if "cassetteitem" in html:
        return False
    if len(html) < 3000:
        return True
    return any(phrase in html for phrase in _BLOCK_PHRASES)


class SuumoScraper(BaseScraper):
    source_name = "suumo"

    def is_blocked(self, html: str | None) -> bool:
        """Delegate to Suumo's marker-aware block detector."""
        return _looks_blocked(html)

    async def scrape(self):
        """
        Warm up with a homepage visit, then fetch each page via the shared
        live-first→Firecrawl `fetch_page` primitive (see BaseScraper).

        The previous bespoke live/Firecrawl loop now lives in the base class so
        every scraper shares it; Suumo only contributes its homepage warmup and
        its marker-aware `is_blocked`. Pagination uses a string-based next check
        so it works whether the HTML came from the live page or Firecrawl.
        """
        import asyncio as _asyncio
        from app.scrapers.firecrawl import is_recently_blocked

        # Telemetry only — no longer changes control flow.
        if await is_recently_blocked(self.source_name):
            logger.info("[suumo] Note: Suumo recently served a block page; trying live first anyway")

        context = await self._new_context()
        page = await self._new_page(context)
        try:
            logger.info("[suumo] Warming up via homepage…")
            try:
                await page.goto("https://suumo.jp/chintai/tokyo/", wait_until="domcontentloaded")
                await _asyncio.sleep(3)
            except Exception as exc:
                logger.warning("[suumo] Warmup failed (non-fatal): %s", exc)

            for page_num in range(1, self.criteria.max_pages + 1):
                url = self.build_search_url(page_num)
                logger.info("[suumo] Scraping page %d → %s", page_num, url)

                html = await self.fetch_page(page, url)
                if html is None:
                    if page_num == 1:
                        self.blocked = True
                    break

                listings = self._parse_html(html)
                logger.info("[suumo] Page %d → %d listings", page_num, len(listings))
                for listing in listings:
                    listing["source"] = self.source_name
                    yield listing

                if not listings or not self._has_next_in_html(html):
                    break
        finally:
            if context is not None:
                await context.close()

    def _has_next_in_html(self, html: str) -> bool:
        """Suumo shows a 次へ (next) link when more pages exist."""
        return "次へ" in (html or "")

    def build_search_url(self, page_num: int = 1) -> str:
        c = self.criteria
        params: list[tuple[str, str]] = [
            ("ar", "030"),   # Kanto
            ("bs", "040"),   # Rental
            ("ta", "13"),    # Tokyo
        ]

        # Ward codes (can repeat the param key)
        for code in c.ward_codes():
            params.append(("sc", code))

        if c.rent_min > 0:
            params.append(("cb", str(c.rent_min)))
        if c.rent_max < 9999:
            params.append(("ct", str(c.rent_max)))
        if c.size_min_m2 > 0:
            params.append(("mb", str(int(c.size_min_m2))))
        if c.size_max_m2 < 9999:
            params.append(("mt", str(int(c.size_max_m2))))
        if c.walk_minutes.value < 9999:
            params.append(("et", str(c.walk_minutes.value)))
        if c.building_age_max < 9999:
            params.append(("cn", str(c.building_age_max)))

        # Room types
        if c.floor_plans:
            for fp in c.floor_plans:
                params.append(("md", FLOOR_PLAN_CODES[fp]))

        if page_num > 1:
            params.append(("page", str(page_num)))

        # Encode manually to allow duplicate keys
        qs = "&".join(f"{k}={v}" for k, v in params)
        return f"{SUUMO_BASE}?{qs}"

    def _parse_html(self, html: str) -> list[dict]:
        """Parse raw Suumo HTML (used by both Playwright path and Firecrawl fallback)."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        for cassette in soup.select(".cassetteitem"):
            # Building-level info (shared by all units in this card).
            # NOTE: Suumo's real CSS classes use UNDERSCORES in the prefix
            # (.cassetteitem_detail-col1), not hyphens. The header title block
            # (.cassetteitem_content-title) holds "line station floors age", so
            # we use it as a fallback name and parse transport from col2.
            building_name = self._text(cassette, ".cassetteitem_content-title")
            address = self._text(cassette, ".cassetteitem_detail-col1")
            age_text = self._text(cassette, ".cassetteitem_detail-col3")
            building_type = None
            image_tag = cassette.select_one(".cassetteitem_object-item img, .cassetteitem-object-img img")
            image_url = (image_tag.get("rel-lazy") or image_tag.get("src")) if image_tag else None

            # Station + line + walk from the transport column (col2). It packs
            # several "線/駅 歩N分" segments separated by whitespace; pick the
            # closest (smallest walk). parse_transport handles one segment.
            line, station, walk = None, None, None
            transport_el = cassette.select_one(".cassetteitem_detail-col2")
            if transport_el:
                raw = transport_el.get_text(" ", strip=True)
                # Split into one segment per station: each starts at a "線" name
                # and ends after "歩N分". Regex captures "…/駅 歩N分" chunks.
                segments = re.findall(r"[^\s].*?歩\s*\d+\s*分", raw) or [raw]
                best: tuple[int, str | None, str | None] | None = None
                for seg in segments:
                    ln, st, wk = parse_transport(seg)
                    if wk is not None and (best is None or wk < best[0]):
                        best = (wk, ln, st)
                if best:
                    walk, line, station = best

            age_years, built_year = _parse_building_age(age_text)

            # Unit rows. Layout varies:
            #   Live Suumo: each .cassetteitem_other is one unit (7 td cells).
            #   Firecrawl HTML: one .cassetteitem_other contains multiple <tr>, each a unit (9 cells).
            # Collect candidate rows from both shapes.
            candidate_rows: list = []
            for other in cassette.select(".cassetteitem_other"):
                trs = [tr for tr in other.select("tr") if tr.select("td")]
                if trs:
                    candidate_rows.extend(trs)
                else:
                    candidate_rows.append(other)

            for row in candidate_rows:
                cells = row.select("td")
                if not cells:
                    continue

                # Detect layout by probing cell contents. The 9-cell Firecrawl layout has
                # '万円' in cell 3; the 7-cell live layout has '万円' in cell 1.
                cell_texts = [c.get_text(" ", strip=True) for c in cells]
                if len(cells) >= 9 and "万円" in cell_texts[3]:
                    floor_text = cell_texts[2]
                    # Cell 3: "10.7万円 8000円" → rent + fee in one cell
                    price_text = cell_texts[3]
                    rent_text = price_text
                    fee_m = re.search(r"万円\s+([\d,]+\s*円)", price_text)
                    fee_text = fee_m.group(1) if fee_m else None
                    # Cell 4: "- 10.7万円" → deposit + key_money
                    dep_text = cell_texts[4]
                    dep_parts = re.findall(r"[-\d.万円,]+", dep_text)
                    deposit_text = dep_parts[0] if dep_parts else None
                    key_money_text = dep_parts[1] if len(dep_parts) > 1 else None
                    # Cell 5: "1SK 32.26m²" — floor plan + size combined
                    combo = cell_texts[5]
                    fp_m = re.search(r"(\dR|\d[SLK]?[LDK]+|\dK)", combo)
                    floor_plan_text = fp_m.group(1) if fp_m else None
                    size_text = combo
                else:
                    floor_text = self._cell_text(cells, 0)
                    rent_text = self._cell_text(cells, 1)
                    fee_text = self._cell_text(cells, 2)
                    deposit_text = self._cell_text(cells, 3)
                    key_money_text = self._cell_text(cells, 4)
                    floor_plan_text = self._cell_text(cells, 5)
                    size_text = self._cell_text(cells, 6)

                detail_link = row.select_one("a.js-cassette_link_href") or row.select_one("a[href*='/chintai/']")
                if detail_link and detail_link.get("href"):
                    href = detail_link["href"]
                    detail_url = href if href.startswith("http") else f"https://suumo.jp{href}"
                else:
                    detail_url = ""

                floor_num, total_floors = _parse_floor(floor_text)

                results.append(RawListing(
                    source_url=detail_url,
                    source=self.source_name,
                    title=building_name or "",
                    building_name=building_name,
                    rent=_parse_yen(rent_text),
                    management_fee=_parse_yen(fee_text),
                    deposit=_parse_yen(deposit_text),
                    key_money=_parse_yen(key_money_text),
                    address=address,
                    ward=None,  # derived from ward code in manager
                    nearest_station=station,
                    nearest_line=line,
                    walk_minutes=walk,
                    floor_plan=floor_plan_text,
                    size_m2=_parse_size(size_text),
                    floor=floor_num,
                    total_floors=total_floors,
                    building_age_years=age_years,
                    built_year=built_year,
                    building_type=building_type,
                    image_url=image_url,
                ).to_dict())

        return results

    async def parse_detail(self, page: Page, url: str, built_year: int | None = None) -> dict:
        """Fetch a listing detail page and extract parking / amenity flags."""
        await self._goto_with_retry(page, url)
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        return parse_detail_features(soup.get_text(separator=" "), built_year)

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _text(parent, selector: str) -> str | None:
        el = parent.select_one(selector)
        return el.get_text(strip=True) if el else None

    @staticmethod
    def _cell_text(cells: list, index: int) -> str | None:
        if index < len(cells):
            return cells[index].get_text(strip=True) or None
        return None
