"""
Shared parser for the 交通 (transport) field across Suumo / Homes / Chintai.

Input format varies slightly by site:
  "東京メトロ丸ノ内線/新高円寺駅 歩5分"   (Suumo)
  "丸ノ内線/新高円寺駅 徒歩5分"          (Homes)
  "東京メトロ丸ノ内線 新高円寺駅 徒歩5分" (Chintai — space-delimited)
  "JR中央線/高円寺駅 徒歩8分"

Returns (line, station, walk_minutes). Any of the three may be None.
"""

import re

# Walk time: "徒歩5分" or just "歩5分" (Suumo)
_WALK_RE = re.compile(r"徒?歩\s*(\d+)\s*分")
# Station token — everything up to 駅
_STATION_RE = re.compile(r"([\u3040-\u30ff\u4e00-\u9fff\w・ー]+駅)")


def parse_transport(text: str | None) -> tuple[str | None, str | None, int | None]:
    if not text:
        return None, None, None

    t = text.strip()

    walk = None
    m = _WALK_RE.search(t)
    if m:
        walk = int(m.group(1))
        t = t[: m.start()].strip()

    station = None
    sm = _STATION_RE.search(t)
    if sm:
        station = sm.group(1)
        before = t[: sm.start()].rstrip(" /／・")
        line = before or None
    else:
        line = t or None

    if line:
        line = line.rstrip(" /／・").strip()
        if not line:
            line = None

    return line, station, walk
