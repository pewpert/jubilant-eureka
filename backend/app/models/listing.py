"""Pydantic models for listing output (API responses)."""
import uuid
from datetime import datetime
from pydantic import BaseModel


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
    walk_minutes: int | None
    floor_plan: str | None
    size_m2: float | None
    floor: int | None
    total_floors: int | None
    building_age_years: int | None
    built_year: int | None
    building_type: str | None
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

    model_config = {"from_attributes": True}


class SearchJobWithListings(SearchJobOut):
    listings: list[ListingOut] = []
