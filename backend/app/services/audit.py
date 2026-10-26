import hashlib
import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import AuditLog


def record(db: Session, actor: str, action: str, entity: str = "", payload: dict | None = None) -> AuditLog:
    payload = payload or {}
    last = db.query(AuditLog).order_by(AuditLog.seq.desc()).first()
    prev_hash = last.hash if last else "GENESIS"
    seq = (last.seq + 1) if last else 1
    payload_json = json.dumps(payload, sort_keys=True, default=str)
    now = datetime.utcnow()
    ts = now.isoformat()
    digest = hashlib.sha256(f"{prev_hash}{payload_json}{ts}{actor}{action}".encode()).hexdigest()
    entry = AuditLog(seq=seq, actor=actor, action=action, entity=entity, payload=payload,
                      prev_hash=prev_hash, hash=digest, created_at=now)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def verify_chain(db: Session) -> dict:
    entries = db.query(AuditLog).order_by(AuditLog.seq.asc()).all()
    prev_hash = "GENESIS"
    for e in entries:
        payload_json = json.dumps(e.payload, sort_keys=True, default=str)
        ts = e.created_at.isoformat()
        expected = hashlib.sha256(f"{prev_hash}{payload_json}{ts}{e.actor}{e.action}".encode()).hexdigest()
        if e.prev_hash != prev_hash or e.hash != expected:
            return {"intact": False, "broken_at": e.seq, "entries": len(entries)}
        prev_hash = e.hash
    return {"intact": True, "broken_at": None, "entries": len(entries)}
