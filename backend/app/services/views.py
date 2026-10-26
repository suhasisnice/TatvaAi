"""Read models for the officer workbench: rule results, infrastructure map data, document timeline."""
import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters import sources
from app.models import Application, Document, ExtractedField, Fact, Flag, Institution, RuleResult
from app.services.engines.geo import haversine_km


def rule_results(db: Session, app: Application) -> list[dict]:
    out = []
    for r in db.scalars(select(RuleResult).where(RuleResult.application_id == app.id).order_by(RuleResult.id)):
        x = json.loads(r.result_json)
        out.append(dict(rule_id=r.rule_id, scope=r.scope, title=x["title"], status=r.status, severity=x["severity"], code=x["code"], message=x["message"], inputs=x["inputs"],
                        computed=x["computed"], citation=x["citation"], rule_pack_version=r.rule_pack_version))
    return out


def infrastructure(db: Session, app: Application, radius_km: float = 1.0) -> dict:
    inst = db.get(Institution, app.institution_id)
    facts = {}
    for f in db.scalars(select(Fact).where(Fact.application_id == app.id, Fact.subject.in_(["campus", "application"]))):
        facts.setdefault(f.subject, {})[f.attribute] = json.loads(f.value)
    campus = facts.get("campus")
    photos = []
    for d in db.scalars(select(Document).where(Document.application_id == app.id, Document.doc_type == "INFRA_PHOTO").order_by(Document.id)):
        v = {f.name: f.value for f in db.scalars(select(ExtractedField).where(ExtractedField.document_id == d.id))}
        lat, lon = v.get("gps_lat"), v.get("gps_lon")
        km = haversine_km(campus["lat"], campus["lon"], float(lat), float(lon)) if campus and lat and lon else None
        photos.append(dict(document_id=d.id, filename=d.filename, lat=float(lat) if lat else None, lon=float(lon) if lon else None, taken_at=v.get("taken_at"),
                           km_from_campus=round(km, 2) if km is not None else None, offsite=km is not None and km > radius_km))
    dups = []
    for f in db.scalars(select(Flag).where(Flag.application_id == app.id, Flag.code == "DUPLICATE_PHOTO")):
        ev = json.loads(f.evidence)
        if len(ev) > 1:
            dups.append(dict(flag_id=f.id, severity=f.severity, photo_document_id=ev[0]["document_id"], other_document_id=ev[1]["document_id"], distance=ev[1].get("distance"), message=f.message))
    res = sources.geo_footprints(f"{inst.slug}-main")
    footprints = res.body if res.available and res.body.get("features") else None
    return dict(campus=campus, radius_km=radius_km, photos=photos, duplicates=dups, footprints=footprints, footprint_source="Building footprint dataset (MOCK)",
                declared_built_up_total_m2=facts.get("application", {}).get("declared_built_up_total_m2"))


DATE_FIELDS = {  # document type -> [(field, label)]
    "AFFIDAVIT_2": [("estamp_issue_date", "E-stamp issued"), ("notarisation_date", "Affidavit notarised")],
    "TER_RECEIPT": [("payment_date", "TER fee paid")],
    "OCCUPANCY_CERTIFICATE": [("completion_date", "Building completed"), ("issue_date", "Occupancy certificate issued"), ("valid_till", "Occupancy certificate valid till")],
    "STRUCTURAL_STABILITY_CERTIFICATE": [("issue_date", "Structural certificate issued"), ("valid_till", "Structural certificate valid till")],
    "FIRE_SAFETY_CERTIFICATE": [("issue_date", "Fire certificate issued"), ("valid_till", "Fire certificate valid till")],
    "SATELLITE_MAP": [("capture_date", "Satellite imagery date")],
    "AUDITED_ACCOUNTS": [("report_date", "Audit report dated")],
    "LAND_DOCUMENT": [("registration_date", "Land registered")],
}


def timeline(db: Session, app: Application, ay_start: str, deadline: str | None) -> dict:
    events = []
    for d in db.scalars(select(Document).where(Document.application_id == app.id).order_by(Document.id)):
        vals = {f.name: (f.value, f) for f in db.scalars(select(ExtractedField).where(ExtractedField.document_id == d.id))}
        label_extra = f" ({vals['building_name'][0]})" if "building_name" in vals else ""
        for field, label in DATE_FIELDS.get(d.doc_type, []):
            if field in vals and len(vals[field][0] or "") == 10 and vals[field][0][4] == "-":
                f = vals[field][1]
                events.append(dict(date=vals[field][0], label=label + label_extra, document_id=d.id, document_type=d.doc_type, field=field, page=f.page,
                                   bbox=[f.x0, f.y0, f.x1, f.y1] if f.x0 is not None else None))
        info = json.loads(d.dsc_info) if d.dsc_info else {}
        for s in (info.get("signatures") or [])[:1]:
            if s.get("signed_at"):
                events.append(dict(date=s["signed_at"][:10], label=f"{d.doc_type} digitally signed", document_id=d.id, document_type=d.doc_type, field=None, page=None, bbox=None))
    events.append(dict(date=ay_start, label="Academic year starts", document_id=None, document_type=None, field=None, page=None, bbox=None, marker=True))
    if deadline:
        events.append(dict(date=deadline, label="Submission deadline", document_id=None, document_type=None, field=None, page=None, bbox=None, marker=True))
    events.sort(key=lambda e: e["date"])
    impossible = [dict(flag_id=f.id, message=f.message, evidence=json.loads(f.evidence)) for f in db.scalars(select(Flag).where(Flag.application_id == app.id, Flag.code == "TIMELINE_IMPOSSIBLE"))]
    bad = {(e.get("document_id"), e.get("field")) for i in impossible for e in i["evidence"]}
    for e in events:
        e["impossible"] = (e["document_id"], e["field"]) in bad
    return dict(events=events, impossible=impossible)
