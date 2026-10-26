import json
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_app
from app.core.db import get_db
from app.core.security import require_roles
from app.models import Application, Flag, FlagDecision, Institution, User
from app.services.audit import hash_chain as audit
from app.services.risk.inspection import inspection_list
from app.services.risk.scoring import ROUTING, TIER_LABEL, TIER_RANK, risk_summary, score_application

router = APIRouter(tags=["risk"])
STAFF = ("officer", "inspector")


class DecisionIn(BaseModel):
    decision: str
    reason: str

    @field_validator("decision")
    @classmethod
    def _d(cls, v):
        if v.upper() not in ("ACCEPT", "DISMISS"):
            raise ValueError("decision must be ACCEPT or DISMISS")
        return v.upper()

    @field_validator("reason")
    @classmethod
    def _r(cls, v):
        if len(v.strip()) < 5:
            raise ValueError("a reason of at least 5 characters is mandatory")
        return v.strip()


class InspectionIn(BaseModel):
    status: str
    note: str

    @field_validator("status")
    @classmethod
    def _s(cls, v):
        if v.upper() not in ("CONFIRMED", "CLEARED"):
            raise ValueError("status must be CONFIRMED or CLEARED")
        return v.upper()

    @field_validator("note")
    @classmethod
    def _n(cls, v):
        if len(v.strip()) < 5:
            raise ValueError("an on-site note of at least 5 characters is mandatory")
        return v.strip()


def flag_out(db: Session, f: Flag) -> dict:
    decisions = db.scalars(select(FlagDecision).where(FlagDecision.flag_id == f.id).order_by(FlagDecision.id)).all()
    return dict(id=f.id, application_id=f.application_id, engine=f.engine, code=f.code, severity=f.severity, confidence=f.confidence, message=f.message,
                explanation=f.explanation, evidence=json.loads(f.evidence), rule_id=f.rule_id, rule_pack_version=f.rule_pack_version,
                citation=json.loads(f.citation) if f.citation else None, status=f.status, document_id=f.document_id, forensic=f.forensic,
                preliminary_indicator=f.forensic, inspection_status=f.inspection_status, inspection_note=f.inspection_note, decisions=[dict(decision=d.decision, reason=d.reason, officer_id=d.officer_id, decided_at=d.decided_at.isoformat()) for d in decisions])


def queue_item(db: Session, a: Application) -> dict:
    inst = db.get(Institution, a.institution_id)
    reasons = json.loads(a.risk_reasons or "[]")
    return dict(application_id=a.id, institution_id=inst.id, institution_name=inst.name, state=inst.state, category=a.category, academic_year=a.academic_year, status=a.status,
                submitted_at=a.submitted_at.isoformat() if a.submitted_at else None, tier=a.risk_tier, tier_label=TIER_LABEL.get(a.risk_tier), score=a.risk_score,
                top_reason=reasons[0]["message"] if reasons else None, routing=ROUTING.get(a.risk_tier), rule_pack_version=a.rule_pack_version,
                open_flags=db.query(Flag).filter(Flag.application_id == a.id, Flag.status == "OPEN", Flag.severity != "INFO").count())


@router.post("/applications/{app_id}/score")
def score(app_id: int, user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    a = get_app(db, user, app_id)
    s = score_application(db, a)
    audit.log(db, user, "risk.rescore", f"application:{a.id}", {"application_id": a.id, "tier": s["tier"], "score": s["score"]})
    db.commit()
    return s


@router.get("/risk/queue")
def queue(tier: str | None = None, category: str | None = None, status: str | None = None, q: str | None = None, include_drafts: bool = False, academic_year: str | None = None,
          user: User = Depends(require_roles(*STAFF)), db: Session = Depends(get_db)):
    apps = db.scalars(select(Application)).all()
    ay = academic_year or max((a.academic_year for a in apps if a.risk_tier and a.status != "DRAFT"), default=None)  # default: latest academic year; pass academic_year=all for every year
    items = [queue_item(db, a) for a in apps if a.risk_tier and (include_drafts or a.status != "DRAFT") and (ay == "all" or a.academic_year == ay)]
    items = [i for i in items if (not tier or i["tier"] == tier.upper()) and (not category or i["category"] == category) and (not status or i["status"] == status)
             and (not q or q.lower() in i["institution_name"].lower())]
    return sorted(items, key=lambda i: (-TIER_RANK[i["tier"]], -(i["score"] or 0), i["application_id"]))


@router.get("/risk/stats")
def stats(user: User = Depends(require_roles(*STAFF)), db: Session = Depends(get_db)):
    all_apps = db.scalars(select(Application)).all()
    latest = max((a.academic_year for a in all_apps if a.risk_tier and a.status != "DRAFT"), default=None)
    apps = [a for a in all_apps if a.risk_tier and a.status != "DRAFT" and a.academic_year == latest]
    flags = db.scalars(select(Flag).where(Flag.application_id.in_([a.id for a in apps] or [0]), Flag.severity != "INFO")).all()
    return dict(by_tier={t: sum(a.risk_tier == t for a in apps) for t in ("GREEN", "AMBER", "RED")}, flags_by_engine=dict(Counter(f.engine for f in flags)),
                flags_by_severity=dict(Counter(f.severity for f in flags)), total_applications=len(apps))


@router.get("/risk/inspection-list")
def inspections(user: User = Depends(require_roles(*STAFF)), db: Session = Depends(get_db)):
    return inspection_list(db)


@router.get("/risk/inspection-list.pdf")
def inspections_pdf(user: User = Depends(require_roles(*STAFF)), db: Session = Depends(get_db)):
    from fastapi.responses import Response

    from app.services.reports.pdf import inspection_pdf

    pdf = inspection_pdf(inspection_list(db))
    audit.log(db, user, "report.inspection_list", "inspection-list", {"entries": len(inspection_list(db))})
    db.commit()
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=inspection-list.pdf"})


@router.get("/flags")
def list_flags(application_id: int, engine: str | None = None, status: str | None = None, user: User = Depends(require_roles(*STAFF)), db: Session = Depends(get_db)):
    get_app(db, user, application_id)
    q = select(Flag).where(Flag.application_id == application_id).order_by(Flag.id)
    return [flag_out(db, f) for f in db.scalars(q) if (not engine or f.engine == engine) and (not status or f.status == status.upper())]


@router.post("/flags/{flag_id}/inspection")
def inspect_flag(flag_id: int, body: InspectionIn, user: User = Depends(require_roles("inspector")), db: Session = Depends(get_db)):
    """The inspection committee's on-site verdict on a flagged item: CONFIRMED (the issue is real) or CLEARED (a false alarm)."""
    f = db.get(Flag, flag_id)
    if not f:
        raise HTTPException(404, "Flag not found")
    f.inspection_status, f.inspection_note, f.inspection_by_id = body.status, body.note, user.id
    f.inspected_at = datetime.now(timezone.utc).replace(tzinfo=None)
    audit.log(db, user, f"inspection.{body.status.lower()}", f"flag:{f.id}", {"application_id": f.application_id, "code": f.code, "note": body.note})
    db.commit()
    return flag_out(db, f)


@router.post("/flags/{flag_id}/decision")
def decide(flag_id: int, body: DecisionIn, user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    """Accept or dismiss a flag with a mandatory reason. There is deliberately no 'reject application' action anywhere."""
    f = db.get(Flag, flag_id)
    if not f:
        raise HTTPException(404, "Flag not found")
    a = get_app(db, user, f.application_id)
    f.status = "ACCEPTED" if body.decision == "ACCEPT" else "DISMISSED"
    db.add(FlagDecision(flag_id=f.id, officer_id=user.id, decision=body.decision, reason=body.reason, decided_at=datetime.now(timezone.utc).replace(tzinfo=None)))
    db.flush()
    before = (a.risk_tier, a.risk_score)
    s = score_application(db, a)
    audit.log(db, user, "flag.decision", f"flag:{f.id}", {"application_id": a.id, "code": f.code, "decision": body.decision, "reason": body.reason,
                                                         "score_before": before[1], "score_after": s["score"], "tier_before": before[0], "tier_after": s["tier"]})
    db.commit()
    return dict(flag=flag_out(db, f), risk=s)
