"""Unit tests for the shared field normalisers. Pure, no network/DB."""
from datetime import date

from app.scrapers.normalize import (
    parse_yen, parse_size, parse_walk, parse_floor, parse_building_age,
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
