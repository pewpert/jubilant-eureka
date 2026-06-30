"""Commute estimate + station-name folding. Pure, no network/DB."""
from app.data.commute import estimate_commute, station_normalize


def test_suffix_and_ke_folding():
    # 駅 suffix and the ケ/ヶ variant all collapse to one key.
    assert station_normalize("新高円寺駅") == "新高円寺"
    assert station_normalize("阿佐ヶ谷") == station_normalize("阿佐ケ谷") == "阿佐ケ谷"
    assert station_normalize("南阿佐ヶ谷駅") == "南阿佐ケ谷"
    assert station_normalize(None) == ""


def test_estimate_adds_walk():
    # door-to-door = walk + table train time
    r = estimate_commute("荻窪", 5)
    assert r is not None
    assert r["tokyo_total"] == 27 + 5
    assert r["shinjuku_total"] == 12 + 5


def test_both_ke_forms_resolve_equally():
    assert estimate_commute("阿佐ヶ谷駅", 3) == estimate_commute("阿佐ケ谷", 3)


def test_unknown_station_is_none():
    # Out-of-table station → None (caller keeps it as "unknown", never a fake 0).
    assert estimate_commute("葛西", 5) is None
