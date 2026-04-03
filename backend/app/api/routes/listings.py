"""Listings API — browse/filter persisted listings."""
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import Listing
from app.models.listing import ListingOut

router = APIRouter()


@router.get("/", response_model=list[ListingOut])
async def list_listings(
    job_id: uuid.UUID | None = Query(None),
    source: str | None = Query(None),
    min_rent: int | None = Query(None),
    max_rent: int | None = Query(None),
    floor_plan: str | None = Query(None),
    ward: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """Browse listings with optional filters."""
    q = select(Listing)

    if job_id:
        q = q.where(Listing.job_id == job_id)
    if source:
        q = q.where(Listing.source == source)
    if min_rent:
        q = q.where(Listing.rent >= min_rent)
    if max_rent:
        q = q.where(Listing.rent <= max_rent)
    if floor_plan:
        q = q.where(Listing.floor_plan == floor_plan)
    if ward:
        q = q.where(Listing.ward.ilike(f"%{ward}%"))

    q = q.order_by(Listing.rent.asc().nullslast()).limit(limit).offset(offset)

    result = await db.execute(q)
    return result.scalars().all()
