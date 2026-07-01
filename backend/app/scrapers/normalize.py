"""
Shared field normalisers for all scrapers.

Every portal renders rent / size / walk / floor / building age as free-form
Japanese text, and the parsing rules are identical across sites. These helpers
used to be copy-pasted (as private `_parse_*` functions) into suumo.py, homes.py
and chintai.py — three near-identical copies that drifted independently. They now
live here, are unit-tested in tests/test_normalize.py, and each scraper imports
them.

All functions are total and defensive: they accept None / junk and return None
rather than raising, because scraper input is untrusted HTML.
"""

import re
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.search import SearchCriteria


def parse_yen(text: str | None) -> int | None:
    """'8.5万円' / '85,000円' / '8.5万円 6,000円' → int yen (first amount)."""
    if not text:
        return None
    text = text.strip().replace(",", "").replace(" ", "")
    m = re.search(r"([\d.]+)\s*万", text)
    if m:
        return int(float(m.group(1)) * 10000)
    m = re.search(r"(\d+)\s*円", text)
    return int(m.group(1)) if m else None


def parse_size(text: str | None) -> float | None:
    """'35.5m²' / '35.5m2' → 35.5"""
    if not text:
        return None
    m = re.search(r"([\d.]+)\s*m", text, re.IGNORECASE)
    return float(m.group(1)) if m else None


def parse_walk(text: str | None) -> int | None:
    """'歩10分' / '徒歩10分' / '10分' → 10"""
    if not text:
        return None
    m = re.search(r"(\d+)\s*分", text)
    return int(m.group(1)) if m else None


def parse_floor(text: str | None) -> tuple[int | None, int | None]:
    """'3階/10階建' → (3, 10); '3階' → (3, None)"""
    if not text:
        return None, None
    m = re.search(r"(\d+)\s*階\s*/\s*(\d+)\s*階建", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d+)\s*階", text)
    if m:
        return int(m.group(1)), None
    return None, None


def parse_building_age(text: str | None) -> tuple[int | None, int | None]:
    """
    '築10年' → (10, None); '新築' → (0, None); '2015年築' / '2015年' → (age, 2015).

    Returns (age_years, built_year). Either may be None. When a 4-digit year is
    present we also compute age relative to the current year so callers get both.
    """
    if not text:
        return None, None
    if "新築" in text:
        return 0, None
    # Explicit build year, e.g. '2015年築' or '2015年' — prefer this (gives built_year too).
    m = re.search(r"(\d{4})年", text)
    if m:
        year = int(m.group(1))
        return date.today().year - year, year
    m = re.search(r"築\s*(\d+)\s*年", text)
    if m:
        return int(m.group(1)), None
    return None, None


def common_search_params(
    c: "SearchCriteria",
    names: dict[str, str],
    page_num: int = 1,
    rent_in_yen: bool = False,
) -> list[tuple[str, str]]:
    """
    Build the rent/size/walk/page query params shared by every portal's search URL.

    The 4 scrapers differ only in param NAMES and whether rent is in yen or 万円,
    so this takes a name-map and emits the present params; each scraper appends its
    own site-specific params (wards, floor_plans, building_age) inline.

    names keys (omit a key to skip that param for a site):
      rent_min, rent_max, size_min, size_max, walk, page
    rent_in_yen: True → rent ×10000 (chintai/ehousing), False → 万円 as-is (suumo/homes).
    """
    p: list[tuple[str, str]] = []
    rent_mul = 10000 if rent_in_yen else 1

    def add(key: str, present: bool, value):
        name = names.get(key)
        if name and present:
            p.append((name, str(value)))

    add("rent_min", c.rent_min > 0, int(c.rent_min * rent_mul) if rent_in_yen else c.rent_min)
    add("rent_max", c.rent_max < 9999, int(c.rent_max * rent_mul) if rent_in_yen else c.rent_max)
    add("size_min", c.size_min_m2 > 0, int(c.size_min_m2))
    add("size_max", c.size_max_m2 < 9999, int(c.size_max_m2))
    add("walk", c.walk_minutes.value < 9999, c.walk_minutes.value)
    add("page", page_num > 1, page_num)
    return p
