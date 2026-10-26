"""Evidence graph: every fact stored with provenance (document/page/bbox, online form, or system record). Tables, not a graph DB."""
import json
from collections import Counter, defaultdict

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.adapters import accreditation_lists, aicte_records
from app.models import Application, Document, ExtractedField, Fact, FacultyRecord, Institution


def _add(db, app_id, subject, attribute, value, unit=None, source_type="form", **src):
    db.add(Fact(application_id=app_id, subject=subject, attribute=attribute, value=json.dumps(value), unit=unit, source_type=source_type,
                document_id=src.get("document_id"), page=src.get("page"), bbox=json.dumps(src["bbox"]) if src.get("bbox") else None,
                system_source=src.get("system_source"), record_id=src.get("record_id")))


def doc_subjects(docs: list[Document]) -> dict[int, str]:
    n, out = Counter(), {}
    for d in sorted(docs, key=lambda d: d.id):
        n[d.doc_type] += 1
        out[d.id] = f"doc:{d.doc_type}#{n[d.doc_type]}"
    return out


def _form_facts(db, app, form):
    a = app.id
    i = form["institution"]
    for k in ("name", "trust_name", "address", "state", "survey_no", "aicte_id"):
        _add(db, a, "institution", k, i[k])
    _add(db, a, "campus", "lat", i["lat"], "deg")
    _add(db, a, "campus", "lon", i["lon"], "deg")
    _add(db, a, "signatory", "name", form["signatory"]["name"])
    for p in form["programmes"]:
        for k in ("programme", "level", "intake", "duration", "divisions"):
            _add(db, a, f"programme:{p['course']}", k, p[k])
    for k, v in form["enrolment"].items():
        _add(db, a, "enrolment", k, v)
    for b in form["buildings"]:
        for k in ("completion_date", "floors", "declared_built_up_m2", "oc_type"):
            _add(db, a, f"building:{b['name']}", k, b[k], "m2" if k.endswith("m2") else None)
    _add(db, a, "application", "declared_built_up_total_m2", form["declared_built_up_total_m2"], "m2")
    _add(db, a, "faculty", "declared_full_time", form["faculty"]["declared_full_time"])
    for item, v in form["infrastructure"].items():
        if isinstance(v, dict):
            _add(db, a, "infrastructure", f"{item}_count", v["count"])
            _add(db, a, "infrastructure", f"{item}_area_each_m2", v["area_each_m2"], "m2")
        else:
            _add(db, a, "infrastructure", item, v)
    if form.get("accreditation_claim"):
        _add(db, a, "accreditation_claim", "body", form["accreditation_claim"]["body"])
        _add(db, a, "accreditation_claim", "score", form["accreditation_claim"]["score"])


def _document_facts(db, app):
    docs = list(db.scalars(select(Document).where(Document.application_id == app.id)))
    names = doc_subjects(docs)
    for d in docs:
        s = names[d.id]
        for f in db.scalars(select(ExtractedField).where(ExtractedField.document_id == d.id)):
            if f.name.startswith("_") or f.value is None:
                continue
            bbox = [f.x0, f.y0, f.x1, f.y1] if f.x0 is not None else None
            _add(db, app.id, s, f.name, f.value, source_type="document", document_id=d.id, page=f.page, bbox=bbox)
        info = json.loads(d.dsc_info) if d.dsc_info else {}
        sigs = info.get("signatures") or [{}]
        for k, v in dict(dsc_status=d.dsc_status, sha256=d.sha256, signed_at=sigs[0].get("signed_at"), qr_payload=d.qr_payload,
                         carried_forward_from=d.carried_forward_from).items():
            if v is not None:
                _add(db, app.id, s, k, v, source_type="document", document_id=d.id)


def _faculty_facts(db, app, inst):
    rows = list(db.scalars(select(FacultyRecord).where(FacultyRecord.application_id == app.id)))
    if not rows:
        return
    own = inst.aicte_id
    dups, unavailable = [], False
    for r in rows:
        res = aicte_records.faculty_registry(r.faculty_id)
        if not res.available:
            unavailable = True
            continue
        regs = [x for x in res.body.get("registrations", []) if x["full_time"]]
        others = [x for x in regs if x["institution_aicte_id"] != own]
        if others:
            mine = [x["since"] for x in regs if x["institution_aicte_id"] == own]
            dups.append(dict(faculty_id=r.faculty_id, other_institutions=[x["institution_aicte_id"] for x in others],
                             other_since=[x["since"] for x in others], own_since=min(mine) if mine else None))
    bad = {d["faculty_id"] for d in dups}
    valid = [r for r in rows if r.full_time and r.faculty_id not in bad]
    by_dept = defaultdict(lambda: Counter())
    for r in valid:
        by_dept[r.department][r.designation] += 1
    a = app.id
    _add(db, a, "faculty", "record_count", len(rows), source_type="document")
    _add(db, a, "faculty", "valid_full_time", len(valid), source_type="derived", system_source="faculty_records + AICTE faculty registry (MOCK)")
    _add(db, a, "faculty", "duplicates_cross_institution", dups, source_type="system", system_source="AICTE faculty registry (MOCK)", record_id=own)
    _add(db, a, "faculty", "valid_by_department", {k: dict(v) for k, v in by_dept.items()}, source_type="derived")
    _add(db, a, "faculty", "registry_unavailable", unavailable, source_type="system", system_source="AICTE faculty registry (MOCK)")


def _system_facts(db, app, inst, form):
    rec = aicte_records.institution_record(inst.aicte_id)
    src = dict(system_source=rec.source, record_id=inst.aicte_id)
    _add(db, app.id, "aicte_record", "available", rec.available and rec.record is not None, source_type="system", **src)
    for k, v in (rec.record or {}).items():
        if k not in ("institution_id", "name"):
            _add(db, app.id, "aicte_record", k, v, source_type="system", **src)
    if form.get("accreditation_claim"):
        g = accreditation_lists.naac_grades()
        score = (g.body or {}).get("grades", {}).get(inst.aicte_id) if g.available else None
        _add(db, app.id, "accreditation_list", "naac_score", score, source_type="system", system_source=g.source, record_id=inst.aicte_id)


def build_facts(db: Session, app: Application) -> int:
    """Rebuild all facts for an application (idempotent). Returns the number of facts."""
    db.execute(delete(Fact).where(Fact.application_id == app.id))
    inst = db.get(Institution, app.institution_id)
    form = json.loads(app.form_data) if app.form_data else None
    if form:
        _form_facts(db, app, form)
    _document_facts(db, app)
    _faculty_facts(db, app, inst)
    if form:
        _system_facts(db, app, inst, form)
    db.commit()
    return db.query(Fact).filter_by(application_id=app.id).count()


def graph_json(db: Session, app: Application) -> dict:
    if not db.query(Fact).filter_by(application_id=app.id).count():
        build_facts(db, app)
    docs = {d.id: d for d in db.scalars(select(Document).where(Document.application_id == app.id))}
    names = doc_subjects(list(docs.values()))
    facts = []
    for f in db.scalars(select(Fact).where(Fact.application_id == app.id).order_by(Fact.id)):
        src = {"type": f.source_type}
        if f.document_id:
            src |= dict(document_id=f.document_id, document_type=docs[f.document_id].doc_type, page=f.page, bbox=json.loads(f.bbox) if f.bbox else None)
        if f.system_source:
            src |= dict(system_source=f.system_source, record_id=f.record_id, mock=True)
        facts.append(dict(id=f.id, subject=f.subject, attribute=f.attribute, value=json.loads(f.value), unit=f.unit, source=src))
    return dict(application_id=app.id, academic_year=app.academic_year,
                documents=[dict(id=i, subject=names[i], doc_type=d.doc_type, sha256=d.sha256, dsc_status=d.dsc_status, carried_forward_from=d.carried_forward_from)
                           for i, d in docs.items()],
                facts=facts)
