"""
Scraper manager — orchestrates multiple scrapers concurrently.

Each scraper runs independently. Results are collected per-source so we can
track how many raw listings each site returned, and how many were excluded by
which post-scrape filter. This powers the /debug endpoint.
"""

import asyncio
import logging
from typing import Callable

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

ProgressCb = Callable[[str], None]

SOURCE_LABELS = {
    "homes": "homes.co.jp",
    "suumo": "suumo.jp",
    "chintai": "chintai.com",
}


def _empty_stats(url: str = "") -> dict:
    return {
        "url_used": url,
        "raw_count": 0,
        "passed_count": 0,
        "excluded_by": {
            "rent": 0,
            "size": 0,
            "walk": 0,
            "building_age": 0,
            "floor_plan": 0,
            "unparseable_rent": 0,
        },
        "error": None,
        "blocked": False,
        "sample_excluded": [],
        "sample_near_miss": [],
    }


async def _run_single_scraper(
    scraper_class: type[BaseScraper],
    criteria: SearchCriteria,
    per_source_results: dict[str, list[dict]],
    per_source_stats: dict[str, dict],
    completed: list[str],
    progress_cb: ProgressCb | None,
) -> None:
    source = scraper_class.source_name
    label = SOURCE_LABELS.get(source, source)

    # Capture URL before entering the async context
    try:
        url_used = scraper_class(criteria).build_search_url(1)
    except Exception:
        url_used = ""

    per_source_stats[source] = _empty_stats(url_used)
    per_source_results[source] = []

    if progress_cb:
        progress_cb(f"Searching {label}…")

    try:
        async with scraper_class(criteria) as scraper:
            async for listing in scraper.scrape():
                listing["source"] = source
                per_source_results[source].append(listing)
            per_source_stats[source]["blocked"] = bool(getattr(scraper, "blocked", False))
    except Exception as exc:
        logger.error("[%s] Scraper failed: %s", source, exc, exc_info=True)
        per_source_stats[source]["error"] = str(exc)

    completed.append(label)
    if progress_cb:
        progress_cb(f"Done: {', '.join(completed)}")


async def run_all_scrapers(
    criteria: SearchCriteria,
    progress_cb: ProgressCb | None = None,
) -> tuple[list[dict], dict]:
    """
    Run all requested scrapers concurrently.
    Returns (filtered_listings, scrape_stats) where scrape_stats has per-source
    raw counts, passed counts, and exclusion breakdowns.
    """
    per_source_results: dict[str, list[dict]] = {}
    per_source_stats: dict[str, dict] = {}
    completed: list[str] = []
    tasks = []

    for source in criteria.sources:
        scraper_class = SCRAPERS.get(source)
        if not scraper_class:
            logger.warning("No scraper registered for source: %s", source)
            continue
        tasks.append(_run_single_scraper(
            scraper_class, criteria,
            per_source_results, per_source_stats,
            completed, progress_cb,
        ))

    await asyncio.gather(*tasks, return_exceptions=True)

    # Merge all results and dedup across sources.
    # Primary key: source_url. Secondary: (building_name, floor_plan, rent, size)
    # for listings whose URL is empty or identical across sources.
    seen_urls: set[str] = set()
    seen_composite: set[tuple] = set()
    unique: list[dict] = []
    for source, listings in per_source_results.items():
        per_source_stats[source]["raw_count"] = len(listings)
        for listing in listings:
            url = listing.get("source_url", "") or ""
            if url:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
            else:
                # No URL — dedup by composite key so the same unit scraped twice
                # from different pages doesn't slip through.
                composite = (
                    (listing.get("building_name") or "").strip(),
                    listing.get("floor_plan"),
                    listing.get("rent"),
                    listing.get("size_m2"),
                )
                if composite == ("", None, None, None):
                    # Nothing to dedup on — drop it, we can't show it to the user without a URL
                    continue
                if composite in seen_composite:
                    continue
                seen_composite.add(composite)
            unique.append(listing)

    # Build post-scrape filter thresholds
    rent_max_yen = int(criteria.rent_max * 10000) if criteria.rent_max < 9999 else None
    rent_min_yen = int(criteria.rent_min * 10000) if criteria.rent_min > 0 else None
    size_min = criteria.size_min_m2 if criteria.size_min_m2 > 0 else None
    size_max = criteria.size_max_m2 if criteria.size_max_m2 < 9999 else None
    walk_max = criteria.walk_minutes.value if criteria.walk_minutes.value < 9999 else None
    age_max = criteria.building_age_max if criteria.building_age_max < 9999 else None
    allowed_plans = {fp.value for fp in criteria.floor_plans} if criteria.floor_plans else None
    rent_filter_active = bool(rent_min_yen or rent_max_yen)

    filtered: list[dict] = []

    for l in unique:
        source = l.get("source", "unknown")
        stats = per_source_stats.get(source)
        if stats is None:
            filtered.append(l)
            continue

        rent = l.get("rent")
        size = l.get("size_m2")
        walk = l.get("walk_minutes")
        age = l.get("building_age_years")
        fp = l.get("floor_plan")

        # Collect ALL failing reasons (not just the first) so we can identify near-misses.
        reasons: list[str] = []

        if rent_filter_active and rent is None:
            reasons.append("unparseable_rent")
        elif (rent_min_yen and rent is not None and rent < rent_min_yen) or \
             (rent_max_yen and rent is not None and rent > rent_max_yen):
            reasons.append("rent")

        if (size_min and size is not None and size < size_min) or \
           (size_max and size is not None and size > size_max):
            reasons.append("size")

        if walk_max and walk is not None and walk > walk_max:
            reasons.append("walk")

        if age_max and age is not None and age > age_max:
            reasons.append("building_age")

        if allowed_plans and fp is not None and fp not in allowed_plans:
            reasons.append("floor_plan")

        if not reasons:
            filtered.append(l)
            stats["passed_count"] += 1
            continue

        # Failed at least one filter. Charge it to the first reason for the headline count.
        primary = reasons[0]
        stats["excluded_by"][primary] += 1
        if len(stats["sample_excluded"]) < 3:
            stats["sample_excluded"].append({**l, "_excluded_reason": primary})

        # Near-miss: failed exactly one filter — these are the "almost matched" listings
        # worth surfacing so the user can see what loosening one criterion would yield.
        if len(reasons) == 1 and len(stats["sample_near_miss"]) < 3:
            stats["sample_near_miss"].append({**l, "_missed_filter": primary})

    # Compute dominant filter across all sources
    total_excl: dict[str, int] = {}
    for stats in per_source_stats.values():
        for k, v in stats["excluded_by"].items():
            total_excl[k] = total_excl.get(k, 0) + v

    dominant = max(total_excl, key=lambda k: total_excl[k]) if total_excl else None
    if dominant and total_excl.get(dominant, 0) == 0:
        dominant = None

    scrape_stats = {
        "per_source": per_source_stats,
        "total_raw": sum(s["raw_count"] for s in per_source_stats.values()),
        "total_passed": len(filtered),
        "dominant_filter": dominant,
    }

    logger.info(
        "Scraping complete. Total unique listings: %d (from %d raw)",
        len(filtered),
        scrape_stats["total_raw"],
    )
    return filtered, scrape_stats
