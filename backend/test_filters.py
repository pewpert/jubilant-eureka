"""
Filter test suite — verifies post-scrape filters behave correctly.

Run inside the worker container:
    docker compose exec worker python test_filters.py

Each test triggers a real scrape against homes.co.jp (1 page, Suginami ward)
and asserts specific properties about the returned listings and scrape_stats.

Pass/fail printed per test. Summary at the end.
"""

import asyncio
import sys

from app.models.search import SearchCriteria, Source, FloorPlan, WalkMinutes
from app.scrapers.manager import run_all_scrapers

SUGINAMI = ["suginami"]
SOURCES_HOMES = [Source.HOMES]
ONE_PAGE = 1

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = PASS if ok else FAIL
    print(f"[{status}] {name}" + (f"\n       {detail}" if detail else ""))


async def test_rent_narrow() -> None:
    """All returned listings must have rent in [90k, 100k]."""
    criteria = SearchCriteria(
        wards=SUGINAMI,
        rent_min=9.0,
        rent_max=10.0,
        sources=SOURCES_HOMES,
        max_pages=ONE_PAGE,
    )
    listings, stats = await run_all_scrapers(criteria)
    violations = [l for l in listings if l.get("rent") is not None and not (90000 <= l["rent"] <= 100000)]
    raw = stats["total_raw"]
    passed = stats["total_passed"]
    ok = len(violations) == 0
    record("rent_narrow", ok,
           f"raw={raw}, passed={passed}, violations={len(violations)}" +
           (f", first={violations[0].get('rent')}" if violations else ""))


async def test_rent_upper() -> None:
    """No listing should exceed ¥120,000."""
    criteria = SearchCriteria(
        wards=SUGINAMI,
        rent_min=0.0,
        rent_max=12.0,
        sources=SOURCES_HOMES,
        max_pages=ONE_PAGE,
    )
    listings, stats = await run_all_scrapers(criteria)
    over_budget = [l for l in listings if l.get("rent") is not None and l["rent"] > 120000]
    ok = len(over_budget) == 0
    record("rent_upper", ok,
           f"raw={stats['total_raw']}, passed={stats['total_passed']}, over_budget={len(over_budget)}" +
           (f", max_seen=¥{max(l['rent'] for l in listings if l.get('rent')):,}" if listings else ""))


async def test_size_filter() -> None:
    """All returned listings with known size must be in [30, 40] m²."""
    criteria = SearchCriteria(
        wards=SUGINAMI,
        rent_max=30.0,
        size_min_m2=30.0,
        size_max_m2=40.0,
        sources=SOURCES_HOMES,
        max_pages=ONE_PAGE,
    )
    listings, stats = await run_all_scrapers(criteria)
    sized = [l for l in listings if l.get("size_m2") is not None]
    violations = [l for l in sized if not (30.0 <= l["size_m2"] <= 40.0)]
    ok = len(violations) == 0
    record("size_filter", ok,
           f"raw={stats['total_raw']}, passed={stats['total_passed']}, "
           f"sized={len(sized)}, violations={len(violations)}" +
           (f", first_bad={violations[0].get('size_m2')}" if violations else ""))


async def test_walk_filter() -> None:
    """All returned listings with known walk time must be ≤ 5 min."""
    criteria = SearchCriteria(
        wards=SUGINAMI,
        rent_max=30.0,
        walk_minutes=WalkMinutes.FIVE,
        sources=SOURCES_HOMES,
        max_pages=ONE_PAGE,
    )
    listings, stats = await run_all_scrapers(criteria)
    walked = [l for l in listings if l.get("walk_minutes") is not None]
    violations = [l for l in walked if l["walk_minutes"] > 5]
    ok = len(violations) == 0
    record("walk_filter", ok,
           f"raw={stats['total_raw']}, passed={stats['total_passed']}, "
           f"with_walk={len(walked)}, violations={len(violations)}" +
           (f", first_bad={violations[0].get('walk_minutes')}" if violations else ""))


async def test_floor_plan_filter() -> None:
    """All returned listings must be 1K."""
    criteria = SearchCriteria(
        wards=SUGINAMI,
        rent_max=30.0,
        floor_plans=[FloorPlan.K1],
        sources=SOURCES_HOMES,
        max_pages=ONE_PAGE,
    )
    listings, stats = await run_all_scrapers(criteria)
    with_plan = [l for l in listings if l.get("floor_plan") is not None]
    violations = [l for l in with_plan if l["floor_plan"] != "1K"]
    ok = len(violations) == 0
    record("floor_plan_filter", ok,
           f"raw={stats['total_raw']}, passed={stats['total_passed']}, "
           f"with_plan={len(with_plan)}, violations={len(violations)}" +
           (f", first_bad={violations[0].get('floor_plan')}" if violations else ""))


async def test_building_age_filter() -> None:
    """All listings with known age must be ≤ 10 yrs. excluded_by.building_age > 0 if any raw results."""
    criteria = SearchCriteria(
        wards=SUGINAMI,
        rent_max=30.0,
        building_age_max=10,
        sources=SOURCES_HOMES,
        max_pages=ONE_PAGE,
    )
    listings, stats = await run_all_scrapers(criteria)
    aged = [l for l in listings if l.get("building_age_years") is not None]
    violations = [l for l in aged if l["building_age_years"] > 10]
    homes_stats = stats["per_source"].get("homes", {})
    excl_age = homes_stats.get("excluded_by", {}).get("building_age", 0)
    raw = stats["total_raw"]
    ok = len(violations) == 0 and (raw == 0 or excl_age > 0)
    record("building_age_filter", ok,
           f"raw={raw}, passed={stats['total_passed']}, excl_by_age={excl_age}, "
           f"violations={len(violations)}")


async def test_multi_ward() -> None:
    """Multi-ward search returns listings (both wards scraped)."""
    criteria = SearchCriteria(
        wards=["suginami", "nakano"],
        rent_max=15.0,
        sources=SOURCES_HOMES,
        max_pages=ONE_PAGE,
    )
    listings, stats = await run_all_scrapers(criteria)
    raw = stats["total_raw"]
    ok = raw > 0
    record("multi_ward", ok,
           f"wards=[suginami,nakano], raw={raw}, passed={stats['total_passed']}")


async def test_zero_expected() -> None:
    """With rent 50–100万, should get 0 results. dominant_filter should be 'rent'."""
    criteria = SearchCriteria(
        wards=SUGINAMI,
        rent_min=50.0,
        rent_max=100.0,
        sources=SOURCES_HOMES,
        max_pages=ONE_PAGE,
    )
    listings, stats = await run_all_scrapers(criteria)
    passed = stats["total_passed"]
    raw = stats["total_raw"]
    dominant = stats.get("dominant_filter")
    ok = passed == 0 and (raw == 0 or dominant == "rent")
    record("zero_expected", ok,
           f"raw={raw}, passed={passed}, dominant_filter={dominant!r}")


async def main() -> None:
    print("=" * 60)
    print("Filter Test Suite — homes.co.jp, Suginami, 1 page")
    print("=" * 60 + "\n")

    tests = [
        test_rent_narrow,
        test_rent_upper,
        test_size_filter,
        test_walk_filter,
        test_floor_plan_filter,
        test_building_age_filter,
        test_multi_ward,
        test_zero_expected,
    ]

    for test_fn in tests:
        try:
            await test_fn()
        except Exception as exc:
            record(test_fn.__name__, False, f"EXCEPTION: {exc}")

    print("\n" + "=" * 60)
    passed_count = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"Results: {passed_count}/{total} passed")
    if passed_count < total:
        print("\nFailed tests:")
        for name, ok, detail in results:
            if not ok:
                print(f"  ✗ {name}: {detail}")
    print("=" * 60)

    sys.exit(0 if passed_count == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
