"""
Scraper manager — orchestrates multiple scrapers concurrently.

Design:
  - Each scraper runs as an independent async generator.
  - We run them concurrently using asyncio.gather so Suumo + Homes +
    Chintai all scrape in parallel (up to concurrency limit).
  - Results are yielded as they arrive (streaming to the caller).
  - Errors from one scraper don't stop others.

Adding a new scraper later:
  1. Create backend/app/scrapers/newsite.py extending BaseScraper
  2. Add it to SCRAPERS dict below
  3. Add the Source enum value to models/search.py
  That's it.
"""

import asyncio
import logging
from typing import AsyncIterator

from app.models.search import SearchCriteria, Source
from app.scrapers.base import BaseScraper
from app.scrapers.suumo import SuumoScraper
from app.scrapers.homes import HomesScraper
from app.scrapers.chintai import ChintaiScraper

logger = logging.getLogger(__name__)

SCRAPERS: dict[Source, type[BaseScraper]] = {
    Source.SUUMO: SuumoScraper,
    Source.HOMES: HomesScraper,
    Source.CHINTAI: ChintaiScraper,
}


async def _run_single_scraper(
    scraper_class: type[BaseScraper],
    criteria: SearchCriteria,
    results: list[dict],
) -> None:
    """Run one scraper and append results to shared list."""
    source = scraper_class.source_name
    try:
        async with scraper_class(criteria) as scraper:
            async for listing in scraper.scrape():
                results.append(listing)
    except Exception as exc:
        logger.error("[%s] Scraper failed: %s", source, exc, exc_info=True)


async def run_all_scrapers(criteria: SearchCriteria) -> list[dict]:
    """
    Run all requested scrapers concurrently.
    Returns a deduplicated list of raw listing dicts.
    """
    results: list[dict] = []
    tasks = []

    for source in criteria.sources:
        scraper_class = SCRAPERS.get(source)
        if not scraper_class:
            logger.warning("No scraper registered for source: %s", source)
            continue
        tasks.append(_run_single_scraper(scraper_class, criteria, results))

    # Run all scrapers concurrently
    await asyncio.gather(*tasks, return_exceptions=True)

    # Basic deduplication by URL
    seen_urls: set[str] = set()
    unique: list[dict] = []
    for listing in results:
        url = listing.get("source_url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(listing)
        elif not url:
            unique.append(listing)  # keep if no URL to dedup on

    logger.info("Scraping complete. Total unique listings: %d", len(unique))
    return unique
