"""Unit tests for dedup. Pure, no network/DB."""
from app.scrapers.manager import dedup_listings


def _l(**kw):
    base = dict(source_url="", building_name=None, nearest_station=None,
                rent=None, size_m2=None, floor=None, floor_plan=None)
    base.update(kw)
    return base


def test_exact_dupe_collapsed():
    """Same building+station+rent+size+floor under different URLs → one row."""
    per_source = {
        "suumo": [_l(source_url="a", building_name="エントピア中野", nearest_station="中野駅",
                     rent=126000, size_m2=30.0, floor=2)],
        "homes": [_l(source_url="b", building_name="エントピア中野", nearest_station="中野駅",
                     rent=126000, size_m2=30.0, floor=2)],
    }
    assert len(dedup_listings(per_source)) == 1


def test_different_floors_kept_separate():
    per_source = {"suumo": [
        _l(source_url="u1", building_name="エントピア中野", nearest_station="中野駅", rent=126000, size_m2=30.0, floor=2),
        _l(source_url="u2", building_name="エントピア中野", nearest_station="中野駅", rent=126000, size_m2=30.0, floor=4),
    ]}
    assert len(dedup_listings(per_source)) == 2


def test_distinct_units_same_station_rent_size_kept():
    """Different buildings sharing station/rent/size/floor must NOT merge — building
    name is load-bearing. This is the over-merge the removed fuzzy layer caused."""
    per_source = {"homes": [
        _l(source_url="a", building_name="A中野", nearest_station="東中野駅", rent=171500, size_m2=31.0, floor=1),
        _l(source_url="b", building_name="B中野", nearest_station="東中野駅", rent=171500, size_m2=31.0, floor=1),
    ]}
    assert len(dedup_listings(per_source)) == 2


def test_url_dedup_still_works():
    per_source = {
        "suumo": [_l(source_url="same", building_name="X", nearest_station="中野駅", rent=100000, size_m2=25.0, floor=1)],
        "homes": [_l(source_url="same", building_name="Y", nearest_station="高円寺駅", rent=200000, size_m2=40.0, floor=5)],
    }
    assert len(dedup_listings(per_source)) == 1
