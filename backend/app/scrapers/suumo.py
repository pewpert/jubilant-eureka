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


def _parse_yen(text: str | None) -> int | None:
    """Convert '8.5万円' or '85,000円' → int yen."""
    if not text:
        return None
    text = text.strip().replace(",", "").replace("\u00a0", "")
    # 万円 format (e.g. 8.5万円)
    m = re.search(r"([\d.]+)\s*万円", text)
    if m:
        return int(float(m.group(1)) * 10000)
    # Plain yen (e.g. 85000円)
    m = re.search(r"(\d+)\s*円", text)
    if m:
        return int(m.group(1))
    return None


def _parse_size(text: str | None) -> float | None:
    """Convert '35.5m²' → 35.5"""
    if not text:
        return None
    m = re.search(r"([\d.]+)\s*m", text, re.IGNORECASE)
    return float(m.group(1)) if m else None


def _parse_walk(text: str | None) -> int | None:
    """Convert '歩10分' or '10分' → 10"""
    if not text:
        return None
    m = re.search(r"(\d+)\s*分", text)
    return int(m.group(1)) if m else None


def _parse_floor(text: str | None) -> tuple[int | None, int | None]:
    """Convert '3階/10階建' → (3, 10)"""
    if not text:
        return None, None
    m = re.search(r"(\d+)\s*階\s*/\s*(\d+)\s*階建", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d+)\s*階", text)
    if m:
        return int(m.group(1)), None
    return None, None


def _parse_building_age(text: str | None) -> tuple[int | None, int | None]:
    """Convert '築10年' or '新築' → (age_years, built_year)"""
    if not text:
        return None, None
    if "新築" in text:
        return 0, None
    m = re.search(r"築(\d+)年", text)
    if m:
        return int(m.group(1)), None
    # '2015年築'
    m = re.search(r"(\d{4})年築", text)
    if m:
        year = int(m.group(1))
        from datetime import date
        age = date.today().year - year
        return age, year
    return None, None


class SuumoScraper(BaseScraper):
    source_name = "suumo"

    async def scrape(self):
        """Override to warm up with a homepage visit before hitting the search URL.
        Uses a shared block-memory to skip the local attempt entirely if Suumo
        has rate-limited us recently (Playwright warmup costs ~5s per request)."""
        import asyncio as _asyncio
        from app.scrapers.firecrawl import fetch_html, is_recently_blocked, mark_blocked

        recently_blocked = await is_recently_blocked(self.source_name)
        if recently_blocked:
            logger.info("[suumo] Recently blocked — skipping local scrape, going straight to Firecrawl")

        context = await self._new_context() if not recently_blocked else None
        page = await self._new_page(context) if context else None
        try:
            if not recently_blocked:
                logger.info("[suumo] Warming up via homepage…")
                try:
                    await page.goto("https://suumo.jp/chintai/tokyo/", wait_until="domcontentloaded")
                    await _asyncio.sleep(3)
                except Exception as exc:
                    logger.warning("[suumo] Warmup failed (non-fatal): %s", exc)

            for page_num in range(1, self.criteria.max_pages + 1):
                url = self.build_search_url(page_num)

                if recently_blocked:
                    # Skip local attempt — go straight to Firecrawl (may be a cache hit)
                    logger.info("[suumo] Firecrawl-only fetch page %d → %s", page_num, url)
                    fc_html = await fetch_html(url)
                    if fc_html and "アクセス集中に関するお詫び" not in fc_html:
                        listings = self._parse_html(fc_html)
                        logger.info("[suumo] Firecrawl page %d → %d listings", page_num, len(listings))
                        for listing in listings:
                            listing["source"] = self.source_name
                            yield listing
                        if not listings:
                            break
                        continue
                    logger.warning("[suumo] Firecrawl also failed — aborting")
                    self.blocked = True
                    break

                logger.info("[suumo] Scraping page %d → %s", page_num, url)
                try:
                    await self._goto_with_retry(page, url)
                except Exception as exc:
                    logger.error("[suumo] Failed to load page %d: %s", page_num, exc)
                    break

                html = await page.content()
                title = await page.title()
                logger.info("[suumo] Page title: %s | HTML length: %d", title, len(html))

                if "アクセス集中に関するお詫び" in html or len(html) < 3000:
                    logger.warning("[suumo] Rate-limit page detected — marking blocked + trying Firecrawl fallback")
                    await mark_blocked(self.source_name)
                    fc_html = await fetch_html(url)
                    if fc_html and "アクセス集中に関するお詫び" not in fc_html:
                        logger.info("[suumo] Firecrawl returned usable HTML — parsing")
                        listings = self._parse_html(fc_html)
                        logger.info("[suumo] Firecrawl page %d → %d listings", page_num, len(listings))
                        for listing in listings:
                            listing["source"] = self.source_name
                            yield listing
                        if not listings:
                            break
                        continue
                    logger.warning("[suumo] Firecrawl unavailable or also blocked — marking source blocked")
                    self.blocked = True
                    break

                import os as _os
                with open(f"/tmp/debug_suumo_p{page_num}.html", "w", encoding="utf-8") as f:
                    f.write(html)

                listings = await self.parse_listings_page(page)
                logger.info("[suumo] Page %d → %d listings", page_num, len(listings))

                for listing in listings:
                    listing["source"] = self.source_name
                    yield listing

                if not listings or not await self.has_next_page(page):
                    break
        finally:
            if context is not None:
                await context.close()

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

    async def parse_listings_page(self, page: Page) -> list[dict]:
        """
        Parse Suumo search results.
        Suumo groups units by building — each .cassetteitem div represents
        one building. Inside, .cassetteitem_other table rows are individual units.
        We flatten them: one dict per unit.
        """
        # Wait for listings to appear (or bail if blocked/CAPTCHA)
        try:
            await page.wait_for_selector(".cassetteitem", timeout=15000)
        except Exception:
            logger.warning("[suumo] .cassetteitem not found — possibly blocked or no results")
            return []

        html = await page.content()
        return self._parse_html(html)

    def _parse_html(self, html: str) -> list[dict]:
        """Parse raw Suumo HTML (used by both Playwright path and Firecrawl fallback)."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        for cassette in soup.select(".cassetteitem"):
            # Building-level info (shared by all units in this card)
            building_name = self._text(cassette, ".cassetteitem-detail-title")
            address = self._text(cassette, ".cassetteitem-detail-col1")
            building_type = self._text(cassette, ".cassetteitem-detail-col2")
            age_text = self._text(cassette, ".cassetteitem-detail-col3")
            transport_text = self._text(cassette, ".cassetteitem-detail-col1 ~ li")
            image_tag = cassette.select_one(".cassetteitem-object-img img")
            image_url = image_tag.get("rel-lazy") or image_tag.get("src") if image_tag else None

            # Station + line + walk from transport block
            line, station, walk = None, None, None
            transport_el = cassette.select_one(".cassetteitem-detail-col1")
            if transport_el:
                # Each <li> is one line/station pair; take the closest one (smallest walk)
                lis = transport_el.select("li") or [transport_el]
                best: tuple[int, str | None, str | None] | None = None
                for li in lis:
                    txt = li.get_text(" ", strip=True)
                    ln, st, wk = parse_transport(txt)
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

                results.append({
                    "source_url": detail_url,
                    "title": building_name or "",
                    "building_name": building_name,
                    "rent": _parse_yen(rent_text),
                    "management_fee": _parse_yen(fee_text),
                    "deposit": _parse_yen(deposit_text),
                    "key_money": _parse_yen(key_money_text),
                    "address": address,
                    "ward": None,  # derived from ward code in manager
                    "nearest_station": station,
                    "nearest_line": line,
                    "walk_minutes": walk,
                    "floor_plan": floor_plan_text,
                    "size_m2": _parse_size(size_text),
                    "floor": floor_num,
                    "total_floors": total_floors,
                    "building_age_years": age_years,
                    "built_year": built_year,
                    "building_type": building_type,
                    "features": [],
                    "image_url": image_url,
                })

        return results

    async def has_next_page(self, page: Page) -> bool:
        # Suumo shows a 次へ (next) button when there are more pages
        next_btn = await page.query_selector("a.pagination-parts:has-text('次へ')")
        return next_btn is not None

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
