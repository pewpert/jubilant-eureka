"""
LIFULL HOME'S (homes.co.jp) scraper.

Homes is Japan's second-largest portal. Characteristics:
  - Mix of SSR and client-side hydration. The listing cards are in the
    initial HTML but some metadata loads via XHR.
  - Anti-bot: relatively light — UA check + occasional CAPTCHA on rapid
    repeated access. Our delays + UA rotation handle this.
  - Listings are in <div class="mod-mergeBuilding--rent"> blocks.

URL structure:
  https://www.homes.co.jp/chintai/tokyo/{ward}/list/?
    ?pricemax={万円}
    &pricemin={万円}
    &floorspace={m²}
    &buildingarea=走10分 ...  ← station walk
    &page=2
"""

import re
import logging

from playwright.async_api import Page
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper
from app.models.search import SearchCriteria, FloorPlan, TOKYO_WARDS

logger = logging.getLogger(__name__)

HOMES_BASE = "https://www.homes.co.jp/chintai"

# Homes uses ward name in the URL path (romaji)
WARD_SLUGS = {v: k for k, v in TOKYO_WARDS.items()}  # code → slug

# Homes floor plan query values
FLOOR_PLAN_VALUES = {
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
        c = self.criteria

        # Use first selected ward or default to 'tokyo'
        if c.wards:
            ward_slug = c.wards[0]
            path = f"/tokyo/{ward_slug}"
        else:
            path = "/tokyo"

        params: list[tuple[str, str]] = []

        if c.rent_min > 0:
            params.append(("pricemin", str(int(c.rent_min))))
        if c.rent_max < 9999:
            params.append(("pricemax", str(int(c.rent_max))))
        if c.size_min_m2 > 0:
            params.append(("floorspacemin", str(int(c.size_min_m2))))
        if c.walk_minutes.value < 9999:
            params.append(("tsukin", str(c.walk_minutes.value)))
        if c.building_age_max < 9999:
            params.append(("newlybuilt", str(c.building_age_max)))
        if c.floor_plans:
            for fp in c.floor_plans:
                params.append(("madori", FLOOR_PLAN_VALUES[fp]))
        if page_num > 1:
            params.append(("page", str(page_num)))

        qs = "&".join(f"{k}={v}" for k, v in params)
        base = f"{HOMES_BASE}{path}/list/"
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
