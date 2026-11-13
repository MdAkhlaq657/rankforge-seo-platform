from celery import Celery
from app.config import settings

celery_app = Celery(
    "seo_platform",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.crawl_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Retry broker connection on worker startup and transient publish failures.
    broker_connection_retry_on_startup=True,
    task_publish_retry=True,
    task_publish_retry_policy={
        "max_retries": 5,
        "interval_start": 0,
        "interval_step": 0.5,
        "interval_max": 2,
    },
    task_default_queue="default",
    task_routes={
        "app.workers.crawl_tasks.run_crawl": {"queue": "crawls"},
        "app.workers.crawl_tasks.run_audit": {"queue": "audits"},
    },
    beat_schedule={
        # Future: scheduled crawls will go here
    },
)
