"""Append-only hash-chained audit log. Tampering with any row (or deleting one) breaks verification at that entry."""
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.workflow import AuditLog

GENESIS = "0" * 64


def canonical(payload) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def entry_hash(prev_hash: str, payload_hash: str, ts: str, actor: str, action: str) -> str:
    return sha(prev_hash + payload_hash + ts + actor + action)


def actor_of(user) -> str:
    return "system" if user is None else f"user:{user.id}:{user.role}" if hasattr(user, "role") else str(user)


def log(db: Session, user, action: str, entity: str, payload: dict | None = None) -> AuditLog:
    """Adds one chained entry to the session (caller commits). ponytail: single writer; use an advisory lock if concurrent writers matter."""
    last = db.scalars(select(AuditLog).order_by(desc(AuditLog.seq)).limit(1)).first()
    prev = last.hash if last else GENESIS
    body, ts, actor = canonical(payload or {}), datetime.now(timezone.utc).isoformat(timespec="microseconds"), actor_of(user)
    ph = sha(body)
    row = AuditLog(ts=ts, actor=actor, action=action, entity=entity, payload_json=body, payload_hash=ph, prev_hash=prev, hash=entry_hash(prev, ph, ts, actor, action))
    db.add(row)
    db.flush()
    return row


def verify(db: Session) -> dict:
    """Walk the chain. Reports the first broken entry (seq) and why."""
    prev, n = GENESIS, 0
    for row in db.scalars(select(AuditLog).order_by(AuditLog.seq)):
        n += 1
        problem = None
        if row.prev_hash != prev:
            problem = "previous hash does not match (an earlier entry was removed or altered)"
        elif sha(row.payload_json) != row.payload_hash:
            problem = "payload does not match its recorded hash"
        elif entry_hash(row.prev_hash, row.payload_hash, row.ts, row.actor, row.action) != row.hash:
            problem = "entry hash does not match its contents"
        if problem:
            return dict(intact=False, entries=n, broken_at=row.seq, reason=problem)
        prev = row.hash
    return dict(intact=True, entries=n, broken_at=None, reason=None, head=prev)
