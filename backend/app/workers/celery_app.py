from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery = Celery("tatva", broker=settings.redis_url, backend=settings.redis_url)
celery.conf.imports = ("app.workers.tasks",)
celery.conf.beat_schedule = {"nightly-alerts": {"task": "nightly_alerts", "schedule": crontab(hour=2, minute=0)}}


@celery.task
def ping():
    return "pong"
