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
from app.scrapers.transport import parse_transport
from app.scrapers.detail_features import parse_detail_features
from app.scrapers.normalize import parse_yen as _parse_yen, parse_size as _parse_size, parse_walk as _parse_walk, common_search_params
from app.scrapers.contract import RawListing
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


class HomesScraper(BaseScraper):
    source_name = "homes"

    _PARAM_NAMES = {
        "rent_min": "cb", "rent_max": "ct",
        "size_min": "mb", "size_max": "mt", "walk": "et", "page": "page",
    }

    def _url_for_path(self, path: str, page_num: int) -> str:
        """Assemble a Homes search URL for a geo path + the shared param ladder."""
        params = common_search_params(self.criteria, self._PARAM_NAMES, page_num)
        qs = "&".join(f"{k}={v}" for k, v in params)
        base = f"{HOMES_BASE}{path}"
        return f"{base}?{qs}" if qs else base

    def _build_url_for_ward(self, ward_slug: str | None, page_num: int) -> str:
        """Build search URL for a specific ward (or all-Tokyo if None)."""
        c = self.criteria
        use_theme = FloorPlan.LDK1 in c.floor_plans or FloorPlan.DK1 in c.floor_plans

        if ward_slug:
            geo = WARD_TO_CITY_SLUG.get(ward_slug, f"{ward_slug}-city")
            path = f"/theme/{HOMES_THEME_1LDK}/tokyo/{geo}/list/" if use_theme else f"/tokyo/{geo}/list/"
        else:
            path = "/tokyo/list/"
        return self._url_for_path(path, page_num)

    def is_blocked(self, html: str | None) -> bool:
        """A real Homes results page carries the merge-building card marker."""
        if html and "mod-mergeBuilding" in html:
            return False
        return super().is_blocked(html)

    async def scrape(self):
        """Iterate over all selected wards, fetch each page resiliently, dedup by URL."""
        wards = self.criteria.wards if self.criteria.wards else [None]  # type: ignore[list-item]

        seen_urls: set[str] = set()
        context = await self._new_context()
        page = await self._new_page(context)

        try:
            for ward_slug in wards:
                for page_num in range(1, self.criteria.max_pages + 1):
                    url = self._build_url_for_ward(ward_slug, page_num)
                    logger.info("[homes] Scraping page %d (ward=%s) → %s", page_num, ward_slug, url)

                    html = await self.fetch_page(page, url)
                    if html is None:
                        if page_num == 1 and ward_slug == wards[0]:
                            self.blocked = True
                        break

                    listings = self.parse_html(html)
                    logger.info("[homes] Page %d → %d listings", page_num, len(listings))

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

                    if not listings or not found_new or not self._has_next_in_html(html):
                        break
        finally:
            await context.close()

    def build_search_url(self, page_num: int = 1) -> str:
        """Return URL for first ward (used by manager for stats URL capture)."""
        ward_slug = self.criteria.wards[0] if self.criteria.wards else None
        # Handle station override
        if self.criteria.station:
            for name, code in KNOWN_STATION_CODES.items():
                if name.lower() in self.criteria.station.lower():
                    c = self.criteria
                    use_theme = FloorPlan.LDK1 in c.floor_plans or FloorPlan.DK1 in c.floor_plans
                    geo = f"{code}-st"
                    path = f"/theme/{HOMES_THEME_1LDK}/tokyo/{geo}/list/" if use_theme else f"/tokyo/{geo}/list/"
                    return self._url_for_path(path, page_num)
        return self._build_url_for_ward(ward_slug, page_num)

    def parse_html(self, html: str) -> list[dict]:
        """Pure string→listings parser (used by both live and Firecrawl paths)."""
        soup = BeautifulSoup(html or "", "lxml")
        cards = soup.select("div.mod-mergeBuilding--rent--photo")
        if not cards:
            all_cls: set[str] = set()
            for tag in soup.find_all(class_=True):
                for c in tag.get("class", []):
                    all_cls.add(c)
            kw = ["list", "item", "card", "cassette", "bukken", "building", "merge", "prg-"]
            hits = sorted(c for c in all_cls if any(k in c.lower() for k in kw))[:30]
            logger.warning("[homes] No cards in HTML (len=%d). Candidate classes: %s", len(html or ""), hits)
            return []
        logger.info("[homes] Found %d building cards", len(cards))

        results = []
        for card in cards:
            # Building name and first listing URL
            name_el = card.select_one(".moduleHead a, h2 a, h3 a")
            building_name = name_el.get_text(strip=True) if name_el else None

            # Building-level fields from first tbody (th/td rows)
            tbodies = card.select("tbody")
            if not tbodies:
                continue
            bldg_fields: dict[str, str] = {}
            for row in tbodies[0].select("tr"):
                th = row.select_one("th")
                td = row.select_one("td")
                if th and td:
                    bldg_fields[th.get_text(strip=True)] = td.get_text(strip=True)

            address = bldg_fields.get("所在地")

            # Nearest station + line from 交通 field
            traffic_raw = bldg_fields.get("交通", "")
            line, station, walk = parse_transport(traffic_raw)

            # Building age from 築年数/階数
            age_raw = bldg_fields.get("築年数/階数") or bldg_fields.get("築年数") or ""
            age_years = None
            ma = re.search(r"(\d+)年", age_raw)
            if ma:
                age_years = int(ma.group(1))
            elif "新築" in age_raw:
                age_years = 0

            image_tag = card.select_one("img")
            image_url = image_tag.get("src") if image_tag else None

            # Unit rows from second tbody — each data row has: floor | price | layout+size | ... | detail link
            unit_tbody = tbodies[1] if len(tbodies) > 1 else None
            if unit_tbody is None:
                continue

            unit_links = unit_tbody.select("a[href*='/chintai/']")
            unit_rows = [r for r in unit_tbody.select("tr") if r.select_one("td")]

            for i, row in enumerate(unit_rows):
                tds = row.select("td")
                if len(tds) < 4:
                    continue
                raw_text = row.get_text(separator=" ", strip=True)

                # Price cell contains "X.X万円/fee"
                rent, mgmt_fee = None, None
                price_m = re.search(r"([\d.]+)\s*万円\s*/\s*([\d,]+円|-)", raw_text)
                if price_m:
                    rent = int(float(price_m.group(1)) * 10000)
                    mgmt_fee = _parse_yen(price_m.group(2))

                # 敷金/礼金
                dep_m = re.search(r"([\d.]+)ヶ月/([\d.]+)ヶ月", raw_text)
                deposit = int(float(dep_m.group(1)) * rent) if (dep_m and rent) else None
                key_money = int(float(dep_m.group(2)) * rent) if (dep_m and rent) else None

                # Layout and size — e.g. "1LDK30m²"
                floor_plan_m = re.search(r"(1LDK|1DK|2LDK|2DK|ワンルーム|1K|1R)", raw_text)
                floor_plan = floor_plan_m.group(1) if floor_plan_m else None
                size_m = re.search(r"([\d.]+)m", raw_text)
                size_m2 = float(size_m.group(1)) if size_m else None

                # Floor
                floor_m = re.search(r"(\d+)階", raw_text)
                floor_num = int(floor_m.group(1)) if floor_m else None

                # Detail URL — prefer a link inside this row; fall back to indexed lookup.
                # Indexed lookup is fragile when the row/link counts diverge (e.g. if a row
                # has no link, the indexes shift and we'd attribute the wrong URL).
                row_link = row.select_one("a[href*='/chintai/']")
                if row_link:
                    detail_url = row_link.get("href", "")
                else:
                    detail_url = unit_links[i]["href"] if i < len(unit_links) else ""
                if detail_url and not detail_url.startswith("http"):
                    detail_url = f"https://www.homes.co.jp{detail_url}"

                if not rent and not floor_plan:
                    continue

                results.append(RawListing(
                    source_url=detail_url,
                    source=self.source_name,
                    title=building_name or floor_plan or "",
                    building_name=building_name,
                    rent=rent,
                    management_fee=mgmt_fee,
                    deposit=deposit,
                    key_money=key_money,
                    address=address,
                    ward=None,
                    nearest_station=station,
                    nearest_line=line,
                    walk_minutes=walk,
                    floor_plan=floor_plan,
                    size_m2=size_m2,
                    floor=floor_num,
                    building_age_years=age_years,
                    image_url=image_url,
                ).to_dict())

        return results

    async def parse_detail(self, page: Page, url: str, built_year: int | None = None) -> dict:
        """Fetch a listing detail page and extract parking / amenity flags."""
        await self._goto_with_retry(page, url)
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        return parse_detail_features(soup.get_text(separator=" "), built_year)

    @staticmethod
    def _text(parent, selector: str) -> str | None:
        el = parent.select_one(selector)
        return el.get_text(strip=True) if el else None
