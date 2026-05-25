"""
Celery scraping tasks.

Why async + Celery?
  Scraping can take 30-120 seconds per source (Playwright browser startup +
  page renders + rate-limit delays). Running this synchronously in the HTTP
  request would time out and give a terrible UX.

  Instead:
    1. POST /api/search  → creates a SearchJob row, enqueues Celery task,
                           returns job_id immediately (< 100ms)
    2. GET /api/search/{id}/status  → frontend polls this (or we use SSE)
    3. Celery worker runs the scrapers async internally, writes results to DB
    4. When done, job.status = "completed"

  Celery workers run a synchronous task that internally runs an asyncio
  event loop (asyncio.run) — this is the standard pattern for mixing
  Celery (sync) with async scraping code.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.tasks.celery_app import celery_app
from app.db.models import SearchJob, Listing
from app.models.search import SearchCriteria
from app.scrapers.manager import run_all_scrapers

logger = logging.getLogger(__name__)
settings = get_settings()

# Celery workers use a synchronous SQLAlchemy engine (not async)
# because Celery tasks run in their own thread/process.
_sync_db_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace(
    "postgresql+asyncpg", "postgresql"
)
sync_engine = create_engine(_sync_db_url, pool_pre_ping=True)


@celery_app.task(bind=True, name="scrape_apartments", max_retries=2)
def scrape_apartments(self, job_id: str, criteria_dict: dict) -> dict:
    """
    Main scraping task.
    Called by the API after creating a SearchJob row.
    """
    logger.info("Starting scrape task for job %s", job_id)

    with Session(sync_engine) as db:
        job = db.get(SearchJob, uuid.UUID(job_id))
        if not job:
            logger.error("Job %s not found in DB", job_id)
            return {"error": "job not found"}

        job.status = "running"
        db.commit()

    try:
        criteria = SearchCriteria(**criteria_dict)

        def update_progress(msg: str) -> None:
            with Session(sync_engine) as _db:
                _job = _db.get(SearchJob, uuid.UUID(job_id))
                if _job:
                    _job.progress = msg
                    _db.commit()

        raw_listings, scrape_stats = asyncio.run(_scrape(criteria, update_progress))

        # Only spread keys that are actual Listing columns — scraper dicts may
        # carry transient keys (e.g. _excluded_reason) that would crash the insert.
        listing_columns = {c.name for c in Listing.__table__.columns}

        with Session(sync_engine) as db:
            job = db.get(SearchJob, uuid.UUID(job_id))

            for raw in raw_listings:
                listing = Listing(
                    job_id=job.id,
                    **{k: v for k, v in raw.items() if k in listing_columns and k != "source"},
                    source=raw.get("source", "unknown"),
                )
                db.add(listing)

            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.total_results = len(raw_listings)
            job.scrape_stats = scrape_stats
            db.commit()

        logger.info("Job %s completed — %d listings", job_id, len(raw_listings))
        return {"job_id": job_id, "total": len(raw_listings)}

    except Exception as exc:
        logger.exception("Scrape task failed for job %s", job_id)

        with Session(sync_engine) as db:
            job = db.get(SearchJob, uuid.UUID(job_id))
            if job:
                job.status = "failed"
                job.error = str(exc)
                db.commit()

        raise self.retry(exc=exc, countdown=10)


async def _scrape(criteria: SearchCriteria, progress_cb=None) -> tuple[list[dict], dict]:
    return await run_all_scrapers(criteria, progress_cb=progress_cb)
