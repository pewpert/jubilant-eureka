"""SQLAlchemy ORM models."""
import uuid
from datetime import datetime

from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class SearchJob(Base):
    """Represents a user-initiated search request."""
    __tablename__ = "search_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending | running | completed | failed
    criteria: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_results: Mapped[int] = mapped_column(Integer, default=0)
    scrape_stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    listings: Mapped[list["Listing"]] = relationship(
        "Listing", back_populates="job", cascade="all, delete-orphan"
    )


class Listing(Base):
    """A single apartment listing scraped from any source."""
    __tablename__ = "listings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_jobs.id"), nullable=False
    )

    # Source
    source: Mapped[str] = mapped_column(String(50))   # "suumo" | "homes" | "chintai"
    source_url: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Core fields
    title: Mapped[str] = mapped_column(Text)
    building_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    rent: Mapped[int | None] = mapped_column(Integer, nullable=True)       # yen/month
    management_fee: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deposit: Mapped[int | None] = mapped_column(Integer, nullable=True)    # shikikin
    key_money: Mapped[int | None] = mapped_column(Integer, nullable=True)  # reikin

    # Location
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    ward: Mapped[str | None] = mapped_column(String(50), nullable=True)
    nearest_station: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nearest_line: Mapped[str | None] = mapped_column(String(100), nullable=True)
    walk_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Unit details
    floor_plan: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 1K, 2LDK…
    size_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_floors: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Building
    building_age_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    built_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    building_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Amenities / parking (populated from the listing detail page).
    # Parking fields use a 3-state string: "available" | "none" | "unknown".
    # "unknown" means the detail page didn't mention it — NOT that there is none.
    motorcycle_parking: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bicycle_parking: Mapped[str | None] = mapped_column(String(20), nullable=True)
    car_parking: Mapped[str | None] = mapped_column(String(20), nullable=True)
    foreigner_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # "new" (post-1981 新耐震) | "old" (pre-1981 旧耐震) | "unknown"
    earthquake_standard: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Features (stored as JSON list of strings — raw 設備 equipment terms)
    features: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Media
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    scraped_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    job: Mapped["SearchJob"] = relationship("SearchJob", back_populates="listings")
