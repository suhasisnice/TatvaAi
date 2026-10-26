from datetime import date

from app.core.db import SessionLocal
from app.services.alerts.generate import generate_scheduled
from app.services.precheck import execute_job
from app.workers.celery_app import celery


@celery.task(name="precheck")
def precheck_task(job_id: str):
    with SessionLocal() as db:
        execute_job(db, job_id)


@celery.task(name="nightly_alerts")
def nightly_alerts():
    with SessionLocal() as db:
        return generate_scheduled(db, date.today())

