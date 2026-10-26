import csv
import io
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_app
from app.core.db import get_db
from app.core.security import require_roles
from app.models import AuditLog, Document, User
from app.services.audit import hash_chain

router = APIRouter(prefix="/audit", tags=["audit"])


def _row(r: AuditLog) -> dict:
    return dict(seq=r.seq, ts=r.ts, actor=r.actor, action=r.action, entity=r.entity, payload=json.loads(r.payload_json), payload_hash=r.payload_hash, prev_hash=r.prev_hash, hash=r.hash)


def _query(db: Session, application_id: int | None, action: str | None):
    q = select(AuditLog).order_by(desc(AuditLog.seq))
    if application_id:
        docs = [f"document:{d}" for d in db.scalars(select(Document.id).where(Document.application_id == application_id))]
        q = q.where(or_(AuditLog.entity == f"application:{application_id}", AuditLog.entity.in_(docs), AuditLog.payload_json.contains(f'"application_id":{application_id},'),
                            AuditLog.payload_json.contains(f'"application_id":{application_id}' + '}')))
    if action:
        q = q.where(AuditLog.action.startswith(action))
    return q


@router.get("")
def list_audit(application_id: int | None = None, action: str | None = None, limit: int = Query(100, le=1000), offset: int = 0,
               user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    if application_id:
        get_app(db, user, application_id)
    return [_row(r) for r in db.scalars(_query(db, application_id, action).limit(limit).offset(offset))]


@router.get("/verify")
def verify_chain(user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    return hash_chain.verify(db)


@router.get("/export")
def export(format: str = "csv", user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    rows = [_row(r) for r in db.scalars(select(AuditLog).order_by(AuditLog.seq))]
    if format == "json":
        return Response(json.dumps(rows, indent=1), media_type="application/json", headers={"Content-Disposition": "attachment; filename=audit.json"})
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["seq", "ts", "actor", "action", "entity", "payload", "payload_hash", "prev_hash", "hash"])
    for r in rows:
        w.writerow([r["seq"], r["ts"], r["actor"], r["action"], r["entity"], json.dumps(r["payload"], sort_keys=True), r["payload_hash"], r["prev_hash"], r["hash"]])
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=audit.csv"})
