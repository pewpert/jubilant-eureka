"""
Standalone scraper test — run this INSIDE the worker container to diagnose
whether the scraper can reach homes.co.jp and parse listings.

Bypasses Celery entirely. Useful when jobs stay "pending" or return 0 results.

Usage:
    docker compose exec worker python test_scraper.py
    docker compose exec worker python test_scraper.py suginami
    docker compose exec worker python test_scraper.py kita
"""

import asyncio
import sys
import os
from bs4 import BeautifulSoup

from app.models.search import SearchCriteria, Source, FloorPlan, WalkMinutes
from app.scrapers.homes import HomesScraper


async def main(ward: str = "suginami"):
    criteria = SearchCriteria(
        wards=[ward],
        rent_min=10.0,
        rent_max=12.0,
        size_min_m2=25.0,
        size_max_m2=40.0,
        floor_plans=[FloorPlan.LDK1, FloorPlan.DK1],
        walk_minutes=WalkMinutes.TEN,
        sources=[Source.HOMES],
        max_pages=1,
    )

    scraper_instance = HomesScraper(criteria)
    url = scraper_instance.build_search_url(1)
    print(f"\n{'='*60}")
    print(f"Ward:  {ward}")
    print(f"URL:   {url}")
    print(f"{'='*60}\n")

    listings = []
    try:
        async with HomesScraper(criteria) as scraper:
            async for listing in scraper.scrape():
                listings.append(listing)
                name = listing.get("building_name") or listing.get("title") or "?"
                rent = listing.get("rent")
                rent_str = f"¥{rent:,}" if rent else "N/A"
                plan = listing.get("floor_plan") or "?"
                size = listing.get("size_m2")
                size_str = f"{size}m²" if size else "?"
                print(f"  ✓ {name} | {rent_str}/mo | {plan} {size_str}")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

    print(f"\n→ Total listings scraped: {len(listings)}")

    # Inspect HTML snapshot if it was saved
    snap = f"/tmp/debug_homes_p1.html"
    if os.path.exists(snap):
        print(f"\nAnalysing HTML snapshot: {snap}")
        with open(snap, encoding="utf-8") as f:
            html = f.read()
        soup = BeautifulSoup(html, "lxml")
        title = soup.title.string if soup.title else "no title"
        print(f"Page title : {title}")
        print(f"HTML length: {len(html):,} chars")

        # Print all CSS classes that look like listing-related
        all_classes: set[str] = set()
        for tag in soup.find_all(class_=True):
            for c in tag.get("class", []):
                all_classes.add(c)

        keywords = ["list", "item", "card", "cassette", "property", "bukken",
                    "building", "result", "rent", "merge", "unit", "chintai",
                    "price", "room", "flat", "apartment", "mod-", "prg-"]
        hits = [c for c in all_classes if any(k in c.lower() for k in keywords)]
        print(f"\nListing-related CSS classes ({len(hits)}):")
        for c in sorted(hits)[:50]:
            count = len(soup.select(f".{c}"))
            print(f"  .{c}  ({count} elements)")

        print(f"\nBody text (first 600 chars):")
        print(soup.get_text()[:600].strip())
    else:
        print(f"\nNo HTML snapshot found at {snap}. The scraper may have crashed before saving.")


if __name__ == "__main__":
    ward = sys.argv[1] if len(sys.argv) > 1 else "suginami"
    asyncio.run(main(ward))
