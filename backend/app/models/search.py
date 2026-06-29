"""Search criteria Pydantic models — what the user submits."""
from enum import Enum
from pydantic import BaseModel, Field, model_validator


# Tokyo ward codes used in Suumo URLs
TOKYO_WARDS = {
    "chiyoda": "13101",
    "chuo": "13102",
    "minato": "13103",
    "shinjuku": "13104",
    "bunkyo": "13105",
    "taito": "13106",
    "sumida": "13107",
    "koto": "13108",
    "shinagawa": "13109",
    "meguro": "13110",
    "ota": "13111",
    "setagaya": "13112",
    "shibuya": "13113",
    "nakano": "13114",
    "suginami": "13115",
    "toshima": "13116",
    "kita": "13117",
    "arakawa": "13118",
    "itabashi": "13119",
    "nerima": "13120",
    "adachi": "13121",
    "katsushika": "13122",
    "edogawa": "13123",
}


class FloorPlan(str, Enum):
    R1 = "1R"
    K1 = "1K"
    DK1 = "1DK"
    LDK1 = "1LDK"
    K2 = "2K"
    DK2 = "2DK"
    LDK2 = "2LDK"
    K3 = "3K"
    DK3 = "3DK"
    LDK3 = "3LDK"
    LDK4_PLUS = "4LDK+"


class WalkMinutes(int, Enum):
    FIVE = 5
    TEN = 10
    FIFTEEN = 15
    TWENTY = 20
    ANY = 9999


class Source(str, Enum):
    SUUMO = "suumo"
    HOMES = "homes"
    CHINTAI = "chintai"
    EHOUSING = "ehousing"


class SearchCriteria(BaseModel):
    """Everything the user can specify to filter their apartment search."""

    # Location
    wards: list[str] = Field(
        default_factory=list,
        description="Tokyo ward slugs (e.g. ['shibuya', 'shinjuku']). Empty = all wards.",
        examples=[["shibuya", "shinjuku"]],
    )
    station: str | None = Field(
        None,
        description="Free-text station name (e.g. '渋谷', 'Shinjuku'). Overrides wards if set.",
    )

    # Rent (in 万円 — e.g. 10.0 = ¥100,000)
    rent_min: float = Field(0.0, ge=0, description="Min rent in 万円 (e.g. 8.0 = ¥80,000)")
    rent_max: float = Field(30.0, ge=0, description="Max rent in 万円 (e.g. 20.0 = ¥200,000)")

    # Unit size
    size_min_m2: float = Field(0.0, ge=0, description="Minimum size in m²")
    size_max_m2: float = Field(9999.0, ge=0)

    # Room type
    floor_plans: list[FloorPlan] = Field(
        default_factory=list,
        description="Room types (empty = any)",
    )

    # Station access
    walk_minutes: WalkMinutes = Field(
        WalkMinutes.ANY,
        description="Max walk time from station in minutes",
    )

    # Building
    building_age_max: int = Field(9999, ge=0, description="Max building age in years")

    # Sources to scrape
    sources: list[Source] = Field(
        default=[Source.SUUMO, Source.HOMES, Source.CHINTAI],
        description="Which sites to scrape",
    )

    # Results limit per source
    max_pages: int = Field(3, ge=1, le=10, description="Pages to scrape per source")

    # Detail-page enrichment: after filtering, visit each surviving listing's
    # detail page to extract parking / amenity / foreigner-OK / earthquake data.
    # Capped because detail fetches are slow and more block-prone.
    enrich_details: bool = Field(
        True, description="Fetch detail pages to extract parking & amenity data"
    )
    max_detail_fetches: int = Field(
        60, ge=0, le=200,
        description="Max detail pages to fetch for enrichment. Enriches the "
                    "cheapest listings first (top-N). 0 = disabled.",
    )

    # Moto-parking filter (opt-in). When True, keep only listings whose detail
    # page CONFIRMED motorcycle parking ("available"). Never hides listings by
    # default — "unknown"/"none" only drop when this is explicitly enabled.
    moto_parking_only: bool = Field(
        False, description="Show only listings with confirmed motorcycle parking",
    )

    @model_validator(mode="after")
    def validate_rent_range(self):
        if self.rent_max < self.rent_min:
            raise ValueError("rent_max must be >= rent_min")
        return self

    def ward_codes(self) -> list[str]:
        """Return Suumo ward codes for selected wards."""
        if not self.wards:
            return list(TOKYO_WARDS.values())
        return [TOKYO_WARDS[w] for w in self.wards if w in TOKYO_WARDS]
