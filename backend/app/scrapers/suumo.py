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

        params += [
            ("cb", str(c.rent_min)),
            ("ct", str(c.rent_max)),
            ("mb", str(int(c.size_min_m2))),
            ("mt", str(int(c.size_max_m2) if c.size_max_m2 < 9999 else 9999999)),
            ("et", str(c.walk_minutes.value)),
            ("cn", str(c.building_age_max if c.building_age_max < 9999 else 9999999)),
        ]

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

            # Station info from transport block
            station, walk = None, None
            transport_el = cassette.select_one(".cassetteitem-detail-col1")
            if transport_el:
                # Walk time usually appears as 'XX分' in the transport text
                transport_text = transport_el.get_text(" ", strip=True)
                walk = _parse_walk(transport_text)
                # Station name is harder — pick the part before 分
                m = re.search(r"([^\s]+駅)\s*歩(\d+)分", transport_text)
                if m:
                    station = m.group(1)

            # The transport block is actually in a separate element on Suumo
            transport_block = cassette.select(".cassetteitem-detail-col1 .cassette_detail-col1")
            if not station:
                # Try alt selector for station
                for li in cassette.select("li"):
                    txt = li.get_text(" ", strip=True)
                    m = re.search(r"([^\s/]+駅)\s*歩(\d+)分", txt)
                    if m:
                        station = m.group(1)
                        walk = int(m.group(2))
                        break

            age_years, built_year = _parse_building_age(age_text)

            # Unit rows inside this building card
            for row in cassette.select(".cassetteitem_other"):
                cells = row.select("td")
                if not cells:
                    continue

                # Floor plan cell text extraction is layout-dependent; use indexes
                floor_text = self._cell_text(cells, 0)
                rent_text = self._cell_text(cells, 1)
                fee_text = self._cell_text(cells, 2)
                deposit_text = self._cell_text(cells, 3)
                key_money_text = self._cell_text(cells, 4)
                floor_plan_text = self._cell_text(cells, 5)
                size_text = self._cell_text(cells, 6)

                detail_link = row.select_one("a.js-cassette_link_href")
                detail_url = f"https://suumo.jp{detail_link['href']}" if detail_link and detail_link.get("href") else ""

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
