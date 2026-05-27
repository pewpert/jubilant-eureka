"""Pydantic models for listing output (API responses)."""
import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class ListingOut(BaseModel):
    id: uuid.UUID
    source: str
    source_url: str
    title: str
    building_name: str | None
    rent: int | None            # yen/month
    management_fee: int | None
    deposit: int | None
    key_money: int | None
    address: str | None
    ward: str | None
    nearest_station: str | None
    nearest_line: str | None = None
    walk_minutes: int | None
    floor_plan: str | None
    size_m2: float | None
    floor: int | None
    total_floors: int | None
    building_age_years: int | None
    built_year: int | None
    building_type: str | None
    motorcycle_parking: str | None = None   # "available" | "none" | "unknown"
    bicycle_parking: str | None = None
    car_parking: str | None = None
    foreigner_ok: bool | None = None
    earthquake_standard: str | None = None  # "new" | "old" | "unknown"
    commute_tokyo_min: int | None = None
    commute_shinjuku_min: int | None = None
    commute_score: float | None = None
    features: list[str] | None
    image_url: str | None
    scraped_at: datetime

    model_config = {"from_attributes": True}


class SearchJobOut(BaseModel):
    id: uuid.UUID
    status: str
    criteria: dict
    created_at: datetime
    completed_at: datetime | None
    total_results: int
    error: str | None
    progress: str | None
    scrape_stats: dict | None = None

    model_config = {"from_attributes": True}


class SearchJobWithListings(SearchJobOut):
    listings: list[ListingOut] = []


# --- Debug response models ---

class ExclusionBreakdown(BaseModel):
    rent: int = 0
    size: int = 0
    walk: int = 0
    building_age: int = 0
    floor_plan: int = 0
    unparseable_rent: int = 0


class SourceDebugStats(BaseModel):
    url_used: str | None = None
    raw_count: int = 0
    passed_count: int = 0
    excluded_by: ExclusionBreakdown = Field(default_factory=ExclusionBreakdown)
    error: str | None = None
    blocked: bool = False
    sample_excluded: list[dict] = Field(default_factory=list)
    sample_near_miss: list[dict] = Field(default_factory=list)


class DebugResponse(BaseModel):
    job_id: str
    status: str
    criteria: dict
    per_source: dict[str, SourceDebugStats]
    total_raw: int
    total_passed: int
    dominant_filter: str | None
