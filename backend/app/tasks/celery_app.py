"""Celery application factory."""
from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "tokyo_apartments",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.scrape"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Tokyo",
    enable_utc=True,
    # Results expire after 24h
    result_expires=86400,
    # Limit concurrency at the task level as well
    worker_max_tasks_per_child=50,
)
