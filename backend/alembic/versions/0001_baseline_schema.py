"""baseline schema — search_jobs + listings as of the current models

This is the BASELINE migration. It reflects the schema that the running stack
already has (search_jobs + listings, including the amenity/parking/commute
columns added across prior sessions).

On an EXISTING database whose tables were created by the old `create_all` boot
path, do NOT run upgrade (it would try to re-create existing tables). Instead
mark this revision as already-applied:

    alembic stamp 0001_baseline

On a FRESH database, `alembic upgrade head` creates everything.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "search_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("criteria", JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("progress", sa.Text(), nullable=True),
        sa.Column("total_results", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scrape_stats", JSON, nullable=True),
    )

    op.create_table(
        "listings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("search_jobs.id"), nullable=False),
        # Source
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_id", sa.String(length=100), nullable=True),
        # Core
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("building_name", sa.Text(), nullable=True),
        sa.Column("rent", sa.Integer(), nullable=True),
        sa.Column("management_fee", sa.Integer(), nullable=True),
        sa.Column("deposit", sa.Integer(), nullable=True),
        sa.Column("key_money", sa.Integer(), nullable=True),
        # Location
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("ward", sa.String(length=50), nullable=True),
        sa.Column("nearest_station", sa.String(length=100), nullable=True),
        sa.Column("nearest_line", sa.String(length=100), nullable=True),
        sa.Column("walk_minutes", sa.Integer(), nullable=True),
        # Unit
        sa.Column("floor_plan", sa.String(length=20), nullable=True),
        sa.Column("size_m2", sa.Float(), nullable=True),
        sa.Column("floor", sa.Integer(), nullable=True),
        sa.Column("total_floors", sa.Integer(), nullable=True),
        # Building
        sa.Column("building_age_years", sa.Integer(), nullable=True),
        sa.Column("built_year", sa.Integer(), nullable=True),
        sa.Column("building_type", sa.String(length=50), nullable=True),
        # Amenities / parking
        sa.Column("motorcycle_parking", sa.String(length=20), nullable=True),
        sa.Column("bicycle_parking", sa.String(length=20), nullable=True),
        sa.Column("car_parking", sa.String(length=20), nullable=True),
        sa.Column("foreigner_ok", sa.Boolean(), nullable=True),
        sa.Column("earthquake_standard", sa.String(length=20), nullable=True),
        # Commute estimate
        sa.Column("commute_tokyo_min", sa.Integer(), nullable=True),
        sa.Column("commute_shinjuku_min", sa.Integer(), nullable=True),
        sa.Column("commute_score", sa.Float(), nullable=True),
        # Features / media
        sa.Column("features", JSON, nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("scraped_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_listings_job_id", "listings", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_listings_job_id", table_name="listings")
    op.drop_table("listings")
    op.drop_table("search_jobs")
