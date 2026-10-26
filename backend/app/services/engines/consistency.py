"""Consistency: cross-document, cross-year, cross-institution (later uploader gets the flag, earlier owner an INFO notice),
timeline integrity, and public-disclosure cross-check."""
from sqlalchemy import select

from app.adapters import sources
from app.core import storage
from app.models import Application, Document, ExtractedField, FacultyRecord, Institution
from app.services.engines.common import Run, flag_from_result, form_source, make_flag
from app.services.engines.geo import haversine_km
from app.services.engines.imgsim import photo_distance

PHOTO_DISTANCE = 8  # of 64 bits; true crop+recompress copy measures 2, unrelated synthetic photos >= 14
ID_FIELDS = ("certificate_no", "estamp_cert_no", "receipt_no", "udin", "registration_no")
CROSS_YEAR_DOC_FIELDS = {"LAND_DOCUMENT": ("survey_no", "owner_name", "registration_no")}


def handles(rule: dict) -> bool:
    return rule["type"] in ("consistency", "timeline")


def _later(a: Document, b: Document) -> bool:
    """True if document a was uploaded after b."""
    return (a.uploaded_at, a.id) > (b.uploaded_at, b.id)


def _rule_flags(r: Run) -> list[dict]:
    flags = []
    for res in r.results:
        rule = r.rules[res["rule_id"]]
        if res["status"] != "FAIL" or not handles(rule):
            continue
        ev = []
        if rule["type"] == "consistency":
            src_field = {s["document_type"]: s["field"] for s in rule["sources"]}
            ev = [r.ev.field(m["document_id"], src_field[m["document_type"]]) for m in res["details"]["mismatches"]]
            ev.append(form_source(r, rule["reference"]))
        else:
            for spec in rule.get("evidence", []):
                for d in r.ev.of_type(spec["document_type"]):
                    if all(r.ev.value(d.id, k) == v for k, v in spec.get("where", {}).items()):
                        ev += [r.ev.field(d.id, f) for f in spec["fields"]]
            ev = ev or [form_source(r, "application:" + str(r.app.id))]
        doc = next((e["document_id"] for e in ev if e.get("document_id")), None)
        flags.append(flag_from_result("consistency", res, r, ev, document_id=doc, key=str(rule["id"])))
    return flags


def _cross_year(r: Run) -> list[dict]:
    flags, f = [], r.ctx["facts"]
    thr = r.thresholds.get("cross_year_change", 0.10)
    rec = f.get("aicte_record", {})
    inst = f["institution"]
    src = {"system_source": "AICTE records (MOCK)", "record_id": inst["aicte_id"], "mock": True}

    def changed(label, old, new, extra_ev):
        if old and abs(new - old) / old > thr:
            flags.append(make_flag("consistency", "MISMATCH_CROSS_YEAR", "MAJOR", f"{label} changed from {old:g} to {new:g} since the previous year ({(new - old) / old:+.0%})",
                                   extra_ev + [src], explanation=f"Unexplained change above {thr:.0%} compared with AICTE records.", key=label))

    prev_ay = max((y for c in rec.get("approved_intake", {}).values() for y in c if y < r.app.academic_year), default=None)
    for course, years in rec.get("approved_intake", {}).items():
        cur = f.get(f"programme:{course}", {}).get("intake")
        if prev_ay and cur is not None:
            changed(f"Approved intake for {course}", years.get(prev_ay), cur, [form_source(r, f"programme:{course}")])
    if rec.get("built_up_area_m2") and r.ctx.get("declared_built_up_total_m2"):
        changed("Declared built-up area", rec["built_up_area_m2"], r.ctx["declared_built_up_total_m2"], [form_source(r, "application.declared_built_up_total_m2")])
    if rec.get("faculty_count") and r.ctx.get("declared_faculty"):
        changed("Declared faculty count", rec["faculty_count"], r.ctx["declared_faculty"], [form_source(r, "faculty.declared_full_time")])
    c = rec.get("campus")
    if c and haversine_km(c["lat"], c["lon"], f["campus"]["lat"], f["campus"]["lon"]) > 0.5:
        flags.append(make_flag("consistency", "MISMATCH_CROSS_YEAR", "MAJOR", "Campus coordinates differ from AICTE records by more than 0.5 km", [form_source(r, "campus"), src], key="campus"))
    # same document type, previous year's application of the same institution
    prev = r.db.scalars(select(Application).where(Application.institution_id == r.app.institution_id, Application.academic_year < r.app.academic_year)
                        .order_by(Application.academic_year.desc())).first()
    if prev:
        for dtype, names in CROSS_YEAR_DOC_FIELDS.items():
            old_docs = r.db.scalars(select(Document).where(Document.application_id == prev.id, Document.doc_type == dtype)).all()
            for d in r.ev.of_type(dtype):
                for o in old_docs:
                    for n in names:
                        old_v = r.db.scalar(select(ExtractedField.value).where(ExtractedField.document_id == o.id, ExtractedField.name == n))
                        new_v = r.ev.value(d.id, n)
                        if old_v and new_v and old_v != new_v:
                            flags.append(make_flag("consistency", "MISMATCH_CROSS_YEAR", "MAJOR", f"{dtype}: {n.replace('_', ' ')} is {new_v!r} but was {old_v!r} in {prev.academic_year}",
                                                   [r.ev.field(d.id, n), dict(r.ev.doc(o.id), field=n, value=old_v, academic_year=prev.academic_year)], document_id=d.id, key=n))
    return flags


def _cross_institution(r: Run) -> list[dict]:
    flags, db = [], r.db
    own_id = r.app.institution_id
    # faculty registered full-time elsewhere (AICTE registry) -> later registrant is flagged
    dups = r.ctx["facts"].get("faculty", {}).get("duplicates_cross_institution", [])
    later = [d for d in dups if d["own_since"] and all(d["own_since"] > s for s in d["other_since"])]
    earlier = [d for d in dups if d not in later]
    fl = r.ev.of_type("FACULTY_LIST")
    fev = [r.ev.doc(fl[0].id)] if fl else []
    reg = {"system_source": "AICTE faculty registry (MOCK)", "record_id": r.ctx["facts"]["institution"]["aicte_id"], "mock": True}
    if later:
        ids = ", ".join(d["faculty_id"] for d in later[:5]) + (" ..." if len(later) > 5 else "")
        flags.append(make_flag("consistency", "DUPLICATE_FACULTY_CROSS_INSTITUTION", "MAJOR",
                               f"{len(later)} faculty listed as full-time are already registered full-time at another institution ({ids})",
                               fev + [dict(reg, faculty_ids=[d["faculty_id"] for d in later], other_institutions=sorted({o for d in later for o in d["other_institutions"]}))],
                               explanation="A faculty member can be full-time at only one institution; these entries were excluded from the valid-faculty count.",
                               document_id=fl[0].id if fl else None))
    if earlier:
        flags.append(make_flag("consistency", "DUPLICATE_FACULTY_CROSS_INSTITUTION", "INFO", f"{len(earlier)} of this institution's faculty are also listed full-time by another institution (this institution registered first)",
                               fev + [reg], key="earlier"))
    # same national-ID hash on another institution's faculty list this year (uploaded later = flagged)
    mine = {x.national_id_hash: x for x in db.scalars(select(FacultyRecord).where(FacultyRecord.application_id == r.app.id))}
    flagged_ids = {d["faculty_id"] for d in dups}
    if mine:
        rows = db.execute(select(FacultyRecord, Application).join(Application, FacultyRecord.application_id == Application.id)
                          .where(FacultyRecord.national_id_hash.in_(list(mine)), FacultyRecord.institution_id != own_id, Application.academic_year == r.app.academic_year)).all()
        new = [(fr, a) for fr, a in rows if fr.faculty_id not in flagged_ids and a.id < r.app.id]
        if new:
            flags.append(make_flag("consistency", "DUPLICATE_FACULTY_CROSS_INSTITUTION", "MAJOR", f"{len(new)} faculty national-ID hashes also appear on another institution's list this year",
                                   fev, document_id=fl[0].id if fl else None, key="nid"))
    # identical files / identifiers used by another institution
    for d in r.ev.docs:
        others = db.scalars(select(Document).join(Application, Document.application_id == Application.id)
                            .where(Document.sha256 == d.sha256, Application.institution_id != own_id, Document.doc_type != "INFRA_PHOTO")).all()
        for o in others:
            sev = "MAJOR" if _later(d, o) else "INFO"
            flags.append(make_flag("consistency", "DUPLICATE_DOCUMENT_CROSS_INSTITUTION", sev, f"{d.doc_type} is byte-identical to a document uploaded by another institution",
                                   [r.ev.doc(d.id), dict(r.ev.doc(o.id), other_institution=True)], document_id=d.id, key=f"sha-{o.id}"))
        for fname in ID_FIELDS:
            v = r.ev.value(d.id, fname)
            if not v:
                continue
            same = db.execute(select(Document).join(ExtractedField, ExtractedField.document_id == Document.id).join(Application, Document.application_id == Application.id)
                              .where(ExtractedField.name == fname, ExtractedField.value == v, Application.institution_id != own_id)).scalars().all()
            for o in same:
                flags.append(make_flag("consistency", "DUPLICATE_DOCUMENT_CROSS_INSTITUTION", "MAJOR" if _later(d, o) else "INFO",
                                       f"{fname.replace('_', ' ')} {v} is also used on a document of another institution", [r.ev.field(d.id, fname), dict(r.ev.doc(o.id), other_institution=True)],
                                       document_id=d.id, key=f"{fname}-{o.id}"))
    # reused photos (crop/recompression-tolerant perceptual hash across all institutions)
    mine_p = r.ev.of_type("INFRA_PHOTO")
    if mine_p:
        others = db.scalars(select(Document).join(Application, Document.application_id == Application.id)
                            .where(Document.doc_type == "INFRA_PHOTO", Application.institution_id != own_id)).all()
        inst_of = {o.id: db.scalar(select(Application.institution_id).where(Application.id == o.application_id)) for o in others}
        cache = {}
        load = lambda doc: cache.setdefault(doc.id, storage.get(doc.storage_key))
        for d in mine_p:
            near = {}
            for o in others:
                dist = photo_distance(load(d), load(o))
                if dist <= PHOTO_DISTANCE and (inst_of[o.id] not in near or _later(o, near[inst_of[o.id]][0])):
                    near[inst_of[o.id]] = (o, dist)
            for inst, (o, dist) in near.items():
                is_later = _later(d, o)
                flags.append(make_flag("consistency", "DUPLICATE_PHOTO", "MAJOR" if is_later else "INFO",
                                       f"Photo {d.filename} is a near-copy of a photo uploaded by another institution (perceptual-hash distance {dist}/64)" if is_later
                                       else f"Photo {d.filename} was reused by another institution (this institution uploaded first)",
                                       [r.ev.doc(d.id), dict(r.ev.doc(o.id), other_institution=True, distance=dist)],
                                       explanation="Cropped, resized or recompressed copies keep a similar perceptual hash.", confidence=round(1 - dist / 64, 2),
                                       document_id=d.id, forensic=True, key=f"{o.id}"))
    return flags


def _disclosure(r: Run) -> list[dict]:
    inst = r.db.get(Institution, r.app.institution_id)
    site = sources.website_disclosure(inst.slug)
    src = {"system_source": "Institution website (MOCK)", "record_id": f"{inst.slug}/mandatory-disclosure", "mock": True}
    if not site:
        return [make_flag("consistency", "ISSUER_UNAVAILABLE", "INFO", "The institution's mandatory-disclosure page could not be read", [src], key="web")]
    f = r.ctx["facts"]
    intake = sum(v["intake"] for k, v in f.items() if k.startswith("programme:"))
    diffs = []
    if site["intake_total"] != intake:
        diffs.append(f"intake {site['intake_total']} on website vs {intake} declared")
    declared_fac = f.get("faculty", {}).get("declared_full_time")
    if declared_fac is not None and site["faculty_total"] != declared_fac:
        diffs.append(f"faculty {site['faculty_total']} on website vs {declared_fac} declared")
    claim = f.get("accreditation_claim")
    if claim and str(claim["score"]) not in (site["accreditation"] or ""):
        diffs.append(f"accreditation {site['accreditation']!r} on website vs {claim['body']} {claim['score']} claimed")
    if not diffs:
        return []
    return [make_flag("consistency", "DISCLOSURE_MISMATCH", "MAJOR", "Mandatory disclosure on the institution's website differs from the application: " + "; ".join(diffs),
                      [src, form_source(r, "application:" + str(r.app.id))], explanation="Institutions must publish accurate mandatory disclosures (APH Annexure-18, p. 180).", key="web")]


def run(r: Run) -> list[dict]:
    return _rule_flags(r) + _cross_year(r) + _cross_institution(r) + _disclosure(r)
