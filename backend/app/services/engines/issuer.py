"""Issuer verification: ask the original issuing source (MOCK adapters) and record one of the six statuses per check.
SOURCE_UNAVAILABLE is automatically routed to MANUAL_REVIEW_REQUIRED (a second row) so an officer can confirm by hand."""
import hashlib
import json
import re
from datetime import datetime, timezone

from sqlalchemy import delete

from app.adapters import accreditation_lists, aicte_records, sources
from app.models import Verification
from app.services.engines.common import Run, flag_from_result, form_source, make_flag
from app.services.rules.evaluator import normalise

ISO = re.compile(r"\d{4}-\d{2}-\d{2}$")


def _num(v):
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def _same(a, b) -> bool:
    na, nb = _num(a), _num(b)
    if na is not None and nb is not None:
        return na == nb
    return normalise(a) == normalise(b)


def _compare(pairs: list[tuple[str, object, object]]) -> list[dict]:
    """pairs: (field, printed, issuer). Returns mismatches."""
    return [dict(field=f, printed=p, issuer=i) for f, p, i in pairs if not _same(p, i)]


def _status(res, mismatches: list[dict], expired_on: str | None) -> tuple[str, str]:
    if not res.available:
        return "SOURCE_UNAVAILABLE", f"{res.source} unavailable (HTTP {res.http_status or 'no response'})"
    if res.http_status == 404:
        return "MISMATCH_DETECTED", "Not found at the issuing source"
    if (res.body or {}).get("status") == "PENDING":
        return "VERIFICATION_PENDING", "Issuer has not answered yet"
    if mismatches:
        return "MISMATCH_DETECTED", "; ".join(f"{m['field']}: document {m['printed']!r} vs issuer {m['issuer']!r}" for m in mismatches)
    if expired_on and ISO.match(expired_on):
        return "EXPIRED", f"Issuer record valid only till {expired_on}"
    return "VERIFIED", "All checked fields match the issuer record"


def _expired(valid_till, today) -> str | None:
    return valid_till if isinstance(valid_till, str) and ISO.match(valid_till) and valid_till < today else None


def run(r: Run) -> list[dict]:
    flags, now = [], datetime.now(timezone.utc).replace(tzinfo=None)
    r.db.execute(delete(Verification).where(Verification.application_id == r.app.id, Verification.carried_forward_from.is_(None), Verification.manual_by.is_(None)))
    today = r.ctx.get("submission_date") or r.today.isoformat()
    state = r.ctx["facts"]["institution"]["state"]
    done_docs = {v.document_id for v in r.db.query(Verification).filter_by(application_id=r.app.id, status="VERIFIED").all() if v.carried_forward_from}

    def record(doc, adapter, res, mismatches, expired_on=None, record_ref=""):
        status, summary = _status(res, mismatches, expired_on)
        r.db.add(Verification(application_id=r.app.id, document_id=doc.id if doc else None, adapter=adapter, status=status, source=res.source,
                              request_hash=res.request_hash, response_hash=res.response_hash, response_summary=summary, checked_at=now))
        r.verifs.append(dict(document_id=doc.id if doc else None, adapter=adapter, status=status, source=res.source, summary=summary))
        did, ev_doc = (doc.id if doc else None), ([r.ev.doc(doc.id)] if doc else [])
        sys_ev = {"system_source": res.source, "record_id": record_ref, "mock": True}
        if status == "SOURCE_UNAVAILABLE":
            r.db.add(Verification(application_id=r.app.id, document_id=did, adapter=adapter, status="MANUAL_REVIEW_REQUIRED", source=res.source,
                                  response_summary="Source unavailable: an officer must confirm this document manually", checked_at=now))
            r.verifs.append(dict(document_id=did, adapter=adapter, status="MANUAL_REVIEW_REQUIRED", source=res.source, summary="auto-routed"))
            flags.append(make_flag("issuer", "ISSUER_UNAVAILABLE", "INFO", f"{res.source} could not be reached; manual confirmation required", ev_doc + [sys_ev],
                                   explanation="Routed to MANUAL_REVIEW_REQUIRED. This does not change the risk tier.", document_id=did, key=adapter))
        elif status == "MISMATCH_DETECTED":
            evid = [r.ev.field(did, m["field"]) for m in mismatches if did and r.ev._fields.get((did, m["field"]))] or ev_doc
            flags.append(make_flag("issuer", "ISSUER_MISMATCH", "MAJOR", f"{res.source}: {summary}", evid + [sys_ev],
                                   explanation="The issuing authority's record disagrees with the uploaded document.", document_id=did, key=adapter))
        elif status == "EXPIRED":
            flags.append(make_flag("issuer", "ISSUER_EXPIRED", "MAJOR", f"{res.source}: {summary}", ev_doc + [sys_ev], document_id=did, key=adapter))
        return status

    for d in r.ev.of_type("AFFIDAVIT_2"):
        if d.id in done_docs:
            continue
        res = sources.shcil_estamp(r.ev.value(d.id, "estamp_cert_no") or "")
        rec = res.record or {}
        record(d, "shcil_estamp", res, _compare([("estamp_issue_date", r.ev.value(d.id, "estamp_issue_date"), rec.get("issue_date")),
                                                  ("estamp_value", r.ev.value(d.id, "estamp_value"), rec.get("value")),
                                                  ("state", r.ev.value(d.id, "state"), rec.get("state"))]) if rec else [], record_ref=rec.get("certificate_no", ""))

    for d in r.ev.of_type("LAND_DOCUMENT"):
        if d.id in done_docs:
            continue
        res = sources.digilocker(r.ev.value(d.id, "digilocker_uri") or "")
        rec = res.record or {}
        pairs = [("survey_no", r.ev.value(d.id, "survey_no"), (rec.get("fields") or {}).get("survey_no")),
                 ("owner_name", r.ev.value(d.id, "owner_name"), (rec.get("fields") or {}).get("owner_name")),
                 ("registration_no", r.ev.value(d.id, "registration_no"), (rec.get("fields") or {}).get("registration_no"))]
        mism = _compare(pairs) if rec else []
        if rec and rec.get("original_sha256") != d.sha256:
            mism.append(dict(field="sha256", printed=d.sha256[:12] + "...", issuer=str(rec.get("original_sha256"))[:12] + "..."))
        record(d, "digilocker", res, mism, record_ref=rec.get("uri", ""))

    for d in r.ev.of_type("AUDITED_ACCOUNTS"):
        if d.id in done_docs:
            continue
        res = sources.icai_udin(r.ev.value(d.id, "udin") or "")
        rec = res.record or {}
        record(d, "icai_udin", res, _compare([("ca_name", r.ev.value(d.id, "ca_name"), rec.get("ca_name")), ("entity_name", r.ev.value(d.id, "entity_name"), rec.get("entity")),
                                               ("financial_year", r.ev.value(d.id, "financial_year"), rec.get("financial_year"))]) if rec else [], record_ref=rec.get("udin", ""))

    for d in r.ev.of_type("FIRE_SAFETY_CERTIFICATE"):
        if d.id in done_docs:
            continue
        res = sources.fire_noc(state, r.ev.value(d.id, "certificate_no") or "")
        rec = res.record or {}
        record(d, "fire_noc", res, _compare([("valid_till", r.ev.value(d.id, "valid_till"), rec.get("valid_till")), ("issue_date", r.ev.value(d.id, "issue_date"), rec.get("issue_date"))]) if rec else [],
               _expired(rec.get("valid_till"), today), rec.get("certificate_no", ""))

    for d in r.ev.of_type("OCCUPANCY_CERTIFICATE"):
        if d.id in done_docs:
            continue
        res = sources.occupancy(state, r.ev.value(d.id, "certificate_no") or "")
        rec = res.record or {}
        record(d, "occupancy", res, _compare([("certificate_type", r.ev.value(d.id, "certificate_type"), rec.get("type")), ("issue_date", r.ev.value(d.id, "issue_date"), rec.get("issue_date")),
                                               ("valid_till", r.ev.value(d.id, "valid_till"), rec.get("valid_till")),
                                               ("built_up_area_m2", r.ev.value(d.id, "built_up_area_m2"), rec.get("built_up_area_m2"))]) if rec else [],
               _expired(rec.get("valid_till"), today), rec.get("certificate_no", ""))

    for d in r.ev.of_type("TER_RECEIPT"):
        if d.id in done_docs:
            continue
        res = aicte_records.institution_record(r.ctx["facts"]["institution"]["aicte_id"])
        pay = ((res.record or {}).get("ter_payments") or {}).get(r.app.academic_year)
        mism = _compare([("receipt_no", r.ev.value(d.id, "receipt_no"), (pay or {}).get("receipt_no")), ("amount", r.ev.value(d.id, "amount"), (pay or {}).get("amount"))]) if pay else \
            ([dict(field="receipt_no", printed=r.ev.value(d.id, "receipt_no"), issuer=None)] if res.available else [])
        record(d, "aicte_records", res, mism, record_ref=r.ctx["facts"]["institution"]["aicte_id"])

    for d in r.ev.of_type("STRUCTURAL_STABILITY_CERTIFICATE"):  # no issuing-source adapter exists for structural engineers' registers
        if d.id in done_docs:
            continue
        r.db.add(Verification(application_id=r.app.id, document_id=d.id, adapter="manual", status="MANUAL_REVIEW_REQUIRED", source="No issuer source configured",
                              response_summary="Structural engineer registration cannot be checked automatically", checked_at=now))
        r.verifs.append(dict(document_id=d.id, adapter="manual", status="MANUAL_REVIEW_REQUIRED", source="none", summary="no source"))

    # 3-year EoA accreditation claim: verified through the rule engine, recorded as a verification
    for res in r.results:
        if res["code"] == "ACCREDITATION_CLAIM_UNVERIFIED":
            ok = res["status"] == "PASS"
            src = "NAAC grades (MOCK)"
            r.db.add(Verification(application_id=r.app.id, document_id=None, adapter="accreditation_lists", status="VERIFIED" if ok else "MISMATCH_DETECTED", source=src,
                                  response_summary=res["message"], response_hash=hashlib.sha256(json.dumps(res["inputs"], sort_keys=True, default=str).encode()).hexdigest(), checked_at=now))
            r.verifs.append(dict(document_id=None, adapter="accreditation_lists", status="VERIFIED" if ok else "MISMATCH_DETECTED", source=src, summary=res["message"]))
            if not ok:
                flags.append(flag_from_result("issuer", res, r, [form_source(r, "accreditation_claim"), {"system_source": src, "record_id": "naac", "mock": True}]))
    r.db.commit()
    return flags
