import csv
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.config import UPLOAD_DIR, ALLOWED_EXTENSIONS, MAX_UPLOAD_MB
from app.deps import get_current_user, require_roles
from app.models import Application, Document, User, Flag, Verification, FacultyRegistryEntry
from app.schemas import ApplicationCreate, FlagDecisionIn, InspectionDecisionIn
from app.services import extraction, pipeline, audit, scoring, alerts, report
from app.services.categories import CATEGORIES, CATEGORY_META

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])


def _scope_institution(app: Application, user: User):
    if user.role == "institution" and app.institution_id != user.institution_id:
        raise HTTPException(status_code=404, detail="Not found")


def _serialize_application(app: Application) -> dict:
    return {
        "id": app.id, "institution_id": app.institution_id, "institution_name": app.institution.name,
        "state": app.institution.state, "aicte_id": app.institution.aicte_id,
        "category": app.category, "category_title": CATEGORY_META.get(app.category, {}).get("title", app.category),
        "academic_year": app.academic_year, "status": app.status,
        "risk_tier": app.risk_tier, "risk_score": app.risk_score, "top_reasons": app.top_reasons or [],
        "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
        "reopen_count": app.reopen_count,
    }


@router.get("/categories")
def list_categories(user: User = Depends(get_current_user)):
    return [{"id": cid, "title": meta["title"], "document_count": len(CATEGORIES[cid])}
            for cid, meta in CATEGORY_META.items()]


@router.get("")
def list_applications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Application)
    if user.role == "institution":
        q = q.filter(Application.institution_id == user.institution_id)
    apps = q.order_by(Application.id.desc()).all()
    return [_serialize_application(a) for a in apps]


@router.post("")
def create_application(body: ApplicationCreate, user: User = Depends(require_roles("institution")),
                        db: Session = Depends(get_db)):
    if body.category not in CATEGORIES:
        raise HTTPException(status_code=400, detail="Unknown application category")
    app_obj = Application(institution_id=user.institution_id, category=body.category,
                           academic_year=body.academic_year, status="DRAFT")
    db.add(app_obj)
    db.commit()
    db.refresh(app_obj)
    audit.record(db, user.email, "application.create", f"application:{app_obj.id}")
    return _serialize_application(app_obj)


@router.get("/{app_id}")
def get_application(app_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    app_obj = db.query(Application).get(app_id)
    if not app_obj:
        raise HTTPException(status_code=404, detail="Not found")
    _scope_institution(app_obj, user)

    docs = db.query(Document).filter(Document.application_id == app_id).all()
    flags = db.query(Flag).filter(Flag.application_id == app_id).order_by(Flag.severity.desc()).all()
    verifications = db.query(Verification).filter(Verification.application_id == app_id).all()

    show_forensics = user.role in ("officer", "inspector")

    return {
        **_serialize_application(app_obj),
        "required_documents": [
            {"doc_type": t, "severity": sev, "citation": cit} for t, sev, cit in CATEGORIES.get(app_obj.category, [])
        ],
        "documents": [
            {"id": d.id, "doc_type": d.doc_type, "file_name": d.file_name,
             "signature_status": d.signature_status, "sha256": d.sha256[:12],
             "classification_confidence": d.classification_confidence,
             "fields": {k: v for k, v in d.extracted_fields.items() if not k.startswith("_")}}
            for d in docs
        ],
        "flags": [
            {"id": f.id, "engine": f.engine, "code": f.code, "severity": f.severity,
             "confidence": f.confidence, "forensic": f.forensic, "message": f.message,
             "explanation": f.explanation, "citation": f.citation, "evidence": f.evidence,
             "status": f.status, "decision_reason": f.decision_reason}
            for f in flags
            if show_forensics or not f.forensic
        ],
        "verifications": [
            {"id": v.id, "document_id": v.document_id, "adapter": v.adapter, "source_name": v.source_name,
             "status": v.status, "summary": v.summary, "manual_note": v.manual_note}
            for v in verifications
        ],
    }


@router.get("/{app_id}/report.pdf")
def report_pdf(app_id: int, user: User = Depends(require_roles("officer", "inspector")), db: Session = Depends(get_db)):
    app_obj = db.query(Application).get(app_id)
    if not app_obj:
        raise HTTPException(status_code=404, detail="Not found")
    docs = db.query(Document).filter(Document.application_id == app_id).all()
    flags = db.query(Flag).filter(Flag.application_id == app_id).all()
    verifs = db.query(Verification).filter(Verification.application_id == app_id).all()
    pdf = report.build_report(app_obj, docs, flags, verifs)
    audit.record(db, user.email, "report.generate", f"application:{app_id}", {"bytes": len(pdf)})
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="validation-report-{app_id}.pdf"'})


@router.post("/{app_id}/documents")
async def upload_document(app_id: int, file: UploadFile = File(...),
                           user: User = Depends(require_roles("institution")),
                           db: Session = Depends(get_db)):
    app_obj = db.query(Application).get(app_id)
    if not app_obj:
        raise HTTPException(status_code=404, detail="Not found")
    _scope_institution(app_obj, user)
    if app_obj.status != "DRAFT":
        raise HTTPException(status_code=409, detail="Application is locked; it cannot accept new uploads")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type {suffix}")

    app_dir = UPLOAD_DIR / str(app_id)
    app_dir.mkdir(parents=True, exist_ok=True)
    dest = app_dir / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    if dest.stat().st_size > MAX_UPLOAD_MB * 1024 * 1024:
        dest.unlink()
        raise HTTPException(status_code=400, detail=f"File exceeds {MAX_UPLOAD_MB} MB")

    text = extraction.extract_text(dest)
    doc_type, confidence = extraction.classify(file.filename, text)
    fields = extraction.extract_fields(text)
    signed, signer = extraction.signature_marker(text)
    fields["_signed"] = signed
    fields["_signer"] = signer
    tampered_match = [ln for ln in text.splitlines() if ln.strip().lower().startswith("tampered-field:")]
    if tampered_match:
        fields["_tampered_field"] = tampered_match[0].split(":", 1)[1].strip()

    if doc_type == "FACULTY_LIST":
        fields["_signed"] = True  # a CSV roster carries no signature line; treated as institution-authored data
        with open(dest, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        ids = [r["faculty_id"] for r in rows if r.get("faculty_id")]
        own_slug = app_obj.institution.slug
        dup_rows = (
            db.query(FacultyRegistryEntry)
            .filter(FacultyRegistryEntry.faculty_id.in_(ids), FacultyRegistryEntry.institution_slug != own_slug)
            .all()
        )
        fields["_duplicate_faculty_ids"] = sorted({r.faculty_id for r in dup_rows})
        fields["_faculty_count"] = len(ids)

    doc = Document(
        application_id=app_id, doc_type=doc_type, file_name=file.filename, storage_path=str(dest),
        sha256=extraction.sha256_file(dest), classification_confidence=confidence,
        signed=signed, extracted_fields=fields,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    audit.record(db, user.email, "document.upload", f"document:{doc.id}", {"doc_type": doc_type})
    return {"id": doc.id, "doc_type": doc_type, "confidence": confidence, "signed": signed}


@router.post("/{app_id}/precheck")
def precheck(app_id: int, user: User = Depends(require_roles("institution")), db: Session = Depends(get_db)):
    app_obj = db.query(Application).get(app_id)
    if not app_obj:
        raise HTTPException(status_code=404, detail="Not found")
    _scope_institution(app_obj, user)
    pipeline.run_pipeline(db, app_obj, actor=user.email)
    flags = db.query(Flag).filter(Flag.application_id == app_id, Flag.forensic == False).all()  # noqa: E712
    buckets = {"CRITICAL": [], "MAJOR": [], "MINOR": []}
    for f in flags:
        if f.severity in buckets:
            buckets[f.severity].append({"message": f.message, "explanation": f.explanation, "citation": f.citation})
    return {"tier": app_obj.risk_tier, "score": app_obj.risk_score, "fix_list": buckets}


@router.post("/{app_id}/submit")
def submit_application(app_id: int, user: User = Depends(require_roles("institution")), db: Session = Depends(get_db)):
    app_obj = db.query(Application).get(app_id)
    if not app_obj:
        raise HTTPException(status_code=404, detail="Not found")
    _scope_institution(app_obj, user)
    if app_obj.status not in ("DRAFT", "REOPENED"):
        raise HTTPException(status_code=409, detail="Application already submitted")
    from datetime import datetime
    pipeline.run_pipeline(db, app_obj, actor=user.email)
    app_obj.status = "SUBMITTED"
    app_obj.submitted_at = datetime.utcnow()
    db.commit()
    alerts.generate_alerts(db, app_obj)
    audit.record(db, user.email, "application.submit", f"application:{app_id}")
    return _serialize_application(app_obj)


@router.post("/{app_id}/reopen")
def reopen_application(app_id: int, user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    app_obj = db.query(Application).get(app_id)
    if not app_obj:
        raise HTTPException(status_code=404, detail="Not found")
    if app_obj.reopen_count >= 1:
        raise HTTPException(status_code=409, detail="This application has already been reopened once")
    app_obj.status = "REOPENED"
    app_obj.reopen_count += 1
    db.commit()
    audit.record(db, user.email, "application.reopen", f"application:{app_id}")
    return _serialize_application(app_obj)


@router.post("/{app_id}/revalidate")
def revalidate(app_id: int, user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    app_obj = db.query(Application).get(app_id)
    if not app_obj:
        raise HTTPException(status_code=404, detail="Not found")
    pipeline.run_pipeline(db, app_obj, actor=user.email)
    return _serialize_application(app_obj)


@router.post("/flags/{flag_id}/decision")
def decide_flag(flag_id: int, body: FlagDecisionIn, user: User = Depends(require_roles("officer")),
                 db: Session = Depends(get_db)):
    if body.decision not in ("ACCEPT", "DISMISS"):
        raise HTTPException(status_code=400, detail="decision must be ACCEPT or DISMISS")
    if len(body.reason.strip()) < 5:
        raise HTTPException(status_code=400, detail="Reason must be at least 5 characters")
    flag = db.query(Flag).get(flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Not found")
    app_obj = db.query(Application).get(flag.application_id)
    before = app_obj.risk_score

    flag.status = "ACCEPTED" if body.decision == "ACCEPT" else "DISMISSED"
    flag.decision_reason = body.reason
    db.commit()

    scoring_flags = [
        dict(severity=f.severity, confidence=f.confidence, forensic=f.forensic, status=f.status, message=f.message)
        for f in db.query(Flag).filter(Flag.application_id == app_obj.id).all()
    ]
    score, tier, top_reasons = scoring.score_flags(scoring_flags)
    app_obj.risk_score, app_obj.risk_tier, app_obj.top_reasons = score, tier, top_reasons
    db.commit()

    audit.record(db, user.email, f"flag.{body.decision.lower()}", f"flag:{flag_id}",
                 {"reason": body.reason, "score_before": before, "score_after": score})
    return {"flag_id": flag_id, "status": flag.status, "score_before": before, "score_after": score, "tier": tier}


@router.post("/flags/{flag_id}/inspection")
def inspect_flag(flag_id: int, body: InspectionDecisionIn, user: User = Depends(require_roles("inspector")),
                  db: Session = Depends(get_db)):
    """The EVC's own on-site verdict on a flagged item -- separate from the
    officer's accept/dismiss, which only screens findings before a visit."""
    if body.status not in ("CONFIRMED", "CLEARED"):
        raise HTTPException(status_code=400, detail="status must be CONFIRMED or CLEARED")
    if len(body.note.strip()) < 5:
        raise HTTPException(status_code=400, detail="Note must be at least 5 characters")
    flag = db.query(Flag).get(flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Not found")
    from datetime import datetime
    flag.inspection_status = body.status
    flag.inspection_note = body.note
    flag.inspection_by = user.name
    flag.inspected_at = datetime.utcnow()
    db.commit()
    audit.record(db, user.email, f"inspection.{body.status.lower()}", f"flag:{flag_id}", {"note": body.note})
    return {"flag_id": flag_id, "inspection_status": flag.inspection_status}


@router.post("/verifications/{verification_id}/manual")
def manual_verification(verification_id: int, note: str, user: User = Depends(require_roles("officer")),
                         db: Session = Depends(get_db)):
    if len(note.strip()) < 5:
        raise HTTPException(status_code=400, detail="Note must be at least 5 characters")
    v = db.query(Verification).get(verification_id)
    if not v:
        raise HTTPException(status_code=404, detail="Not found")
    v.status = "VERIFIED"
    v.manual_note = note
    v.manual_by = user.email
    v.summary = f"Manually confirmed by {user.name}: {note}"
    db.commit()
    audit.record(db, user.email, "verification.manual", f"verification:{verification_id}", {"note": note})
    return {"id": v.id, "status": v.status}
