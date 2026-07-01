"""Unit tests for the shared field normalisers. Pure, no network/DB."""
from datetime import date

from app.models.search import SearchCriteria, WalkMinutes
from app.scrapers.normalize import (
    parse_yen, parse_size, parse_walk, parse_floor, parse_building_age,
    common_search_params,
)


def test_parse_yen():
    assert parse_yen("8.5万円") == 85000
    assert parse_yen("12万円") == 120000
    assert parse_yen("85,000円") == 85000
    assert parse_yen("11.4万円 6,000円") == 114000   # rent, not the fee
    assert parse_yen("10.0万") == 100000
    assert parse_yen(None) is None
    assert parse_yen("-") is None
    assert parse_yen("") is None


def test_parse_size():
    assert parse_size("35.5m²") == 35.5
    assert parse_size("30m2") == 30.0
    assert parse_size("1LDK 37.58m²") == 37.58
    assert parse_size(None) is None
    assert parse_size("ワンルーム") is None


def test_parse_walk():
    assert parse_walk("歩10分") == 10
    assert parse_walk("徒歩5分") == 5
    assert parse_walk("10分") == 10
    assert parse_walk(None) is None
    assert parse_walk("駅近") is None


def test_parse_floor():
    assert parse_floor("3階/10階建") == (3, 10)
    assert parse_floor("3階") == (3, None)
    assert parse_floor(None) == (None, None)
    assert parse_floor("地下1階") == (1, None)  # picks the digit


def test_parse_building_age():
    assert parse_building_age("築10年") == (10, None)
    assert parse_building_age("新築") == (0, None)
    y = date.today().year
    assert parse_building_age("2015年築") == (y - 2015, 2015)
    assert parse_building_age("2015年") == (y - 2015, 2015)
    assert parse_building_age(None) == (None, None)


_NAMES = {"rent_min": "cb", "rent_max": "ct", "size_min": "mb",
          "size_max": "mt", "walk": "et", "page": "page"}


def test_common_params_manyen_vs_yen():
    c = SearchCriteria(rent_min=10, rent_max=12, size_min_m2=25,
                       walk_minutes=WalkMinutes.TEN)
    # 万円 mode (suumo/homes): rent passed as-is
    assert ("cb", "10.0") in common_search_params(c, _NAMES)
    # yen mode (chintai/ehousing): rent ×10000
    yen = common_search_params(c, {"rent_min": "yen_from", "rent_max": "yen_to"}, rent_in_yen=True)
    assert ("yen_from", "100000") in yen and ("yen_to", "120000") in yen


def test_common_params_skips_defaults_and_page():
    c = SearchCriteria()  # rent_max defaults to 30, everything else off
    p = dict(common_search_params(c, _NAMES, page_num=1))
    assert p == {"ct": "30.0"}          # only rent_max present; page skipped on page 1
    assert common_search_params(c, _NAMES, page_num=3)[-1] == ("page", "3")


def test_common_params_omitted_name_skips_field():
    # A site without a walk param (name omitted) emits nothing for walk.
    c = SearchCriteria(walk_minutes=WalkMinutes.FIVE)
    names = {"rent_max": "ct"}  # no "walk" key
    assert all(k != "et" for k, _ in common_search_params(c, names))
