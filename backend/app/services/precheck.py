"""Institution pre-check: the same pipeline in plain language. Forensic/officer-only indicators are not shown to institutions;
INFO items are summarised as 'waiting for officer confirmation'."""
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Flag, Job
from app.services.audit import hash_chain as audit
from app.services.pipeline import run_pipeline

HOWTO = {
    "DOC_MISSING": "Upload the missing document (PDF, digitally signed).",
    "DOC_UNSIGNED": "Upload the document again after signing it with a valid Digital Signature Certificate (DSC).",
    "FIELD_MISSING": "Re-issue or re-upload the document so the required field is clearly printed.",
    "DOC_EXPIRED": "Obtain a renewed certificate from the issuing authority and upload it.",
    "DOC_EXPIRES_BEFORE_AY": "Obtain a certificate that is valid on the first day of the academic year and upload it.",
    "PROVISIONAL_OC_LIMIT_EXCEEDED": "A provisional occupancy certificate is accepted for only 2 consecutive academic years. Obtain the full occupancy/completion certificate.",
    "MISMATCH_CROSS_DOC": "Correct the application form or re-upload the document so the name/number agrees everywhere.",
    "MISMATCH_CROSS_YEAR": "Explain the change from last year in a covering note, or correct the entry if it is a mistake.",
    "TIMELINE_IMPOSSIBLE": "Check the dates: re-issue the affidavit or stamp paper in the correct order.",
    "DUPLICATE_FACULTY_CROSS_INSTITUTION": "Remove faculty who are full-time at another institution, or provide a relieving order.",
    "DISCLOSURE_MISMATCH": "Update the mandatory disclosure on your website so it matches the application.",
    "NORM_FACULTY_SHORTFALL": "Recruit or add the missing full-time faculty, or reduce the sanctioned intake.",
    "NORM_CADRE_RATIO": "Rebalance the faculty cadre to 1 Professor : 2 Associate Professors : 6 Assistant Professors.",
    "NORM_ROOMS": "Add the missing rooms or laboratories, or correct the declared numbers and sizes.",
    "NORM_AREA": "Add the required area or correct the declared area of the facility.",
    "NORM_PC_RATIO": "Add the missing computers/printers, or correct the declared numbers.",
    "NORM_BANDWIDTH": "Increase internet bandwidth to the required level.",
    "BUILTUP_AREA_IMPLAUSIBLE": "Check the declared built-up area against your building plans and correct the application.",
    "BUILDING_NOT_VISIBLE_ON_DATE": "Provide a completion certificate with the correct date for this building.",
    "PHOTO_GPS_OFFSITE": "Upload photos taken at the campus (with location enabled).",
    "ACCREDITATION_CLAIM_UNVERIFIED": "Remove the accreditation claim or provide the accreditation certificate.",
    "DUPLICATE_DOCUMENT_CROSS_INSTITUTION": "Upload your own institution's document.",
    "DUPLICATE_PHOTO": "Upload your own photographs of the facility.",
    "ISSUER_MISMATCH": "The issuing authority's record differs from your document. Contact the issuing authority and upload the corrected certificate.",
    "ISSUER_EXPIRED": "The issuing authority shows this certificate as expired. Obtain a renewed certificate.",
    "ISSUER_UNAVAILABLE": "No action needed: an officer will confirm this with the issuing authority.",
}
SEV_ORDER = ["CRITICAL", "MAJOR", "MINOR"]


def fix_list(db: Session, app: Application) -> dict:
    items, waiting = [], 0
    for f in db.scalars(select(Flag).where(Flag.application_id == app.id).order_by(Flag.id)):
        if f.forensic or f.engine == "authenticity":
            continue
        if f.severity == "INFO":
            waiting += 1
            continue
        c = json.loads(f.citation) if f.citation else None
        items.append(dict(flag_id=f.id, severity=f.severity, code=f.code, message=f.message, how_to_fix=HOWTO.get(f.code, "Review and correct the highlighted item."),
                          citation=f"{c['source']}, {c['clause']}, p. {c['page']}" if c else None, document_id=f.document_id))
    groups = [dict(severity=s, items=[i for i in items if i["severity"] == s]) for s in SEV_ORDER]
    return dict(groups=[g for g in groups if g["items"]], total=len(items), waiting_for_officer=waiting,
                ready_to_submit=not any(i["severity"] in ("CRITICAL", "MAJOR") for i in items))


def execute_job(db: Session, job_id: str, actor=None) -> None:
    job = db.get(Job, job_id)
    job.status = "RUNNING"
    db.commit()
    try:
        app = db.get(Application, job.application_id)
        summary = run_pipeline(db, app, actor)
        job.result_json = json.dumps(dict(summary=summary, fix_list=fix_list(db, app)))
        job.status = "DONE"
    except Exception as e:  # surfaced to the caller, never silently lost
        job.status, job.result_json = "FAILED", json.dumps({"error": str(e)[:300]})
    job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()


def create_job(db: Session, app: Application, kind: str = "precheck") -> Job:
    job = Job(id=str(uuid.uuid4()), application_id=app.id, kind=kind, status="PENDING", created_at=datetime.now(timezone.utc).replace(tzinfo=None))
    db.add(job)
    db.commit()
    return job
