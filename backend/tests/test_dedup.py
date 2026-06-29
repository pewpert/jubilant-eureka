"""Unit tests for cross-source dedup. Pure, no network/DB."""
from app.scrapers.manager import dedup_listings


def _l(**kw):
    base = dict(source_url="", building_name=None, nearest_station=None,
                rent=None, size_m2=None, floor=None, floor_plan=None)
    base.update(kw)
    return base


def test_cross_source_english_vs_japanese_name_merges():
    """e-housing's English name collapses against Suumo's Japanese name."""
    per_source = {
        "suumo": [_l(source_url="https://suumo.jp/x", building_name="ハーモニーレジデンス中野",
                     nearest_station="新井薬師前駅", rent=115000, size_m2=25.4, floor=3)],
        "ehousing": [_l(source_url="https://e-housing.jp/y", building_name="Harmony Residence Nakano",
                        nearest_station="新井薬師前駅", rent=115000, size_m2=25.4, floor=3)],
    }
    unique, merged = dedup_listings(per_source)
    assert len(unique) == 1
    assert merged == 1
    # The first-seen (suumo) wins.
    assert unique[0]["source_url"] == "https://suumo.jp/x"


def test_different_floors_kept_separate():
    """Same building/rent/size on different floors are different units — keep both."""
    per_source = {
        "suumo": [
            _l(source_url="u1", building_name="エントピア中野", nearest_station="中野駅",
               rent=126000, size_m2=30.0, floor=2),
            _l(source_url="u2", building_name="エントピア中野", nearest_station="中野駅",
               rent=126000, size_m2=30.0, floor=4),
        ],
    }
    unique, merged = dedup_listings(per_source)
    assert len(unique) == 2
    assert merged == 0


def test_thin_data_not_fuzzy_merged():
    """Missing rent/size/station → fuzzy layer must NOT collapse (avoid false merges)."""
    per_source = {
        "homes": [_l(source_url="a", building_name="A", nearest_station="中野駅", rent=None, size_m2=None)],
        "ehousing": [_l(source_url="b", building_name="B", nearest_station="中野駅", rent=None, size_m2=None)],
    }
    unique, merged = dedup_listings(per_source)
    assert len(unique) == 2
    assert merged == 0


def test_url_dedup_still_works():
    per_source = {
        "suumo": [_l(source_url="same", building_name="X", nearest_station="中野駅", rent=100000, size_m2=25.0, floor=1)],
        "homes": [_l(source_url="same", building_name="Y", nearest_station="高円寺駅", rent=200000, size_m2=40.0, floor=5)],
    }
    unique, merged = dedup_listings(per_source)
    assert len(unique) == 1  # second dropped by URL dedup


def test_size_rounding_tolerates_minor_diff():
    """25.44 vs 25.4 should be treated as the same size (rounded to 0.1)."""
    per_source = {
        "suumo": [_l(source_url="s", building_name="中野マンション", nearest_station="中野駅",
                     rent=110000, size_m2=25.44, floor=2)],
        "ehousing": [_l(source_url="e", building_name="Nakano Mansion", nearest_station="中野駅",
                        rent=110000, size_m2=25.41, floor=2)],
    }
    unique, merged = dedup_listings(per_source)
    assert len(unique) == 1
    assert merged == 1
