from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, require_roles
from app.models import Application, User, Verification
from datetime import datetime, timezone

from pydantic import BaseModel, field_validator

from app.services.audit import hash_chain as audit
from app.services.pipeline import run_pipeline

router = APIRouter(tags=["verification"])


def _app(db: Session, user: User, app_id: int) -> Application:
    a = db.get(Application, app_id)
    if not a or (user.role == "institution" and a.institution_id != user.institution_id):
        raise HTTPException(404, "Application not found")
    return a


@router.post("/applications/{app_id}/verify")
def verify(app_id: int, user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    """Runs the full pipeline: issuer verification, authenticity, completeness, consistency, compliance."""
    return run_pipeline(db, _app(db, user, app_id), user)


@router.get("/applications/{app_id}/verifications")
def list_verifications(app_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _app(db, user, app_id)
    return [dict(id=v.id, document_id=v.document_id, adapter=v.adapter, status=v.status, source=v.source, mock=True, response_summary=v.response_summary,
                 checked_at=v.checked_at.isoformat(), carried_forward_from=v.carried_forward_from, manual_note=v.manual_note)
            for v in db.scalars(select(Verification).where(Verification.application_id == app_id).order_by(Verification.id))]


class ManualIn(BaseModel):
    note: str

    @field_validator("note")
    @classmethod
    def _n(cls, v):
        if len(v.strip()) < 5:
            raise ValueError("a note of at least 5 characters is required")
        return v.strip()


@router.post("/verifications/{ver_id}/manual")
def manual_confirmation(ver_id: int, body: ManualIn, user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    """The officer confirms by hand (phone, letter, site visit) a check the automatic source could not answer."""
    v = db.get(Verification, ver_id)
    if not v:
        raise HTTPException(404, "Verification not found")
    _app(db, user, v.application_id)
    if v.status != "MANUAL_REVIEW_REQUIRED":
        raise HTTPException(409, "Only verifications waiting for manual review can be confirmed manually")
    v.status, v.manual_note, v.manual_by = "VERIFIED", body.note, user.id
    v.response_summary = f"Manually confirmed by officer: {body.note}"
    v.checked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    audit.log(db, user, "verification.manual", f"verification:{v.id}", {"application_id": v.application_id, "adapter": v.adapter, "source": v.source, "note": body.note})
    db.commit()
    return dict(id=v.id, status=v.status, manual_note=v.manual_note)
