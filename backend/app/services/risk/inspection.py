"""Risk-targeted inspection list: RED applications ranked by score, each with reasons and an on-site checklist."""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Document, Flag, Institution, User
from app.services.risk.scoring import TIER_LABEL

CHECKS = {
    "MODIFIED_AFTER_SIGNING": "Compare the survey number and other land-record details with the original record at the sub-registrar / revenue office.",
    "TAMPER_SUSPECTED": "Ask for the original paper document and check the highlighted field for overwriting or font differences.",
    "SIGNATURE_INVALID": "Ask the institution to produce the original digitally signed file and verify it on site.",
    "QR_MISMATCH": "Scan the QR on the original certificate and confirm the validity date with the issuing authority.",
    "TIMELINE_IMPOSSIBLE": "Check the e-stamp paper and the notary's register for the actual dates.",
    "DUPLICATE_PHOTO": "Photograph each laboratory yourself and compare with the submitted photos; confirm the equipment is on site.",
    "PHOTO_GPS_OFFSITE": "Confirm the location of the classrooms/labs shown in the submitted photos.",
    "DUPLICATE_FACULTY_CROSS_INSTITUTION": "Check attendance, salary and appointment records of the flagged faculty; interview a sample.",
    "NORM_FACULTY_SHORTFALL": "Count full-time faculty present against the payroll and the faculty list; verify cadre.",
    "BUILTUP_AREA_IMPLAUSIBLE": "Measure built-up area of each block and compare with the approved building plan.",
    "BUILDING_NOT_VISIBLE_ON_DATE": "Check the construction date of the named block against the completion certificate and site records.",
    "DISCLOSURE_MISMATCH": "Compare the mandatory-disclosure page with the figures declared in the application.",
    "NORM_ROOMS": "Count and measure classrooms, tutorial rooms and laboratories.",
    "NORM_AREA": "Measure the workshop, computer centre, library and seminar hall.",
    "NORM_PC_RATIO": "Count working PCs and printers in the computer labs.",
    "NORM_BANDWIDTH": "Check the internet bandwidth agreement and run a speed test.",
    "ISSUER_MISMATCH": "Verify the document directly with the issuing authority.",
    "MISMATCH_CROSS_DOC": "Check the names/numbers in the originals against the application form.",
    "MISMATCH_CROSS_YEAR": "Ask for an explanation and supporting papers for the change from last year.",
    "DOC_EXPIRES_BEFORE_AY": "Ask for the renewed certificate.", "PROVISIONAL_OC_LIMIT_EXCEEDED": "Ask for the full occupancy certificate.",
}


def checklist(flags: list[Flag]) -> list[dict]:
    seen, out = set(), []
    for f in sorted(flags, key=lambda f: ({"CRITICAL": 0, "MAJOR": 1, "MINOR": 2, "INFO": 3}[f.severity], f.code)):
        if f.severity == "INFO" or f.status == "DISMISSED" or f.code in seen or f.code not in CHECKS:
            continue
        seen.add(f.code)
        out.append(dict(code=f.code, severity=f.severity, check=CHECKS[f.code], finding=f.message))
    return out


def document_groups(db: Session, flags: list[Flag]) -> list[dict]:
    """The on-site checklist grouped by the document each flag came from (institution-wide findings last),
    one item per flag, each carrying the inspector's on-site verdict."""
    groups: dict = {}
    for f in sorted(flags, key=lambda f: ({"CRITICAL": 0, "MAJOR": 1, "MINOR": 2, "INFO": 3}[f.severity], f.code)):
        if f.severity == "INFO" or f.status == "DISMISSED" or f.code not in CHECKS:
            continue
        g = groups.setdefault(f.document_id, dict(document_id=f.document_id, items=[]))
        by = db.get(User, f.inspection_by_id) if f.inspection_by_id else None
        g["items"].append(dict(flag_id=f.id, code=f.code, severity=f.severity, check=CHECKS[f.code], finding=f.message,
                               inspection_status=f.inspection_status, inspection_note=f.inspection_note, inspection_by=by.name if by else None))
    out = []
    for doc_id, g in groups.items():
        doc = db.get(Document, doc_id) if doc_id else None
        out.append(dict(document_id=doc_id, document_type=doc.doc_type.replace("_", " ").title() if doc else "Institution-wide", filename=doc.filename if doc else None, items=g["items"]))
    return sorted(out, key=lambda g: (g["document_id"] is None, min({"CRITICAL": 0, "MAJOR": 1, "MINOR": 2}[i["severity"]] for i in g["items"])))


def inspection_list(db: Session, academic_year: str | None = None) -> list[dict]:
    """RED applications of the latest academic year (or the given one), highest score first."""
    ay = academic_year or db.scalar(select(Application.academic_year).where(Application.risk_tier.is_not(None), Application.status != "DRAFT").order_by(Application.academic_year.desc()).limit(1))
    rows = db.scalars(select(Application).where(Application.risk_tier == "RED", Application.status != "DRAFT", Application.academic_year == ay)
                      .order_by(Application.risk_score.desc(), Application.id)).all()
    out = []
    for rank, a in enumerate(rows, start=1):
        inst = db.get(Institution, a.institution_id)
        flags = list(db.scalars(select(Flag).where(Flag.application_id == a.id)))
        out.append(dict(rank=rank, application_id=a.id, institution_id=inst.id, institution_name=inst.name, state=inst.state, aicte_id=inst.aicte_id, academic_year=a.academic_year,
                        category=a.category, tier=a.risk_tier, tier_label=TIER_LABEL[a.risk_tier], score=a.risk_score, reasons=json.loads(a.risk_reasons or "[]"),
                        checklist=checklist(flags), document_groups=(groups := document_groups(db, flags)), rule_pack_version=a.rule_pack_version,
                        progress=dict(resolved=sum(i["inspection_status"] != "PENDING" for g in groups for i in g["items"]), total=sum(len(g["items"]) for g in groups))))
    return out
