"""Search API routes."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import SearchJob, Listing
from app.models.search import SearchCriteria
from app.models.listing import SearchJobOut, SearchJobWithListings, DebugResponse, SourceDebugStats, ExclusionBreakdown
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


@router.get("/{job_id}/debug", response_model=DebugResponse)
async def get_job_debug(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Per-source scrape diagnostics. Available once job is completed or failed.
    Shows raw_count vs passed_count and which filters excluded listings.
    Useful for diagnosing zero results.
    """
    job = await db.get(SearchJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    stats_raw: dict = job.scrape_stats or {}
    per_source_raw: dict = stats_raw.get("per_source", {})

    per_source: dict[str, SourceDebugStats] = {}
    for source, data in per_source_raw.items():
        excl = data.get("excluded_by", {})
        per_source[source] = SourceDebugStats(
            url_used=data.get("url_used"),
            raw_count=data.get("raw_count", 0),
            passed_count=data.get("passed_count", 0),
            excluded_by=ExclusionBreakdown(**{
                k: excl.get(k, 0) for k in ExclusionBreakdown.model_fields
            }),
            error=data.get("error"),
            blocked=data.get("blocked", False),
            sample_excluded=data.get("sample_excluded", []),
            sample_near_miss=data.get("sample_near_miss", []),
        )

    return DebugResponse(
        job_id=str(job_id),
        status=job.status,
        criteria=job.criteria,
        per_source=per_source,
        total_raw=stats_raw.get("total_raw", 0),
        total_passed=stats_raw.get("total_passed", 0),
        dominant_filter=stats_raw.get("dominant_filter"),
    )
