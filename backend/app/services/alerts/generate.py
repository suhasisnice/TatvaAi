"""In-app alerts: created by the pipeline (missing info, suspected anomalies) and by the nightly job (expiring/expired documents,
verifications pending too long). Deduplicated by (application, key) so repeated runs do not spam."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, Application, Document, ExtractedField, Flag, Verification

ISO = "%Y-%m-%d"
EXPIRY_FIELDS = ("valid_till",)


def _add(db: Session, app_id: int, audience: str, kind: str, severity: str, message: str, key: str) -> bool:
    if db.scalar(select(Alert.id).where(Alert.application_id == app_id, Alert.dedupe_key == f"{audience}:{key}")):
        return False
    db.add(Alert(application_id=app_id, audience=audience, kind=kind, severity=severity, message=message, dedupe_key=f"{audience}:{key}",
                 created_at=datetime.now(timezone.utc).replace(tzinfo=None)))
    db.flush()
    return True


def alerts_from_flags(db: Session, app: Application) -> int:
    n = 0
    for f in db.scalars(select(Flag).where(Flag.application_id == app.id, Flag.status != "DISMISSED")):
        if f.code in ("DOC_MISSING", "FIELD_MISSING", "DOC_UNSIGNED"):
            n += _add(db, app.id, "institution", "MISSING_INFO", f.severity, f.message, f"flag:{f.fingerprint}")
        elif f.severity == "CRITICAL" or (f.forensic and f.severity in ("MAJOR", "CRITICAL")):
            n += _add(db, app.id, "officer", "ANOMALY", f.severity, f"Suspected anomaly: {f.message}", f"flag:{f.fingerprint}")
    return n


def generate_scheduled(db: Session, today: date | None = None, expiry_days: int = 60, pending_days: int = 7) -> dict:
    """Nightly job (Celery beat): documents expiring within `expiry_days`, expired documents, verifications pending longer than `pending_days`."""
    today = today or date.today()
    created = {"DOC_EXPIRING": 0, "DOC_EXPIRED": 0, "PENDING_VERIFICATION": 0}
    horizon = (today + timedelta(days=expiry_days)).isoformat()
    for d, v in db.execute(select(Document, ExtractedField.value).join(ExtractedField, ExtractedField.document_id == Document.id)
                           .where(ExtractedField.name.in_(EXPIRY_FIELDS))):
        if len(v or "") != 10 or v[4] != "-":
            continue  # "Perpetual" etc.
        app = db.get(Application, d.application_id)
        if v < today.isoformat():
            kind, msg = "DOC_EXPIRED", f"{d.doc_type} expired on {v}"
        elif v <= horizon:
            kind, msg = "DOC_EXPIRING", f"{d.doc_type} expires on {v} (within {expiry_days} days)"
        else:
            continue
        for aud in ("institution", "officer") if app.status != "DRAFT" else ("institution",):
            created[kind] += _add(db, app.id, aud, kind, "MAJOR" if kind == "DOC_EXPIRED" else "MINOR", msg, f"{kind}:{d.id}")
    cutoff = datetime.combine(today, datetime.min.time()) - timedelta(days=pending_days)
    for v in db.scalars(select(Verification).where(Verification.status.in_(("VERIFICATION_PENDING", "MANUAL_REVIEW_REQUIRED")), Verification.checked_at < cutoff,
                                                   Verification.manual_by.is_(None))):
        created["PENDING_VERIFICATION"] += _add(db, v.application_id, "officer", "PENDING_VERIFICATION", "MINOR",
                                                f"{v.status.replace('_', ' ').title()} for more than {pending_days} days: {v.source}", f"pending:{v.id}")
    db.commit()
    return created
