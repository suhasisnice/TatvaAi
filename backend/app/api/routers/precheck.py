import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_app
from app.core.config import settings
from app.core.db import get_db
from app.core.security import current_user, require_roles
from app.models import Job, User
from app.services.precheck import create_job, execute_job

router = APIRouter(tags=["precheck"])


def _job_out(j: Job) -> dict:
    r = json.loads(j.result_json) if j.result_json else {}
    return dict(job_id=j.id, application_id=j.application_id, status=j.status, error=r.get("error"), fix_list=r.get("fix_list"),
                created_at=j.created_at.isoformat(), finished_at=j.finished_at.isoformat() if j.finished_at else None)


@router.post("/applications/{app_id}/precheck", status_code=202)
def start_precheck(app_id: int, user: User = Depends(require_roles("institution")), db: Session = Depends(get_db)):
    a = get_app(db, user, app_id)
    if a.locked:
        raise HTTPException(409, "Application is submitted and locked")
    job = create_job(db, a)
    if settings.use_celery:
        from app.workers.tasks import precheck_task

        precheck_task.delay(job.id)
    else:
        execute_job(db, job.id, user)
        db.refresh(job)
    return dict(job_id=job.id, status=job.status)


@router.get("/precheck/jobs/{job_id}")
def get_job(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    get_app(db, user, j.application_id)
    return _job_out(j)
