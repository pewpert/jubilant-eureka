"""
Seed script — inserts the 5 confirmed April 2026 listings into the database.

These are real listings found via manual research on homes.co.jp.
They serve as test data so the frontend can be evaluated without running
a live scrape.

Usage:
    # From project root (with DB running via docker compose):
    docker compose exec backend python scripts/seed_listings.py

    # Or directly (with DB reachable on localhost):
    DATABASE_URL=postgresql://appuser:apppassword@localhost:5432/tokyo_apartments \
        python scripts/seed_listings.py
"""

import os
import sys
import uuid
from datetime import datetime, timezone

# Allow running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.db.models import Base, SearchJob, Listing

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://appuser:apppassword@localhost:5432/tokyo_apartments",
).replace("+asyncpg", "")  # seed script uses sync driver

engine = create_engine(DB_URL, echo=False)
Base.metadata.create_all(engine)

# -----------------------------------------------------------------------
# Base case search criteria (matches CLAUDE.md)
# -----------------------------------------------------------------------
SEED_CRITERIA = {
    "wards": ["suginami", "kita"],
    "station": None,
    "rent_min": 10.0,
    "rent_max": 12.0,
    "size_min_m2": 25.0,
    "size_max_m2": 40.0,
    "floor_plans": ["1LDK", "1DK"],
    "walk_minutes": 10,
    "building_age_max": 9999,
    "sources": ["homes"],
    "max_pages": 3,
}

# -----------------------------------------------------------------------
# Confirmed listings (April 2026, homes.co.jp)
# Initial cost formula:
#   deposit + key_money + agency_fee (1 month × 1.1) + ¥100,000 misc
# -----------------------------------------------------------------------
SEED_LISTINGS = [
    {
        "source": "homes",
        "source_url": "https://www.homes.co.jp/chintai/room/ea5b82044b28d7e4f6f95930e49a0b716ae9bf60/",
        "title": "プラムガーデン",
        "building_name": "プラムガーデン",
        "rent": 100_000,
        "management_fee": 3_000,
        "deposit": 100_000,   # 1 month
        "key_money": 100_000, # 1 month
        "address": "東京都杉並区",
        "ward": "suginami",
        "nearest_station": "新高円寺駅",
        "walk_minutes": 5,
        "floor_plan": "1LDK",
        "size_m2": 30.0,
        "floor": None,
        "total_floors": None,
        "building_age_years": None,  # post-1981 confirmed
        "built_year": None,
        "building_type": "マンション",
        "features": ["新耐震基準", "post-1981"],
        "image_url": None,
    },
    {
        "source": "homes",
        "source_url": "https://www.homes.co.jp/chintai/room/1658ec076eb2f71203bdac0ffaa71ccfa7375e67/",
        "title": "三井マンション",
        "building_name": "三井マンション",
        "rent": 92_000,
        "management_fee": 0,
        "deposit": 92_000,    # 1 month
        "key_money": 0,
        "address": "東京都杉並区",
        "ward": "suginami",
        "nearest_station": "新高円寺駅",
        "walk_minutes": 9,
        "floor_plan": "1LDK",
        "size_m2": 33.0,
        "floor": None,
        "total_floors": None,
        "building_age_years": None,  # pre-1981 — flag for user
        "built_year": None,
        "building_type": "マンション",
        "features": ["旧耐震基準", "pre-1981 ⚠️"],
        "image_url": None,
    },
    {
        "source": "homes",
        "source_url": "https://www.homes.co.jp/chintai/b-31035960093672/",
        "title": "エクセレンスハイツ",
        "building_name": "エクセレンスハイツ",
        "rent": 94_000,
        "management_fee": 1_000,
        "deposit": 94_000,    # 1 month
        "key_money": 94_000,  # 1 month
        "address": "東京都杉並区",
        "ward": "suginami",
        "nearest_station": "高円寺駅",
        "walk_minutes": 10,
        "floor_plan": "1LDK",
        "size_m2": 30.0,
        "floor": None,
        "total_floors": None,
        "building_age_years": None,  # post-1981 confirmed
        "built_year": None,
        "building_type": "マンション",
        "features": ["新耐震基準", "post-1981"],
        "image_url": None,
    },
    {
        "source": "homes",
        "source_url": "https://www.homes.co.jp/chintai/b-1092810076883/",
        "title": "東交ビル",
        "building_name": "東交ビル",
        "rent": 112_000,
        "management_fee": 3_000,
        "deposit": 112_000,   # 1 month (estimated)
        "key_money": 112_000, # 1 month (estimated)
        "address": "東京都杉並区",
        "ward": "suginami",
        "nearest_station": "新高円寺駅",
        "walk_minutes": 3,
        "floor_plan": "1LDK",
        "size_m2": 48.0,
        "floor": None,
        "total_floors": None,
        "building_age_years": None,  # pre-1981 — flag for user
        "built_year": None,
        "building_type": "ビル",
        "features": ["旧耐震基準", "pre-1981 ⚠️"],
        "image_url": None,
    },
    {
        "source": "homes",
        "source_url": "https://www.homes.co.jp/chintai/room/b953dff2d373750fd31689dfcbfcb9bbe78e2d3d/",
        "title": "B・キャッスル十条",
        "building_name": "B・キャッスル十条",
        "rent": 105_000,      # estimated — verify on homes.co.jp
        "management_fee": 4_000,
        "deposit": 105_000,   # 1 month (estimated)
        "key_money": 105_000, # 1 month (estimated)
        "address": "東京都北区",
        "ward": "kita",
        "nearest_station": "東十条駅 / 十条駅",
        "walk_minutes": 7,
        "floor_plan": "1LDK",
        "size_m2": 52.0,
        "floor": None,
        "total_floors": None,
        "building_age_years": 14,   # 14 years old as of 2026 → post-1981 ✓
        "built_year": 2012,
        "building_type": "マンション",
        "features": ["新耐震基準", "post-1981", "dual-station", "rent-unconfirmed"],
        "image_url": None,
    },
]


def seed():
    with Session(engine) as db:
        # Create a seed SearchJob
        job = SearchJob(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            status="completed",
            criteria=SEED_CRITERIA,
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            total_results=len(SEED_LISTINGS),
        )

        existing = db.get(SearchJob, job.id)
        if existing:
            print("Seed data already exists. Skipping.")
            return

        db.add(job)

        for data in SEED_LISTINGS:
            listing = Listing(job_id=job.id, **data)
            db.add(listing)

        db.commit()
        print(f"Seeded {len(SEED_LISTINGS)} listings under job {job.id}")


if __name__ == "__main__":
    seed()
