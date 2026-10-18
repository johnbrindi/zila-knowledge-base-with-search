from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery = Celery(
    "ingest",
    broker=settings.redis_url,
    include=["app.worker.tasks", "app.worker.digest_tasks"],
)
celery.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    timezone=settings.digest_timezone,
    enable_utc=True,
    # Digest jobs go to their own queue so they can never starve document ingestion.
    task_routes={"digest.*": {"queue": "digest"}},
    beat_schedule={
        "weekly-opportunity-digest": {
            "task": "digest.run_weekly",
            "schedule": crontab(day_of_week=settings.digest_cron_day,
                                hour=settings.digest_cron_hour, minute=0),
        },
    },
)
