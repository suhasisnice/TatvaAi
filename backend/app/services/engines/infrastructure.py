"""Infrastructure evidence checks (part of the Compliance engine): photo GPS/time, built-up area plausibility from building
footprints, and satellite-imagery timing of completion certificates.
# ponytail: FEATURE_YOLO PC counting in lab photos is not wired; add a check here comparing detections with declared PCs."""
from datetime import date

from app.adapters import sources
from app.models import Institution
from app.services.engines.common import Run, form_source, make_flag
from app.services.engines.geo import haversine_km


def _photo_checks(r: Run) -> list[dict]:
    flags, f = [], r.ctx["facts"]
    radius = r.thresholds.get("photo_gps_radius_km", 1.0)
    lat0, lon0 = f["campus"]["lat"], f["campus"]["lon"]
    for d in r.ev.of_type("INFRA_PHOTO"):
        lat, lon = r.ev.value(d.id, "gps_lat"), r.ev.value(d.id, "gps_lon")
        if lat is not None and lon is not None:
            km = haversine_km(lat0, lon0, float(lat), float(lon))
            if km > radius:
                flags.append(make_flag("compliance", "PHOTO_GPS_OFFSITE", "MAJOR", f"Photo {d.filename} was taken {km:.0f} km from the declared campus (limit {radius:g} km)",
                                       [r.ev.field(d.id, "gps_lat"), r.ev.field(d.id, "gps_lon"), form_source(r, "campus")], forensic=True, confidence=0.9, document_id=d.id,
                                       explanation=f"EXIF GPS {lat}, {lon} vs campus {lat0}, {lon0}. EXIF can be edited or removed, so this needs human verification."))
        taken = r.ev.value(d.id, "taken_at")
        sub = r.ctx.get("submission_date")
        if taken and sub and (taken[:10] > sub or taken[:4] < str(int(sub[:4]) - 3)):
            flags.append(make_flag("compliance", "METADATA_ANOMALY", "MINOR", f"Photo {d.filename} has an implausible capture time ({taken[:10]}) for a submission on {sub}",
                                   [r.ev.field(d.id, "taken_at")], forensic=True, confidence=0.5, document_id=d.id))
    return flags


def _footprint_checks(r: Run) -> list[dict]:
    inst = r.db.get(Institution, r.app.institution_id)
    res = sources.geo_footprints(f"{inst.slug}-main")
    if not res.available or not res.body.get("features"):
        return []
    feats = res.body["features"]
    geo = {"system_source": res.source, "record_id": f"{inst.slug}-main", "mock": True}
    flags, f = [], r.ctx["facts"]
    declared = r.ctx.get("declared_built_up_total_m2")
    expected = sum(x["properties"]["area_m2"] * x["properties"]["floors"] for x in feats)
    if declared and expected:
        dev = abs(declared - expected) / expected
        limit = r.thresholds.get("builtup_deviation", 0.15)
        if dev > limit:
            floors = {x["properties"]["floors"] for x in feats}
            foot = sum(x["properties"]["area_m2"] for x in feats)
            how = f"footprint {foot:,.0f} sq m x {floors.pop()} floors" if len(floors) == 1 else "sum of footprint x floors per building"
            flags.append(make_flag("compliance", "BUILTUP_AREA_IMPLAUSIBLE", "MAJOR",
                                   f"Declared built-up area {declared:,.0f} sq m vs {expected:,.0f} sq m expected from building footprints ({how}); deviation {dev:.1%} exceeds {limit:.0%}",
                                   [form_source(r, "application.declared_built_up_total_m2"), geo],
                                   explanation="Footprint area is read from the (mock) building-footprint dataset and multiplied by declared floors.", key="area"))
    start = res.body.get("imagery_start_year", 0)
    for x in feats:
        name, first = x["properties"]["building"], x["properties"]["first_seen_year"]
        b = f.get(f"building:{name}")
        if not b:
            continue
        year = date.fromisoformat(b["completion_date"]).year
        if year >= start and first > year + 1:
            oc = next((d for d in r.ev.of_type("OCCUPANCY_CERTIFICATE") if r.ev.value(d.id, "building_name") == name), None)
            ev = ([r.ev.field(oc.id, "completion_date")] if oc else [form_source(r, f"building:{name}")]) + [dict(geo, building=name, first_seen_year=first)]
            flags.append(make_flag("compliance", "BUILDING_NOT_VISIBLE_ON_DATE", "MAJOR",
                                   f"{name}: completion certificate dated {year} but the building first appears in satellite imagery in {first}", ev, document_id=oc.id if oc else None,
                                   explanation=f"Imagery dataset starts in {start}; buildings completed in {year} should be visible by {year + 1}.", forensic=True, confidence=0.8, key=name))
    return flags


def run(r: Run) -> list[dict]:
    return _photo_checks(r) + _footprint_checks(r)
