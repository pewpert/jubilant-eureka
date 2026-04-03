"""Search API routes."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import SearchJob, Listing
from app.models.search import SearchCriteria
from app.models.listing import SearchJobOut, SearchJobWithListings
from app.tasks.scrape import scrape_apartments

router = APIRouter()


@router.post("/", response_model=SearchJobOut, status_code=202)
async def create_search(
    criteria: SearchCriteria,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a new apartment search.
    Returns a job ID immediately. Poll /api/search/{id}/status for progress.
    The actual scraping happens asynchronously in a Celery worker.
    """
    job = SearchJob(criteria=criteria.model_dump(mode="json"))
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Enqueue the Celery task (non-blocking)
    scrape_apartments.delay(str(job.id), criteria.model_dump(mode="json"))

    return job


@router.get("/{job_id}/status", response_model=SearchJobOut)
async def get_job_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Check the status of a search job."""
    job = await db.get(SearchJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/results", response_model=SearchJobWithListings)
async def get_job_results(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve search results once the job is completed.
    Returns all listings associated with this search.
    """
    job = await db.get(SearchJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in ("completed", "failed"):
        raise HTTPException(status_code=202, detail=f"Job is {job.status}")

    result = await db.execute(
        select(Listing)
        .where(Listing.job_id == job_id)
        .order_by(Listing.rent.asc().nullslast())
    )
    listings = result.scalars().all()

    return SearchJobWithListings(
        **SearchJobOut.model_validate(job).model_dump(),
        listings=listings,
    )
