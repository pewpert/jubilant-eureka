"""
Chintai.net scraper.

Verified URL pattern (April 2026):
  https://www.chintai.net/tokyo/area/{WARD_CODE}/list/
    ?yen_from=80000    ← rent in yen
    &yen_to=150000
    &menseki_from=25   ← min size m²
    &tsukin=10         ← max walk minutes
    &madori=1LDK       ← room type (repeatable)
    &page=2

Ward codes: same numeric codes as Suumo (13115 = Suginami, etc.)
For multiple wards the scraper iterates ward codes and deduplicates by URL.

Structure per .cassette_item (non-PR):
  - Building info in table.l-table (address, station, age, floors)
  - Unit rows in .cassette_detail tbody tr.detail-inner
    td.floar / td.price / td.other_price / layout+size td
"""

import re
import logging
from typing import AsyncIterator

from playwright.async_api import Page
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper
from app.scrapers.transport import parse_transport
from app.scrapers.detail_features import parse_detail_features
from app.scrapers.normalize import parse_yen as _parse_yen, parse_size as _parse_size
from app.scrapers.contract import RawListing
from app.models.search import SearchCriteria, FloorPlan

logger = logging.getLogger(__name__)

CHINTAI_BASE = "https://www.chintai.net"

FLOOR_PLAN_VALUES = {
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


def _build_params(c: SearchCriteria, page_num: int) -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = []
    if c.rent_min > 0:
        params.append(("yen_from", str(int(c.rent_min * 10000))))
    if c.rent_max < 9999:
        params.append(("yen_to", str(int(c.rent_max * 10000))))
    if c.size_min_m2 > 0:
        params.append(("menseki_from", str(int(c.size_min_m2))))
    if c.size_max_m2 < 9999:
        params.append(("menseki_to", str(int(c.size_max_m2))))
    if c.walk_minutes.value < 9999:
        params.append(("tsukin", str(c.walk_minutes.value)))
    if c.building_age_max < 9999:
        params.append(("chikunensu", str(c.building_age_max)))
    for fp in c.floor_plans:
        params.append(("madori", FLOOR_PLAN_VALUES[fp]))
    if page_num > 1:
        params.append(("page", str(page_num)))
    return params


class ChintaiScraper(BaseScraper):
    source_name = "chintai"

    def build_search_url(self, page_num: int = 1, ward_code: str | None = None) -> str:
        c = self.criteria
        codes = c.ward_codes()
        code = ward_code or (codes[0] if codes else None)
        if code:
            base = f"{CHINTAI_BASE}/tokyo/area/{code}/list/"
        else:
            base = f"{CHINTAI_BASE}/tokyo/list/"
        params = _build_params(c, page_num)
        qs = "&".join(f"{k}={v}" for k, v in params)
        return f"{base}?{qs}" if qs else base

    def is_blocked(self, html: str | None) -> bool:
        """A real Chintai results page carries the cassette_item card marker."""
        if html and "cassette_item" in html:
            return False
        return super().is_blocked(html)

    async def scrape(self) -> AsyncIterator[dict]:
        """Iterate over all ward codes, fetch each page resiliently, dedup by URL."""
        codes = self.criteria.ward_codes()
        if not codes:
            codes = [None]  # type: ignore[list-item]

        seen_urls: set[str] = set()
        context = await self._new_context()
        page = await self._new_page(context)

        try:
            for ward_code in codes:
                for page_num in range(1, self.criteria.max_pages + 1):
                    url = self.build_search_url(page_num, ward_code)
                    logger.info("[chintai] Scraping page %d (ward=%s) → %s", page_num, ward_code, url)

                    html = await self.fetch_page(page, url)
                    if html is None:
                        if page_num == 1 and ward_code == codes[0]:
                            self.blocked = True
                        break

                    listings = self.parse_html(html)
                    logger.info("[chintai] Page %d → %d listings", page_num, len(listings))

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

    def _has_next_in_html(self, html: str) -> bool:
        return "次のページ" in (html or "")

    async def parse_listings_page(self, page: Page) -> list[dict]:
        try:
            await page.wait_for_selector(".cassette_item", timeout=15000)
        except Exception:
            logger.warning("[chintai] .cassette_item not found")
        return self.parse_html(await page.content())

    def parse_html(self, html: str) -> list[dict]:
        """Pure string→listings parser (used by both live and Firecrawl paths)."""
        soup = BeautifulSoup(html or "", "lxml")
        results = []

        for item in soup.select(".cassette_item"):
            # Skip PR/sponsored items — they often lack standard structure
            if "item_pr" in item.get("class", []):
                continue

            # Building title (h2 text minus the room-type span)
            ttl_h2 = item.select_one(".cassette_ttl h2")
            building_title = None
            if ttl_h2:
                for span in ttl_h2.select("span"):
                    span.decompose()
                building_title = ttl_h2.get_text(strip=True) or None

            # Parse l-table for address, station, age.
            # Row structure: th1 | td1 | th2(rowspan) | td2(rowspan)
            # select_one("th") only gets first th — iterate all cells instead.
            address, station, line, walk_minutes, age_years, built_year, total_floors = (
                None, None, None, None, None, None, None,
            )
            l_table = item.select_one("table.l-table")
            if l_table:
                # Walk all th elements and match each to its next-sibling td
                for th in l_table.select("th"):
                    label = th.get_text(strip=True)
                    # Find the td that follows this th in the DOM
                    td = th.find_next_sibling("td")
                    if not td:
                        continue
                    if "住所" in label:
                        for sub in td.select("a, p"):
                            sub.decompose()
                        address = td.get_text(strip=True) or None
                    elif "交通" in label:
                        first_li = td.select_one("li")
                        if first_li:
                            transport_text = first_li.get_text(" ", strip=True)
                            line, station, walk_minutes = parse_transport(transport_text)
                    elif "築年" in label:
                        age_text = td.get_text(strip=True)
                        m = re.search(r"(\d{4})年", age_text)
                        if m:
                            built_year = int(m.group(1))
                        m2 = re.search(r"築(\d+)年", age_text)
                        if m2:
                            age_years = int(m2.group(1))
                        elif "新築" in age_text:
                            age_years = 0
                    elif "階建" in label:
                        m = re.search(r"(\d+)階建", td.get_text(strip=True))
                        if m:
                            total_floors = int(m.group(1))

            # Unit rows
            for tbody in item.select(".cassette_detail tbody"):
                detail_url = ""
                bk = tbody.get("data-detailurl") or tbody.get("data-bkkey")
                if bk:
                    if bk.startswith("/"):
                        detail_url = f"{CHINTAI_BASE}{bk}"
                    else:
                        detail_url = f"{CHINTAI_BASE}/detail/bk-{bk}/"

                for row in tbody.select("tr.detail-inner"):
                    # Floor
                    floor_td = row.select_one("td.floar")
                    floor_num = None
                    if floor_td:
                        m = re.search(r"(\d+)階", floor_td.get_text(strip=True))
                        if m:
                            floor_num = int(m.group(1))

                    # Rent + management fee
                    # td.price contains: <span class="num">11.4</span>万円<br/>6,000円
                    # joined strings → "11.4 万円 6,000円"
                    price_td = row.select_one("td.price")
                    rent, mgmt_fee = None, None
                    if price_td:
                        price_text = " ".join(price_td.stripped_strings)
                        rent = _parse_yen(price_text)
                        # Management fee is after 万円
                        m_mgmt = re.search(r"万円\s+([\d,]+)\s*円", price_text)
                        if m_mgmt:
                            mgmt_fee = int(m_mgmt.group(1).replace(",", ""))

                    # Deposit / key money ("Xヶ月" or "なし")
                    deposit, key_money = None, None
                    other_td = row.select_one("td.other_price")
                    if other_td and rent:
                        other_text = " ".join(other_td.stripped_strings)
                        amounts = re.findall(r"([\d.]+)\s*ヶ月", other_text)
                        if len(amounts) >= 1:
                            deposit = int(float(amounts[0]) * rent)
                        if len(amounts) >= 2:
                            key_money = int(float(amounts[1]) * rent)

                    # Layout + size: td without specific class → "1DK 37.58m²" (same td)
                    layout, size_m2 = None, None
                    for td in row.select("td"):
                        cls = set(td.get("class", []))
                        skip = {"check", "madori", "floar", "price", "other_price", "inquiry", "detail", "mail_btnArea"}
                        if cls & skip:
                            continue
                        txt = " ".join(td.stripped_strings)
                        if not txt or ("m²" not in txt and "m2" not in txt.lower()):
                            continue
                        size_m2 = _parse_size(txt)
                        # Floor plan: e.g. 1R, 1K, 1DK, 1LDK, 2LDK etc.
                        m_fp = re.search(r"\d(?:R|LDK|DK|K)(?:\+S)?", txt)
                        if m_fp:
                            layout = m_fp.group(0)
                        break

                    results.append(RawListing(
                        source_url=detail_url,
                        source=self.source_name,
                        title=building_title or station or "",
                        building_name=building_title,
                        rent=rent,
                        management_fee=mgmt_fee,
                        deposit=deposit,
                        key_money=key_money,
                        address=address,
                        ward=None,
                        nearest_station=station,
                        nearest_line=line,
                        walk_minutes=walk_minutes,
                        floor_plan=layout,
                        size_m2=size_m2,
                        floor=floor_num,
                        total_floors=total_floors,
                        building_age_years=age_years,
                        built_year=built_year,
                    ).to_dict())

        return results

    async def has_next_page(self, page: Page) -> bool:
        # Chintai uses a next page link with class pagination__next or contains 次のページ
        next_btn = await page.query_selector(".pagination__next, a.next, a[rel='next']")
        if next_btn:
            return True
        # Fallback: look for text link
        try:
            await page.wait_for_selector("text=次のページ", timeout=1000)
            return True
        except Exception:
            return False

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
