from pathlib import Path

import imagehash
from PIL import Image
from sqlalchemy.orm import Session

from app.models import Application, Document, Flag, Verification, IssuerRecord
from app.services import engines, scoring, audit, alerts


def _phash(path: Path) -> imagehash.ImageHash | None:
    try:
        with Image.open(path) as im:
            return imagehash.phash(im)
    except Exception:
        return None


def _find_duplicate_photo(db: Session, doc: Document) -> dict | None:
    if doc.doc_type != "INFRA_PHOTO":
        return None
    path = Path(doc.storage_path)
    h1 = _phash(path)
    if h1 is None:
        return None
    others = (
        db.query(Document, Application)
        .join(Application, Document.application_id == Application.id)
        .filter(Document.doc_type == "INFRA_PHOTO", Document.id != doc.id)
        .all()
    )
    best = None
    for other_doc, other_app in others:
        h2 = _phash(Path(other_doc.storage_path))
        if h2 is None:
            continue
        distance = h1 - h2
        if distance <= 10 and (best is None or distance < best["distance"]):
            best = dict(distance=distance, other_institution=other_app.institution.name,
                        other_app_id=other_app.id)
    if best:
        return dict(is_duplicate=True, distance=best["distance"], confidence=round(1 - best["distance"] / 64, 2),
                     other_institution=best["other_institution"], document_id=doc.id)
    return None


def run_pipeline(db: Session, application: Application, actor: str = "system") -> Application:
    documents = db.query(Document).filter(Document.application_id == application.id).all()
    institution = application.institution

    issuer_records = {
        r.doc_type: r for r in db.query(IssuerRecord).filter(
            IssuerRecord.institution_slug == institution.slug
        ).all()
    }

    all_flags: list[dict] = []
    all_flags += engines.completeness_engine(application, documents)

    issuer_flags, verification_rows = engines.issuer_and_authenticity_engine(documents, issuer_records)
    all_flags += issuer_flags

    all_flags += engines.consistency_engine(application, documents, institution)

    duplicate_info = None
    photo_doc = next((d for d in documents if d.doc_type == "INFRA_PHOTO"), None)
    if photo_doc:
        duplicate_info = _find_duplicate_photo(db, photo_doc)

    all_flags += engines.compliance_engine(application, documents, institution, duplicate_info)

    footprint_estimate = (institution.declared_built_up_m2 or 0) and getattr(institution, "footprint_estimate_m2", None)
    if footprint_estimate:
        bf = engines.built_up_area_flag(institution, footprint_estimate)
        if bf:
            all_flags.append(bf)

    # --- upsert flags by fingerprint, preserving officer decisions ---
    existing = {f.fingerprint: f for f in db.query(Flag).filter(Flag.application_id == application.id).all()}
    seen_fps = set()
    for fd in all_flags:
        fp = fd["fingerprint"]
        seen_fps.add(fp)
        if fp in existing:
            row = existing[fp]
            row.message = fd["message"]
            row.explanation = fd["explanation"]
            row.confidence = fd["confidence"]
        else:
            row = Flag(application_id=application.id, status="OPEN", decision_reason=None, **fd)
            db.add(row)
    for fp, row in existing.items():
        if fp not in seen_fps:
            db.delete(row)

    # --- replace verification rows (mocked, so simply refresh) ---
    db.query(Verification).filter(Verification.application_id == application.id).delete()
    for v in verification_rows:
        db.add(Verification(application_id=application.id, **v))

    db.commit()

    scoring_flags = [
        dict(severity=f.severity, confidence=f.confidence, forensic=f.forensic, status=f.status, message=f.message)
        for f in db.query(Flag).filter(Flag.application_id == application.id).all()
    ]
    score, tier, top_reasons = scoring.score_flags(scoring_flags)
    application.risk_score = score
    application.risk_tier = tier
    application.top_reasons = top_reasons
    db.commit()
    db.refresh(application)
    alerts.generate_alerts(db, application)

    audit.record(db, actor, "pipeline.run", f"application:{application.id}",
                 {"score": score, "tier": tier, "flag_count": len(scoring_flags)})
    return application
