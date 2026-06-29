"""
Offline parser tests — feed each scraper a saved real-world HTML fixture and
assert it extracts plausible listings. No network, no browser, no DB.

These guard against the most common regression: a site tweaks its markup and a
CSS selector / regex silently starts returning null fields or zero listings.
Because parsing is now pure (parse_html / _parse_html take a string), we can run
it against a committed fixture in milliseconds.

Fixtures live in tests/fixtures/ and are real saved search pages. Refresh them
with a live curl when a site's markup changes (and update the assertions).
"""
from app.models.search import SearchCriteria, FloorPlan, WalkMinutes, Source
from app.scrapers.suumo import SuumoScraper, _looks_blocked
from app.scrapers.homes import HomesScraper
from app.scrapers.chintai import ChintaiScraper
from app.scrapers.ehousing import EhousingScraper


def _criteria(source: Source) -> SearchCriteria:
    return SearchCriteria(
        wards=["nakano"], rent_min=10, rent_max=12, size_min_m2=25,
        floor_plans=[FloorPlan.LDK1, FloorPlan.DK1],
        walk_minutes=WalkMinutes.TEN, sources=[source],
    )


def _has_core_fields(listings: list[dict]) -> bool:
    """At least one listing carries rent + size + a station + a detail URL."""
    return any(
        l.get("rent") and l.get("size_m2") and l.get("nearest_station") and l.get("source_url")
        for l in listings
    )


def test_suumo_parse(suumo_html):
    assert not _looks_blocked(suumo_html)
    listings = SuumoScraper(_criteria(Source.SUUMO))._parse_html(suumo_html)
    assert len(listings) >= 20
    assert _has_core_fields(listings)
    # Every listing must carry the source-shape contract keys.
    for l in listings:
        assert "rent" in l and "floor_plan" in l and "walk_minutes" in l
        assert l["source"] == "suumo"


def test_homes_parse(homes_html):
    s = HomesScraper(_criteria(Source.HOMES))
    assert not s.is_blocked(homes_html)        # mod-mergeBuilding marker present
    listings = s.parse_html(homes_html)
    assert len(listings) >= 20
    assert _has_core_fields(listings)
    for l in listings:
        assert l["source"] == "homes"


def test_chintai_parse(chintai_html):
    s = ChintaiScraper(_criteria(Source.CHINTAI))
    assert not s.is_blocked(chintai_html)      # cassette_item marker present
    listings = s.parse_html(chintai_html)
    assert len(listings) >= 10
    assert _has_core_fields(listings)
    for l in listings:
        assert l["source"] == "chintai"


def test_ehousing_parse(ehousing_html):
    s = EhousingScraper(_criteria(Source.EHOUSING))
    assert not s.is_blocked(ehousing_html)     # RSC payload present
    listings, has_more = s._parse_with_meta(ehousing_html)
    # The committed fixture is the base-case search → 27 listings.
    assert len(listings) == 27
    assert _has_core_fields(listings)
    # e-housing uniquely gives coordinates — needed for fuzzy dedup.
    assert all(l.get("latitude") and l.get("longitude") for l in listings)
    for l in listings:
        assert l["source"] == "ehousing"
        assert l["source_url"].startswith("https://e-housing.jp/properties/")


def test_ehousing_url_building():
    c = SearchCriteria(
        wards=["suginami", "nakano"], rent_min=10, rent_max=12, size_min_m2=25,
        floor_plans=[FloorPlan.LDK1, FloorPlan.DK1], walk_minutes=WalkMinutes.TEN,
        sources=[Source.EHOUSING],
    )
    url = EhousingScraper(c).build_search_url(1)
    assert "wards=11" in url and "wards=10" in url     # suginami, nakano
    assert "price_from=100000" in url and "price_to=120000" in url
    assert "layout=1LDK,1DK" in url                    # comma-joined
    assert "area_from=25" in url


def test_ehousing_skips_uncovered_wards():
    """Wards e-housing doesn't cover are dropped; covered ones remain."""
    c = SearchCriteria(
        wards=["nakano", "adachi"],  # adachi not on e-housing
        sources=[Source.EHOUSING],
    )
    s = EhousingScraper(c)
    assert s._ward_ids() == [10]  # only nakano


def test_block_detection_on_empty():
    """All scrapers treat empty / tiny HTML as blocked."""
    for cls in (SuumoScraper, HomesScraper, ChintaiScraper, EhousingScraper):
        s = cls(_criteria(Source.SUUMO))
        assert s.is_blocked("") is True
        assert s.is_blocked("<html>tiny</html>") is True
