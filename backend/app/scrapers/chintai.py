"""
Chintai.net scraper.

Chintai is a mid-size portal focused on long-term rentals.
Characteristics:
  - Mostly SSR, lighter anti-bot than Suumo.
  - Listings in <div class="cassette"> blocks.
  - Good source for listings not on Suumo/Homes.

URL structure:
  https://www.chintai.net/tokyo/list/?
    &chinryoMax=200000   ← max rent in yen
    &chinryoMin=50000
    &mensekiMin=20
    &shodanMin=1
    &kokaiFlg=1
    &page=2
"""

import re
import logging

from playwright.async_api import Page
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper
from app.models.search import FloorPlan

logger = logging.getLogger(__name__)

CHINTAI_BASE = "https://www.chintai.net/tokyo/list/"

FLOOR_PLAN_CODES = {
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


def _parse_yen(text: str | None) -> int | None:
    if not text:
        return None
    text = text.replace(",", "").replace("\u00a0", "").strip()
    m = re.search(r"([\d.]+)\s*万", text)
    if m:
        return int(float(m.group(1)) * 10000)
    m = re.search(r"(\d+)\s*円", text)
    return int(m.group(1)) if m else None


def _parse_size(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"([\d.]+)\s*m", text, re.IGNORECASE)
    return float(m.group(1)) if m else None


class ChintaiScraper(BaseScraper):
    source_name = "chintai"

    def build_search_url(self, page_num: int = 1) -> str:
        c = self.criteria
        params: list[tuple[str, str]] = []

        # Rent in yen (Chintai uses full yen, not 万円)
        if c.rent_min > 0:
            params.append(("chinryoMin", str(int(c.rent_min * 10000))))
        if c.rent_max < 9999:
            params.append(("chinryoMax", str(int(c.rent_max * 10000))))
        if c.size_min_m2 > 0:
            params.append(("mensekiMin", str(int(c.size_min_m2))))
        if c.walk_minutes.value < 9999:
            params.append(("tsukinMin", str(c.walk_minutes.value)))
        if c.building_age_max < 9999:
            params.append(("chikunensuMax", str(c.building_age_max)))
        if c.floor_plans:
            for fp in c.floor_plans:
                params.append(("madori", FLOOR_PLAN_CODES[fp]))
        if page_num > 1:
            params.append(("page", str(page_num)))

        qs = "&".join(f"{k}={v}" for k, v in params)
        return f"{CHINTAI_BASE}?{qs}" if qs else CHINTAI_BASE

    async def parse_listings_page(self, page: Page) -> list[dict]:
        try:
            await page.wait_for_selector(".cassette, .bukken-item", timeout=15000)
        except Exception:
            logger.warning("[chintai] listing selector not found")
            return []

        html = await page.content()
        soup = BeautifulSoup(html, "lxml")
        results = []

        for item in soup.select(".cassette, .bukken-item"):
            building_name = self._text(item, ".cassette__building-name, .bukken-name")
            address = self._text(item, ".cassette__address, .bukken-address")
            station_text = self._text(item, ".cassette__access, .bukken-access")

            station, walk = None, None
            if station_text:
                m = re.search(r"([^\s]+駅).*?(\d+)分", station_text)
                if m:
                    station = m.group(1)
                    walk = int(m.group(2))

            age_text = self._text(item, ".cassette__age, .bukken-age")
            age_years = None
            if age_text:
                if "新築" in age_text:
                    age_years = 0
                else:
                    m = re.search(r"築(\d+)年", age_text)
                    if m:
                        age_years = int(m.group(1))

            building_type = self._text(item, ".cassette__type, .bukken-type")
            image_tag = item.select_one("img.cassette__img, img.bukken-img")
            image_url = image_tag.get("src") if image_tag else None

            rent_text = self._text(item, ".cassette__price, .price-rent")
            fee_text = self._text(item, ".cassette__fee, .price-fee")
            floor_plan_text = self._text(item, ".cassette__madori, .madori")
            size_text = self._text(item, ".cassette__area, .menseki")
            floor_text = self._text(item, ".cassette__floor, .floor")

            link_el = item.select_one("a.cassette__link, a.bukken-link")
            detail_url = ""
            if link_el and link_el.get("href"):
                href = link_el["href"]
                detail_url = href if href.startswith("http") else f"https://www.chintai.net{href}"

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
                "deposit": None,
                "key_money": None,
                "address": address,
                "ward": None,
                "nearest_station": station,
                "walk_minutes": walk,
                "floor_plan": floor_plan_text,
                "size_m2": _parse_size(size_text),
                "floor": floor_num,
                "total_floors": None,
                "building_age_years": age_years,
                "built_year": None,
                "building_type": building_type,
                "features": [],
                "image_url": image_url,
            })

        return results

    async def has_next_page(self, page: Page) -> bool:
        next_btn = await page.query_selector("a.pagination__next, a:has-text('次へ')")
        return next_btn is not None

    @staticmethod
    def _text(parent, selector: str) -> str | None:
        el = parent.select_one(selector)
        return el.get_text(strip=True) if el else None
