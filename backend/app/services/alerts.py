"""Alert generation. Idempotent: an alert is created once per
(application, audience, kind, message), so re-running validation never repeats it.

There is no background worker in this build, so the expiry-window check
(valid-till within 60 days) runs with the pipeline instead of a nightly job.
"""
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Alert, Application, Document, Flag

EXPIRY_WINDOW_DAYS = 60
MISSING_CODES = {"DOC_MISSING", "FIELD_MISSING", "DOC_UNSIGNED"}
EXPIRY_CODES = {"DOC_EXPIRES_BEFORE_AY": "DOC_EXPIRING", "DOC_EXPIRED": "DOC_EXPIRED"}


def _add(db: Session, application_id: int, audience: str, kind: str, message: str):
    exists = db.query(Alert).filter(
        Alert.application_id == application_id, Alert.audience == audience,
        Alert.kind == kind, Alert.message == message,
    ).first()
    if not exists:
        db.add(Alert(application_id=application_id, audience=audience, kind=kind, message=message))


def generate_alerts(db: Session, application: Application) -> None:
    submitted = application.status != "DRAFT"
    flags = db.query(Flag).filter(Flag.application_id == application.id, Flag.status != "DISMISSED").all()

    for f in flags:
        if f.code in MISSING_CODES:
            _add(db, application.id, "institution", "MISSING_INFO", f.message)
        if f.code in EXPIRY_CODES:
            kind = EXPIRY_CODES[f.code]
            _add(db, application.id, "institution", kind, f.message)
            if submitted:
                _add(db, application.id, "officer", kind, f"{application.institution.name}: {f.message}")
        if submitted and (f.severity == "CRITICAL" or (f.forensic and f.severity == "MAJOR")):
            _add(db, application.id, "officer", "ANOMALY",
                 f"Suspected anomaly at {application.institution.name}: {f.message}")

    horizon = date.today() + timedelta(days=EXPIRY_WINDOW_DAYS)
    for d in db.query(Document).filter(Document.application_id == application.id).all():
        raw = (d.extracted_fields or {}).get("valid_till")
        try:
            valid_till = datetime.strptime(raw, "%Y-%m-%d").date() if raw else None
        except ValueError:
            valid_till = None
        if valid_till and date.today() <= valid_till <= horizon:
            msg = f"{d.doc_type.replace('_', ' ').title()} expires on {valid_till} (within {EXPIRY_WINDOW_DAYS} days)"
            _add(db, application.id, "institution", "DOC_EXPIRING", msg)
            if submitted:
                _add(db, application.id, "officer", "DOC_EXPIRING", f"{application.institution.name}: {msg}")

    db.commit()
