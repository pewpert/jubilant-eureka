"""
LIFULL HOME'S (homes.co.jp) scraper.

Homes is Japan's second-largest portal. Characteristics:
  - Mix of SSR and client-side hydration. The listing cards are in the
    initial HTML but some metadata loads via XHR.
  - Anti-bot: relatively light — UA check + occasional CAPTCHA on rapid
    repeated access. Our delays + UA rotation handle this.
  - Listings are in <div class="mod-mergeBuilding--rent"> blocks.
  - IMPORTANT: ?sort=fee does NOT work — sorting is JavaScript-driven.
    Read listings in default order and sort client-side.

Correct URL pattern (verified against live site, April 2026):
  Station-based:
    https://www.homes.co.jp/chintai/theme/14130/tokyo/{STATION_CODE}-st/list/
      ?cb=10.0    ← min rent in 万円 (10.0 = ¥100,000)
      &ct=12.0    ← max rent in 万円
      &mb=25      ← min size m²
      &mt=40      ← max size m²
      &et=10      ← max walk to station (minutes)
      &page=2

  Ward-based (fallback when station code unknown):
    https://www.homes.co.jp/chintai/theme/14130/tokyo/{ward-slug}-city/list/
      ?cb=10.0&ct=12.0&mb=25&mt=40&et=10

  theme/14130 = 1LDK feature filter. Without this the results include
  all room types and the cb/ct params behave differently.

Known station codes (from manual research):
  nakano_00758-st     → 中野 (JR Chuo / Tozai)
  asagaya_00760-st    → 阿佐ヶ谷 (JR Chuo/Sobu)
  新高円寺/高円寺      → use suginami-city ward search
  十条/東十条          → use kita-city ward search
"""

import re
import logging

from playwright.async_api import Page
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper
from app.models.search import SearchCriteria, FloorPlan

logger = logging.getLogger(__name__)

HOMES_BASE = "https://www.homes.co.jp/chintai"

# theme/14130 is the 1LDK filter on homes.co.jp
# Using it narrows results to the correct room type and makes cb/ct work correctly.
HOMES_THEME_1LDK = "14130"

# Ward slug → homes.co.jp city path segment (verified)
WARD_TO_CITY_SLUG: dict[str, str] = {
    "chiyoda": "chiyoda-city",
    "chuo": "chuo-city",
    "minato": "minato-city",
    "shinjuku": "shinjuku-city",
    "bunkyo": "bunkyo-city",
    "taito": "taito-city",
    "sumida": "sumida-city",
    "koto": "koto-city",
    "shinagawa": "shinagawa-city",
    "meguro": "meguro-city",
    "ota": "ota-city",
    "setagaya": "setagaya-city",
    "shibuya": "shibuya-city",
    "nakano": "nakano-city",
    "suginami": "suginami-city",
    "toshima": "toshima-city",
    "kita": "kita-city",
    "arakawa": "arakawa-city",
    "itabashi": "itabashi-city",
    "nerima": "nerima-city",
    "adachi": "adachi-city",
    "katsushika": "katsushika-city",
    "edogawa": "edogawa-city",
}

# Known station codes verified against homes.co.jp
KNOWN_STATION_CODES: dict[str, str] = {
    "nakano": "nakano_00758",
    "asagaya": "asagaya_00760",
}


def _parse_yen(text: str | None) -> int | None:
    if not text:
        return None
    text = text.strip().replace(",", "")
    m = re.search(r"([\d.]+)\s*万", text)
    if m:
        return int(float(m.group(1)) * 10000)
    m = re.search(r"(\d+)\s*円", text)
    if m:
        return int(m.group(1))
    return None


def _parse_size(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"([\d.]+)\s*m", text, re.IGNORECASE)
    return float(m.group(1)) if m else None


def _parse_walk(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"(\d+)\s*分", text)
    return int(m.group(1)) if m else None


class HomesScraper(BaseScraper):
    source_name = "homes"

    def build_search_url(self, page_num: int = 1) -> str:
        """
        Build the correct homes.co.jp URL using the theme/14130 pattern.

        Priority:
          1. If a station name matches a known code → station-based URL
          2. If wards are selected → first ward city-based URL
          3. Fallback → all Tokyo (no geo filter)

        The theme/14130 segment filters for 1LDK and makes cb/ct work correctly.
        """
        c = self.criteria

        # Determine geo path segment
        station_code = None
        if c.station:
            # Try to match station name to a known code
            for name, code in KNOWN_STATION_CODES.items():
                if name.lower() in c.station.lower():
                    station_code = code
                    break

        if station_code:
            geo = f"{station_code}-st"
        elif c.wards:
            ward_slug = c.wards[0]
            geo = WARD_TO_CITY_SLUG.get(ward_slug, f"{ward_slug}-city")
        else:
            geo = "tokyo"  # broad search

        # Use theme/14130 when searching for 1LDK (most common base case)
        # If no floor plan filter or 1LDK is included, use the theme URL.
        use_theme = not c.floor_plans or FloorPlan.LDK1 in c.floor_plans or FloorPlan.DK1 in c.floor_plans
        if use_theme:
            path = f"/theme/{HOMES_THEME_1LDK}/tokyo/{geo}/list/"
        else:
            path = f"/tokyo/{geo}/list/"

        # Query params — cb/ct are in 万円, which is what homes.co.jp expects
        params: list[tuple[str, str]] = []
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
        # Note: building age filter is not a simple param on homes — omit for now
        if page_num > 1:
            params.append(("page", str(page_num)))

        qs = "&".join(f"{k}={v}" for k, v in params)
        base = f"{HOMES_BASE}{path}"
        return f"{base}?{qs}" if qs else base

    async def parse_listings_page(self, page: Page) -> list[dict]:
        try:
            await page.wait_for_selector(".mod-mergeBuilding--rent, .prg-cassette", timeout=15000)
        except Exception:
            logger.warning("[homes] listing selector not found — may be blocked or no results")
            return []

        html = await page.content()
        soup = BeautifulSoup(html, "lxml")
        results = []

        # Homes renders each building/unit as a <section> with class mod-mergeBuilding--rent
        for item in soup.select(".mod-mergeBuilding--rent, .prg-cassette"):
            building_name = self._text(item, ".mod-mergeBuilding__buildingName, .bukken-name")
            address = self._text(item, ".mod-mergeBuilding__address, .bukken-address")

            # Transport
            station = None
            walk = None
            for li in item.select(".mod-mergeBuilding__transport li, .bukken-transport li"):
                txt = li.get_text(strip=True)
                m = re.search(r"(.+?駅).*?歩(\d+)分", txt)
                if m:
                    station = m.group(1)
                    walk = int(m.group(2))
                    break

            # Building age
            age_text = self._text(item, ".mod-mergeBuilding__spec, .bukken-age")
            age_years, built_year = None, None
            if age_text:
                m = re.search(r"築(\d+)年", age_text)
                if m:
                    age_years = int(m.group(1))
                if "新築" in age_text:
                    age_years = 0

            building_type = self._text(item, ".mod-mergeBuilding__buildingType, .bukken-type")
            image_tag = item.select_one("img.mod-mergeBuilding__img, img.bukken-img")
            image_url = image_tag.get("src") if image_tag else None

            # Units
            for unit in item.select(".mod-mergeUnit, .prg-unit"):
                rent_text = self._text(unit, ".mod-mergeUnit__price, .price-rent")
                fee_text = self._text(unit, ".mod-mergeUnit__managementFee, .price-fee")
                deposit_text = self._text(unit, ".mod-mergeUnit__deposit, .price-shikikin")
                key_money_text = self._text(unit, ".mod-mergeUnit__keyMoney, .price-reikin")
                floor_plan_text = self._text(unit, ".mod-mergeUnit__floorPlan, .madori")
                size_text = self._text(unit, ".mod-mergeUnit__floorSpace, .menseki")
                floor_text = self._text(unit, ".mod-mergeUnit__floor, .floor")

                link_el = unit.select_one("a[href]")
                detail_url = link_el["href"] if link_el else ""
                if detail_url and not detail_url.startswith("http"):
                    detail_url = f"https://www.homes.co.jp{detail_url}"

                floor_num = None
                if floor_text:
                    m = re.search(r"(\d+)階", floor_text)
                    if m:
                        floor_num = int(m.group(1))

                results.append({
                    "source_url": detail_url,
                    "title": building_name or floor_plan_text or "",
                    "building_name": building_name,
                    "rent": _parse_yen(rent_text),
                    "management_fee": _parse_yen(fee_text),
                    "deposit": _parse_yen(deposit_text),
                    "key_money": _parse_yen(key_money_text),
                    "address": address,
                    "ward": None,
                    "nearest_station": station,
                    "walk_minutes": walk,
                    "floor_plan": floor_plan_text,
                    "size_m2": _parse_size(size_text),
                    "floor": floor_num,
                    "total_floors": None,
                    "building_age_years": age_years,
                    "built_year": built_year,
                    "building_type": building_type,
                    "features": [],
                    "image_url": image_url,
                })

        return results

    async def has_next_page(self, page: Page) -> bool:
        next_btn = await page.query_selector("a:has-text('次のページ'), .pagination__next:not(.is-disabled)")
        return next_btn is not None

    @staticmethod
    def _text(parent, selector: str) -> str | None:
        el = parent.select_one(selector)
        return el.get_text(strip=True) if el else None
