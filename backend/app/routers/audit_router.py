from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.deps import require_roles
from app.models import AuditLog, User
from app.services.audit import verify_chain

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("")
def list_audit(user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    entries = db.query(AuditLog).order_by(AuditLog.seq.desc()).limit(200).all()
    return [
        {"seq": e.seq, "actor": e.actor, "action": e.action, "entity": e.entity,
         "created_at": e.created_at.isoformat(), "hash": e.hash[:12]}
        for e in entries
    ]


@router.get("/verify")
def verify(user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    return verify_chain(db)
