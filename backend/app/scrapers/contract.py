"""
The raw-listing contract every scraper emits.

Before this module, each scraper hand-assembled a ~20-key dict by literal. A
forgotten or misspelled key was only discovered at DB-insert time (or silently
dropped by the column whitelist in tasks/scrape.py). `RawListing` makes the
shape a single source of truth with safe defaults, so a scraper *cannot* emit a
malformed listing.

`to_dict()` returns exactly the keys the downstream pipeline (manager dedup /
filter / commute / enrichment) and the Listing ORM insert already expect, so
adopting this is a drop-in for the old literal dicts. Extra in-memory-only fields
(latitude/longitude) are included in to_dict() too — the DB insert in
tasks/scrape.py whitelists columns, so non-column keys are harmless there and are
available to the manager for coordinate-based dedup.
"""

from dataclasses import dataclass, field, asdict


# Parking is 3-state: "available" | "none" | "unknown". "unknown" is the default
# and means "not stated", NOT "confirmed absent" — see detail_features.py.
PARKING_UNKNOWN = "unknown"


@dataclass
class RawListing:
    # --- identity / source ---
    source_url: str = ""
    source: str = "unknown"

    # --- naming ---
    title: str = ""
    building_name: str | None = None

    # --- money (yen) ---
    rent: int | None = None
    management_fee: int | None = None
    deposit: int | None = None
    key_money: int | None = None

    # --- location ---
    address: str | None = None
    ward: str | None = None
    nearest_station: str | None = None
    nearest_line: str | None = None
    walk_minutes: int | None = None
    # In-memory only (not a DB column) — used for cross-source fuzzy dedup.
    latitude: float | None = None
    longitude: float | None = None

    # --- unit ---
    floor_plan: str | None = None
    size_m2: float | None = None
    floor: int | None = None
    total_floors: int | None = None

    # --- building ---
    building_age_years: int | None = None
    built_year: int | None = None
    building_type: str | None = None

    # --- amenities (filled by detail enrichment; defaults = "not stated") ---
    motorcycle_parking: str | None = PARKING_UNKNOWN
    bicycle_parking: str | None = PARKING_UNKNOWN
    car_parking: str | None = PARKING_UNKNOWN
    foreigner_ok: bool | None = None
    earthquake_standard: str | None = None

    # --- media / misc ---
    features: list = field(default_factory=list)
    image_url: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
