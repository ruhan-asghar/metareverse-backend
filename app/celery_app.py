from celery import Celery
from kombu import Queue
from app.core.config import get_settings
from app.core.sentry import init_sentry_worker

settings = get_settings()

celery_app = Celery("metareverse", broker=settings.celery_broker, backend=settings.celery_backend)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_max_tasks_per_child=1000,
    task_default_queue="default",
    task_queues=(
        Queue("publish"),
        Queue("insights"),
        Queue("email"),
        Queue("health"),
        Queue("default"),
    ),
    task_routes={
        "app.tasks.publishing.*": {"queue": "publish"},
        "app.tasks.insights.*": {"queue": "insights"},
        "app.tasks.email.*": {"queue": "email"},
        "app.tasks.health.*": {"queue": "health"},
    },
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=120,
    task_soft_time_limit=90,
    redbeat_redis_url=settings.redis_url,
    redbeat_lock_timeout=60,
)

celery_app.autodiscover_tasks(["app.tasks"])

from app.tasks.beat_schedule import BEAT_SCHEDULE
celery_app.conf.beat_schedule = BEAT_SCHEDULE


@celery_app.on_after_configure.connect
def setup_worker_sentry(sender, **kwargs):
    init_sentry_worker()
