from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.deps import require_roles
from app.models import Application, Document, Flag, User

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])

CHECKLIST_TEXT = {
    "MODIFIED_AFTER_SIGNING": "Compare the field with the original at the sub-registrar / revenue office.",
    "TAMPER_SUSPECTED": "Ask for the original paper document; check the highlighted field for overwriting.",
    "ISSUER_MISMATCH": "Verify directly with the issuing authority.",
    "QR_MISMATCH": "Scan the original certificate's QR and confirm validity with the issuer.",
    "TIMELINE_IMPOSSIBLE": "Check the stamp-paper and notary register dates.",
    "DUPLICATE_FACULTY_CROSS_INSTITUTION": "Check attendance, salary and appointment records; interview a sample.",
    "NORM_FACULTY_SHORTFALL": "Count faculty against payroll and the portal list.",
    "DISCLOSURE_MISMATCH": "Compare the website's mandatory disclosure with the declared figures.",
    "BUILTUP_AREA_IMPLAUSIBLE": "Measure each block against the approved building plan.",
    "DUPLICATE_PHOTO": "Photograph each lab/classroom yourself during the visit.",
    "MISMATCH_CROSS_DOC": "Check originals against the online application form.",
}


@router.get("/queue")
def queue(user: User = Depends(require_roles("officer", "inspector")), db: Session = Depends(get_db)):
    apps = db.query(Application).filter(Application.status.in_(["SUBMITTED", "REOPENED"])).all()
    rows = []
    for a in apps:
        open_flags = db.query(Flag).filter(Flag.application_id == a.id, Flag.status == "OPEN").count()
        rows.append({
            "id": a.id, "institution_name": a.institution.name, "category": a.category,
            "academic_year": a.academic_year, "risk_tier": a.risk_tier, "risk_score": a.risk_score,
            "top_reason": (a.top_reasons or ["-"])[0], "open_flags": open_flags,
        })
    order = {"RED": 0, "AMBER": 1, "GREEN": 2, None: 3}
    rows.sort(key=lambda r: (order.get(r["risk_tier"], 3), -r["risk_score"]))
    kpi = {
        "total": len(rows),
        "red": sum(1 for r in rows if r["risk_tier"] == "RED"),
        "amber": sum(1 for r in rows if r["risk_tier"] == "AMBER"),
        "green": sum(1 for r in rows if r["risk_tier"] == "GREEN"),
    }
    return {"kpi": kpi, "rows": rows}


def _flag_document(db: Session, flag: Flag) -> Document | None:
    for item in (flag.evidence or []):
        doc_id = item.get("document_id")
        if doc_id:
            return db.query(Document).get(doc_id)
    return None


@router.get("/inspection-list")
def inspection_list(user: User = Depends(require_roles("officer", "inspector")), db: Session = Depends(get_db)):
    apps = (
        db.query(Application)
        .filter(Application.status.in_(["SUBMITTED", "REOPENED"]), Application.risk_tier == "RED")
        .order_by(Application.risk_score.desc())
        .all()
    )
    result = []
    for a in apps:
        flags = (
            db.query(Flag)
            .filter(Flag.application_id == a.id, Flag.status != "DISMISSED", Flag.severity != "INFO")
            .order_by(Flag.severity.desc())
            .all()
        )

        groups: dict[str, dict] = {}
        for f in flags:
            doc = _flag_document(db, f)
            key = f"doc:{doc.id}" if doc else "institution"
            if key not in groups:
                groups[key] = {
                    "document_id": doc.id if doc else None,
                    "document_type": doc.doc_type.replace("_", " ").title() if doc else "Institution-wide",
                    "file_name": doc.file_name if doc else None,
                    "items": [],
                }
            groups[key]["items"].append({
                "flag_id": f.id, "code": f.code, "severity": f.severity,
                "message": f.message,
                "instruction": CHECKLIST_TEXT.get(f.code, "Verify on site."),
                "inspection_status": f.inspection_status, "inspection_note": f.inspection_note,
                "inspection_by": f.inspection_by,
            })

        # Institution-wide group last; otherwise keep CRITICAL-first document order.
        ordered_groups = sorted(
            groups.values(),
            key=lambda g: (g["document_id"] is None, -max(
                {"CRITICAL": 3, "MAJOR": 2, "MINOR": 1}.get(i["severity"], 0) for i in g["items"]
            )),
        )

        total_items = sum(len(g["items"]) for g in ordered_groups)
        resolved_items = sum(
            1 for g in ordered_groups for i in g["items"] if i["inspection_status"] != "PENDING"
        )

        result.append({
            "application_id": a.id, "institution_name": a.institution.name, "score": a.risk_score,
            "top_reasons": a.top_reasons or [], "document_groups": ordered_groups,
            "progress": {"resolved": resolved_items, "total": total_items},
        })
    return result
