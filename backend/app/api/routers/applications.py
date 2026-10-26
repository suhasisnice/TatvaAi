import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_app, inst_of
from app.core.db import get_db
from app.core.security import current_user, require_roles
from app.models import Application, Flag, User
from app.services.audit import hash_chain as audit
from app.services.pipeline import run_pipeline
from app.services.risk.scoring import risk_summary

router = APIRouter(prefix="/applications", tags=["applications"])


class AppIn(BaseModel):
    category: str = "EOA"
    academic_year: str = "2027-28"


class FormPatch(BaseModel):
    form: dict


LEVELS = ("UG", "PG", "DIPLOMA")


def clean_programmes(items) -> list[dict]:
    """Course & intake settings: validate what the college typed and derive divisions (60 seats each).
    The faculty, room and computer norms are computed from these numbers, so bad input is refused, not guessed."""
    if not isinstance(items, list) or not items:
        raise HTTPException(422, "Add at least one course")
    out_list = []
    for i, p in enumerate(items, start=1):
        try:
            course, level = str(p.get("course", "")).strip(), str(p.get("level", "UG")).upper()
            intake, duration = int(p["intake"]), int(p.get("duration", 4))
        except (AttributeError, KeyError, TypeError, ValueError):
            raise HTTPException(422, f"Course {i}: name, level, intake and duration are required numbers")
        if not course or level not in LEVELS or not 1 <= intake <= 2000 or not 1 <= duration <= 6:
            raise HTTPException(422, f"Course {i}: needs a name, level UG/PG/DIPLOMA, intake 1 to 2000 and duration 1 to 6 years")
        out_list.append(dict(course=course, level=level, intake=intake, duration=duration, divisions=max(1, -(-intake // 60)),
                             programme=p.get("programme") or "ENGINEERING_AND_TECHNOLOGY"))
    return out_list


def out(db: Session, a: Application, user: User, detail: bool = False) -> dict:
    d = {c.name: getattr(a, c.name) for c in Application.__table__.columns if c.name not in ("form_data", "risk_reasons")}
    inst = inst_of(db, a)
    d.update(institution_name=inst.name, state=inst.state, aicte_id=inst.aicte_id)
    if user.role != "institution":  # institutions see the fix-list from pre-check, not the officer-side risk assessment
        d.update(risk=risk_summary(a) if a.risk_tier else None)
        d["open_flags"] = db.query(Flag).filter(Flag.application_id == a.id, Flag.status == "OPEN", Flag.severity != "INFO").count()
    else:
        d.pop("risk_tier"), d.pop("risk_score")
    if detail:
        d["form_data"] = json.loads(a.form_data) if a.form_data else None
    return d


@router.get("")
def list_apps(user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Application).order_by(Application.id)
    if user.role == "institution":
        q = q.where(Application.institution_id == user.institution_id)
    return [out(db, a, user) for a in db.scalars(q)]


@router.post("", status_code=201)
def create_app(body: AppIn, user: User = Depends(require_roles("institution")), db: Session = Depends(get_db)):
    prev = db.scalars(select(Application).where(Application.institution_id == user.institution_id, Application.academic_year < body.academic_year)
                      .order_by(Application.academic_year.desc())).first()
    form = json.loads(prev.form_data) if prev and prev.form_data else None  # pre-fill from last year
    if form:
        form["academic_year"], form["category"] = body.academic_year, body.category
    a = Application(institution_id=user.institution_id, category=body.category, academic_year=body.academic_year, form_data=json.dumps(form) if form else None)
    db.add(a)
    db.flush()
    audit.log(db, user, "application.create", f"application:{a.id}", {"application_id": a.id, "category": a.category, "academic_year": a.academic_year})
    db.commit()
    return out(db, a, user)


@router.get("/{app_id}")
def get_application(app_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return out(db, get_app(db, user, app_id), user, detail=True)


@router.patch("/{app_id}")
def patch_application(app_id: int, body: FormPatch, user: User = Depends(require_roles("institution")), db: Session = Depends(get_db)):
    a = get_app(db, user, app_id)
    if a.locked:
        raise HTTPException(409, "Application is submitted and locked; ask the Regulation Bureau to reopen it")
    form = json.loads(a.form_data) if a.form_data else {}
    if "programmes" in body.form:
        body.form["programmes"] = clean_programmes(body.form["programmes"])
    for k, v in body.form.items():
        form[k] = {**form[k], **v} if isinstance(form.get(k), dict) and isinstance(v, dict) else v
    a.form_data = json.dumps(form)
    audit.log(db, user, "application.update", f"application:{a.id}", {"application_id": a.id, "fields": sorted(body.form)})
    db.commit()
    return out(db, a, user, detail=True)


@router.post("/{app_id}/submit")
def submit(app_id: int, user: User = Depends(require_roles("institution")), db: Session = Depends(get_db)):
    a = get_app(db, user, app_id)
    if a.locked:
        raise HTTPException(409, "Already submitted")
    a.submitted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    summary = run_pipeline(db, a, user)  # final validation before the edit lock
    a.status, a.locked = "SUBMITTED", True
    audit.log(db, user, "application.submit", f"application:{a.id}", {"application_id": a.id, "tier": summary["tier"], "score": summary["score"], "rule_pack_version": summary["rule_pack_version"]})
    db.commit()
    return out(db, a, user)


@router.post("/{app_id}/reopen")
def reopen(app_id: int, user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    a = get_app(db, user, app_id)
    if not a.locked:
        raise HTTPException(409, "Application is not locked")
    if a.reopen_count >= 1:
        raise HTTPException(409, "An application can be reopened only once (APH p. 14)")
    a.locked, a.status, a.reopen_count = False, "REOPENED", a.reopen_count + 1
    audit.log(db, user, "application.reopen", f"application:{a.id}", {"application_id": a.id, "reopen_count": a.reopen_count})
    db.commit()
    return out(db, a, user)


@router.get("/{app_id}/evidence-graph")
def evidence_graph(app_id: int, user: User = Depends(require_roles("officer", "inspector")), db: Session = Depends(get_db)):
    from app.services.evidence.graph import graph_json

    return graph_json(db, get_app(db, user, app_id))


@router.get("/{app_id}/report.pdf")
def report_pdf(app_id: int, user: User = Depends(require_roles("officer", "inspector")), db: Session = Depends(get_db)):
    import hashlib

    from fastapi.responses import Response

    from app.services.reports.pdf import application_report

    a = get_app(db, user, app_id)
    pdf, digest = application_report(db, a)
    audit.log(db, user, "report.generate", f"application:{a.id}", {"application_id": a.id, "content_sha256": digest, "file_sha256": hashlib.sha256(pdf).hexdigest()})
    db.commit()
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=tatvaai-report-{a.id}.pdf"})


STAFF = ("officer", "inspector")


@router.get("/{app_id}/rule-results")
def get_rule_results(app_id: int, user: User = Depends(require_roles(*STAFF)), db: Session = Depends(get_db)):
    from app.services.views import rule_results

    return rule_results(db, get_app(db, user, app_id))


@router.get("/{app_id}/infrastructure")
def get_infrastructure(app_id: int, user: User = Depends(require_roles(*STAFF)), db: Session = Depends(get_db)):
    from app.services.risk.scoring import pack_for
    from app.services.views import infrastructure

    a = get_app(db, user, app_id)
    _, pack = pack_for(db, a)
    return infrastructure(db, a, pack.get("risk", {}).get("thresholds", {}).get("photo_gps_radius_km", 1.0))


@router.get("/{app_id}/timeline")
def get_timeline(app_id: int, user: User = Depends(require_roles(*STAFF)), db: Session = Depends(get_db)):
    from app.services.risk.scoring import pack_for
    from app.services.views import timeline

    a = get_app(db, user, app_id)
    _, pack = pack_for(db, a)
    return timeline(db, a, pack["academic_year_start"], pack.get("constants", {}).get("submission_deadline"))
