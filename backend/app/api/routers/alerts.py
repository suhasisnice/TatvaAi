from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user
from app.models import Alert, AlertRead, Application, User

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _visible(db: Session, user: User):
    q = select(Alert).order_by(Alert.id.desc())
    if user.role == "institution":
        mine = select(Application.id).where(Application.institution_id == user.institution_id)
        return q.where(Alert.audience == "institution", Alert.application_id.in_(mine))
    return q.where(Alert.audience == "officer")


@router.get("")
def list_alerts(unread_only: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    read = {r.alert_id for r in db.scalars(select(AlertRead).where(AlertRead.user_id == user.id))}
    rows = [dict(id=a.id, application_id=a.application_id, kind=a.kind, severity=a.severity, message=a.message, created_at=a.created_at.isoformat(), read=a.id in read)
            for a in db.scalars(_visible(db, user).limit(200))]
    return dict(unread_count=sum(not r["read"] for r in rows), alerts=[r for r in rows if not (unread_only and r["read"])])


@router.post("/{alert_id}/read")
def mark_read(alert_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ids = {a.id for a in db.scalars(_visible(db, user))}
    if alert_id not in ids:
        raise HTTPException(404, "Alert not found")
    if not db.scalar(select(AlertRead.id).where(AlertRead.alert_id == alert_id, AlertRead.user_id == user.id)):
        db.add(AlertRead(alert_id=alert_id, user_id=user.id))
        db.commit()
    return {"read": True}
