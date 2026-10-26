"""Verify once, reuse every year: a document whose SHA-256 matches one VERIFIED for the same institution in an earlier year
keeps its verified status (labelled 'carried forward') and is not re-verified."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Document, Verification


def carry_forward(db: Session, app: Application) -> list[int]:
    prev_apps = db.scalars(select(Application).where(Application.institution_id == app.institution_id, Application.academic_year < app.academic_year)
                           .order_by(Application.academic_year.desc())).all()
    done = []
    for doc in db.scalars(select(Document).where(Document.application_id == app.id)):
        for prev in prev_apps:
            old = db.scalars(select(Document).where(Document.application_id == prev.id, Document.sha256 == doc.sha256)).first()
            if not old:
                continue
            ver = db.scalars(select(Verification).where(Verification.document_id == old.id, Verification.status == "VERIFIED")).all()
            if not ver:
                continue
            doc.carried_forward_from = prev.academic_year
            for v in ver:
                db.add(Verification(application_id=app.id, document_id=doc.id, adapter=v.adapter, status="VERIFIED", source=v.source, request_hash=v.request_hash,
                                    response_hash=v.response_hash, response_summary=f"VERIFIED (carried forward from {prev.academic_year}): {v.response_summary or ''}".strip(),
                                    checked_at=datetime.now(timezone.utc).replace(tzinfo=None), carried_forward_from=prev.academic_year))
            done.append(doc.id)
            break
    db.commit()
    return done
