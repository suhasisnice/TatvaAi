from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.deps import get_current_user
from app.models import Alert, Application, User

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def _visible(db: Session, user: User):
    q = db.query(Alert)
    if user.role == "institution":
        q = q.join(Application, Alert.application_id == Application.id).filter(
            Alert.audience == "institution", Application.institution_id == user.institution_id)
    elif user.role == "officer":
        q = q.filter(Alert.audience == "officer")
    else:
        q = q.filter(Alert.id == -1)
    return q


@router.get("")
def list_alerts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    alerts = _visible(db, user).order_by(Alert.id.desc()).limit(50).all()
    return {
        "unread": sum(1 for a in alerts if not a.read),
        "alerts": [
            {"id": a.id, "application_id": a.application_id, "kind": a.kind, "message": a.message,
             "read": a.read, "created_at": a.created_at.isoformat()}
            for a in alerts
        ],
    }


@router.post("/{alert_id}/read")
def mark_read(alert_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    alert = _visible(db, user).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Not found")
    alert.read = True
    db.commit()
    return {"id": alert.id, "read": True}
