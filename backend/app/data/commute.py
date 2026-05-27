"""
Offline commute estimation: station → Tokyo Station / Shinjuku train times.

Why a curated table instead of a Maps/transit API:
  - The search area (Suginami/Nakano + neighbours) is a small, bounded set of
    ~20-30 stations. A hand-curated table is more reliable than a rate-limited
    external API, costs nothing, and adds no network dependency to a stack that
    already fights scraper blocking.
  - The per-listing estimate is deterministic: walk_to_station (scraped) +
    station→hub train time (this table). One fixed number per listing.

Trade-offs (be honest with the user):
  - Train times are approximate typical daytime times (rounded), NOT real-time.
  - Door-to-door uses the SCRAPED walk-to-nearest-station; it does not route
    from the exact building address (that would need a Maps API).
  - Stations not in the table return None (no score, flagged "unknown") rather
    than a misleading zero. Add new stations here when searching new wards.

Times sourced from the manual transit research in CLAUDE.md plus standard
line timings. transfers_tokyo = number of train changes to reach Tokyo Station
(0 = single-line direct), used as a small ranking penalty.
"""
from __future__ import annotations


# station (no 駅 suffix) -> minutes to hub + transfer count to Tokyo Station.
# tokyo_min / shinjuku_min are approximate typical train times (excludes the
# walk to the station, which we add separately from the scraped walk_minutes).
STATION_TO_HUB: dict[str, dict] = {
    # --- Marunouchi line: the prize — direct to BOTH Shinjuku and Tokyo Stn ---
    "新高円寺":     {"tokyo_min": 30, "shinjuku_min": 14, "transfers_tokyo": 0},
    "東高円寺":     {"tokyo_min": 28, "shinjuku_min": 12, "transfers_tokyo": 0},
    "新中野":       {"tokyo_min": 26, "shinjuku_min": 10, "transfers_tokyo": 0},
    "中野坂上":     {"tokyo_min": 24, "shinjuku_min": 8,  "transfers_tokyo": 0},
    "中野新橋":     {"tokyo_min": 28, "shinjuku_min": 12, "transfers_tokyo": 1},
    "中野富士見町": {"tokyo_min": 29, "shinjuku_min": 13, "transfers_tokyo": 1},
    "方南町":       {"tokyo_min": 31, "shinjuku_min": 15, "transfers_tokyo": 1},

    # --- JR Chuo/Sobu: fast to Shinjuku, one transfer (Ochanomizu/Kanda) to Tokyo ---
    "高円寺":       {"tokyo_min": 22, "shinjuku_min": 9,  "transfers_tokyo": 0},
    "阿佐ケ谷":     {"tokyo_min": 25, "shinjuku_min": 11, "transfers_tokyo": 0},
    "中野":         {"tokyo_min": 20, "shinjuku_min": 7,  "transfers_tokyo": 0},
    "東中野":       {"tokyo_min": 24, "shinjuku_min": 6,  "transfers_tokyo": 1},

    # --- Tozai / Toei Oedo ---
    "落合":         {"tokyo_min": 27, "shinjuku_min": 10, "transfers_tokyo": 1},
    "西新宿五丁目": {"tokyo_min": 26, "shinjuku_min": 5,  "transfers_tokyo": 1},

    # --- Seibu Shinjuku: to Shinjuku direct-ish, Tokyo needs a transfer ---
    "新井薬師前":   {"tokyo_min": 33, "shinjuku_min": 16, "transfers_tokyo": 1},
    "下井草":       {"tokyo_min": 36, "shinjuku_min": 19, "transfers_tokyo": 1},
    "都立家政":     {"tokyo_min": 35, "shinjuku_min": 18, "transfers_tokyo": 1},

    # --- Seibu Ikebukuro: via Ikebukuro, two hops to Tokyo ---
    "富士見台":     {"tokyo_min": 38, "shinjuku_min": 24, "transfers_tokyo": 2},

    # --- Keio / Keio Inokashira: Shibuya/Shinjuku oriented, Tokyo is awkward ---
    "桜上水":       {"tokyo_min": 37, "shinjuku_min": 17, "transfers_tokyo": 1},
    "富士見ヶ丘":   {"tokyo_min": 40, "shinjuku_min": 22, "transfers_tokyo": 2},
    "高井戸":       {"tokyo_min": 39, "shinjuku_min": 21, "transfers_tokyo": 2},
}

# Tokyo Station is weighted heavier than Shinjuku in the ranking score, per
# Daniel's priority (Shinkansen north). Each transfer adds a fixed penalty
# because changing trains is the real friction, not just the clock time.
TOKYO_WEIGHT = 2.0
SHINJUKU_WEIGHT = 1.0
TRANSFER_PENALTY_MIN = 4.0


def station_normalize(station: str | None) -> str:
    """Strip the 駅 suffix and whitespace so 新高円寺駅 and 新高円寺 both match."""
    if not station:
        return ""
    s = station.strip()
    # Take the first station if several are concatenated, then drop 駅 onwards.
    s = s.split()[0] if s.split() else s
    idx = s.find("駅")
    if idx != -1:
        s = s[:idx]
    return s.strip()


def estimate_commute(station: str | None, walk_minutes: int | None) -> dict | None:
    """
    Estimate door-to-door commute for one listing.

    Returns a dict with:
      tokyo_total    : walk + train minutes to Tokyo Station
      shinjuku_total : walk + train minutes to Shinjuku
      score          : lower = better (Tokyo-weighted + transfer penalty)
    or None if the station isn't in the table (caller should treat as unknown,
    not zero).
    """
    key = station_normalize(station)
    hub = STATION_TO_HUB.get(key)
    if hub is None:
        return None

    walk = walk_minutes if walk_minutes is not None else 0
    tokyo_total = walk + hub["tokyo_min"]
    shinjuku_total = walk + hub["shinjuku_min"]

    score = (
        TOKYO_WEIGHT * tokyo_total
        + SHINJUKU_WEIGHT * shinjuku_total
        + TRANSFER_PENALTY_MIN * hub["transfers_tokyo"]
    )
    return {
        "tokyo_total": tokyo_total,
        "shinjuku_total": shinjuku_total,
        "score": round(score, 1),
    }
