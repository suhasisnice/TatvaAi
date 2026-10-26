"""Builds the rule-evaluation context from the evidence graph (facts), never from raw tables."""
import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Fact

SIGNED = ("SIGNED_VALID", "SIGNED_MODIFIED", "SIGNED_UNTRUSTED", "SIGNED_INVALID")
DESIGNATION = {"Professor": "valid_professors", "Associate Professor": "valid_associates", "Assistant Professor": "valid_assistants"}


def build_context(db: Session, app: Application, pack: dict) -> dict:
    facts = [(f.subject, f.attribute, json.loads(f.value), f) for f in db.scalars(select(Fact).where(Fact.application_id == app.id))]
    by: dict[str, dict] = {}
    docs_by_subject: dict[str, dict] = {}
    for subj, attr, val, f in facts:
        by.setdefault(subj, {})[attr] = val
        if subj.startswith("doc:"):
            docs_by_subject.setdefault(subj, {"id": f.document_id, "fields": {}})["fields"][attr] = val

    docs: dict[str, list] = {}
    for subj, d in docs_by_subject.items():
        f = d["fields"]
        dtype = subj.split(":")[1].split("#")[0]
        d.update(subject=subj, doc_type=dtype, dsc_status=f.get("dsc_status"), signed_at=f.get("signed_at"),
                 checks={"dsc_valid": f.get("dsc_status") in SIGNED, "estamp_value_100": str(f.get("estamp_value", "")).strip() == "100"})
        docs.setdefault(dtype, []).append(d)

    ay_start = pack["academic_year_start"]
    ctx: dict = dict(category=app.category, academic_year=app.academic_year, academic_year_start=ay_start, docs=docs,
                     submission_date=app.submitted_at.date().isoformat() if app.submitted_at else None,
                     submission_deadline=pack.get("constants", {}).get("submission_deadline") if app.academic_year == "2027-28" else None)
    ctx["form_values"] = {f"{s}.{a}": v for s, a, v, _ in facts if s in ("institution", "signatory")}

    # programmes -> groups and totals
    progs = [(s.split(":", 1)[1], v) for s, v in by.items() if s.startswith("programme:")]
    enrol = by.get("enrolment", {})
    annual_total = sum(p["intake"] for _, p in progs)
    ctx.update(annual_intake_total=annual_total, S_total=sum(p["intake"] * p["duration"] for _, p in progs), divisions_total=sum(p["divisions"] for _, p in progs),
               ncourses_total=len(progs), max_duration=max((p["duration"] for _, p in progs), default=0))
    dept = by.get("faculty", {}).get("valid_by_department", {})
    ctx["valid_full_time_faculty_all"] = by.get("faculty", {}).get("valid_full_time")
    groups = {}
    for course, p in progs:
        groups.setdefault((p["programme"], p["level"]), []).append((course, p))
    ctx["groups"] = []
    for (programme, level), items in groups.items():
        share = sum(p["intake"] for _, p in items) / annual_total
        counts = {"valid_professors": 0, "valid_associates": 0, "valid_assistants": 0}
        for course, _ in items:
            for des, n in dept.get(course, {}).items():
                counts[DESIGNATION.get(des, "valid_assistants")] += n
        v = dict(sum_approved_intake_all_years=sum(p["intake"] * p["duration"] for _, p in items), annual_intake=sum(p["intake"] for _, p in items),
                 avg_sanctioned_3yr=enrol.get("avg_sanctioned_3yr", 0) * share, avg_admitted_3yr=enrol.get("avg_admitted_3yr", 0) * share,
                 valid_full_time_faculty=sum(counts.values()), **counts)
        ctx["groups"].append(dict(programme=programme, level=level, vars=v))

    # infrastructure (flat)
    ctx.update(by.get("infrastructure", {}))

    # buildings, dates
    buildings = {s.split(":", 1)[1]: v for s, v in by.items() if s.startswith("building:")}
    ctx["has_buildings"] = bool(buildings)
    if buildings:
        earliest = min(b["completion_date"] for b in buildings.values())
        ctx["earliest_completion_date"] = earliest
        y, m, d = map(int, ay_start.split("-"))
        e = date.fromisoformat(earliest)
        ctx["max_building_age_years"] = (date(y, m, d) - e).days / 365.25
    prov = [n for n, b in buildings.items() if b["oc_type"] == "PROVISIONAL"]
    ctx["uses_provisional_oc"] = bool(prov)
    hist = {h["building"]: h for h in by.get("aicte_record", {}).get("provisional_oc_history", [])}
    ctx["provisional_oc_consecutive_years"] = max([len(hist.get(n, {}).get("academic_years", [])) + 1 for n in prov], default=0)

    # documents-derived
    aff = docs.get("AFFIDAVIT_2", [{}])[0].get("fields", {})
    ctx.update(has_affidavit=bool(aff), affidavit_estamp_issue_date=aff.get("estamp_issue_date"), affidavit_notarisation_date=aff.get("notarisation_date"))
    fire = docs.get("FIRE_SAFETY_CERTIFICATE", [{}])[0].get("fields", {})
    ctx.update(has_fire=bool(fire), fire_issue_date=fire.get("issue_date"))
    signed = [d["signed_at"][:10] for ds in docs.values() for d in ds if d.get("signed_at")]
    ctx["latest_signed_date"] = max(signed) if signed else None

    claim = by.get("accreditation_claim")
    ctx.update(has_accreditation_claim=bool(claim), naac_claimed_score=(claim or {}).get("score", 0.0),
               naac_listed_score=by.get("accreditation_list", {}).get("naac_score") or 0.0)
    ctx["facts"] = by  # subject -> {attribute: value}, for engines that need more than rule variables
    ctx["declared_built_up_total_m2"] = by.get("application", {}).get("declared_built_up_total_m2")
    ctx["declared_faculty"] = by.get("faculty", {}).get("declared_full_time")
    return ctx
