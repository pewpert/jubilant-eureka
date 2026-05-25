"""
Shared parser for listing *detail-page* amenity data.

Search-results cards on Suumo/Homes/Chintai don't carry parking or amenity
info — it lives in the 設備 (equipment) / 駐車場 (parking) section of each
listing's detail page. This module turns the raw detail-page text into a small
set of structured flags that the scrapers attach to their listing dicts.

Design notes:
  - Parking flags are 3-state: "available" | "none" | "unknown".
    "unknown" is the default and means the page simply didn't mention it —
    NOT that there is no parking. Many real listings omit parking even when it
    exists, which is why downstream we treat these as badges/sort, not a hard
    filter.
  - We work on plain text (BeautifulSoup .get_text) rather than per-site DOM
    selectors, so the same logic works across all three portals.
"""
import re


# Japanese keyword sets. Order matters: motorcycle (バイク) must be checked
# before generic 駐車 so a bike-only listing isn't miscounted as car parking.
_MOTORCYCLE_TERMS = ["バイク置き場", "バイク置場", "バイク駐車", "バイク置", "バイク"]
_BICYCLE_TERMS = ["駐輪場", "自転車置き場", "自転車置場", "サイクルポート"]
_CAR_TERMS = ["駐車場", "車庫", "カーポート"]

# Phrases that indicate the amenity is explicitly absent / unavailable.
_NONE_TERMS = ["無", "なし", "無し", "空無", "—", "－", "不可"]

_FOREIGNER_OK_TERMS = ["外国人相談", "外国人可", "外国人入居可", "外国籍相談"]


# Markers that signal availability immediately after a keyword.
_AVAILABLE_TERMS = ["有", "あり", "可", "空有", "込"]

# Boundaries that end an amenity's value field — a marker past one of these
# belongs to the *next* field, not this one. Includes all amenity keywords AND
# the foreigner keywords (whose 可 would otherwise read as a positive marker),
# so "駐車場 無 外国人相談可" doesn't mark car parking as available.
_FIELD_BOUNDARIES = (
    _MOTORCYCLE_TERMS + _BICYCLE_TERMS + _CAR_TERMS + _FOREIGNER_OK_TERMS
    + ["外国人", "ペット", "、", "／", "/", "｜", "|"]
)


def _classify(text: str, terms: list[str]) -> str:
    """
    Return "available" / "none" / "unknown" for an amenity given its keyword set.

    Find the keyword, then inspect the text after it — but only up to the next
    field boundary (another amenity/field keyword or separator) so one field's
    value can't bleed into another. Within that window, whichever marker appears
    FIRST decides: an availability marker (有/あり/可) → available; a negation
    marker (無/なし/不可) → none. If neither appears, the keyword's mere presence
    counts as available.
    """
    for term in terms:
        idx = text.find(term)
        if idx == -1:
            continue
        start = idx + len(term)
        window = text[start: start + 14]
        # Trim the window at the first boundary that isn't the term we matched.
        cut = len(window)
        for b in _FIELD_BOUNDARIES:
            if b in term:
                continue
            bpos = window.find(b)
            if bpos != -1:
                cut = min(cut, bpos)
        window = window[:cut]

        neg_pos = min((window.find(n) for n in _NONE_TERMS if n in window), default=-1)
        pos_pos = min((window.find(p) for p in _AVAILABLE_TERMS if p in window), default=-1)
        if neg_pos != -1 and (pos_pos == -1 or neg_pos < pos_pos):
            return "none"
        return "available"
    return "unknown"


def parse_detail_features(detail_text: str, built_year: int | None = None) -> dict:
    """
    Extract amenity flags from a listing detail page's plain text.

    Args:
        detail_text: full visible text of the detail page (BeautifulSoup get_text)
        built_year: numeric build year if already known, used to infer the
            earthquake standard when the page doesn't state it explicitly.

    Returns a dict with: motorcycle_parking, bicycle_parking, car_parking,
    foreigner_ok, earthquake_standard, features (list of matched raw terms).
    """
    text = detail_text or ""

    motorcycle = _classify(text, _MOTORCYCLE_TERMS)
    bicycle = _classify(text, _BICYCLE_TERMS)
    car = _classify(text, _CAR_TERMS)

    foreigner_ok: bool | None = None
    if any(t in text for t in _FOREIGNER_OK_TERMS):
        foreigner_ok = True

    earthquake = _earthquake_standard(text, built_year)

    # Collect the matched amenity terms so the UI can show what was found.
    features: list[str] = []
    if motorcycle == "available":
        features.append("バイク置き場")
    if bicycle == "available":
        features.append("駐輪場")
    if car == "available":
        features.append("駐車場")
    if foreigner_ok:
        features.append("外国人相談可")
    if earthquake == "new":
        features.append("新耐震基準")

    return {
        "motorcycle_parking": motorcycle,
        "bicycle_parking": bicycle,
        "car_parking": car,
        "foreigner_ok": foreigner_ok,
        "earthquake_standard": earthquake,
        "features": features,
    }


def _earthquake_standard(text: str, built_year: int | None) -> str:
    """Infer post-1981 (新耐震) vs pre-1981 (旧耐震) standard."""
    if "新耐震" in text:
        return "new"
    if "旧耐震" in text:
        return "old"
    # Fall back to the build year. The 新耐震基準 took effect June 1981, so any
    # building completed from 1982 onward is unambiguously post-standard.
    if built_year is not None:
        if built_year >= 1982:
            return "new"
        if built_year <= 1980:
            return "old"
    return "unknown"
