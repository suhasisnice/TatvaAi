"""Completeness: required documents/fields present, DSC-signed, valid on the academic-year start date, provisional OC limit.
Driven entirely by Rule Pack rules (document_required / field_required / expiry types)."""
from app.services.engines.common import Run, flag_from_result

CODES = {"DOC_MISSING", "FIELD_MISSING", "DOC_UNSIGNED", "DOC_EXPIRED", "DOC_EXPIRES_BEFORE_AY", "PROVISIONAL_OC_LIMIT_EXCEEDED"}


def handles(rule: dict, res: dict) -> bool:
    return rule["type"] in ("document_required", "field_required", "expiry") or res.get("code") == "PROVISIONAL_OC_LIMIT_EXCEEDED"


def run(r: Run) -> list[dict]:
    flags = []
    for res in r.results:
        rule = r.rules[res["rule_id"]]
        if res["status"] != "FAIL" or not handles(rule, res):
            continue
        t, d = rule["type"], res["details"]
        if t == "document_required":
            code, doc_id = d["code"], d.get("document_id")
            ev = [r.ev.doc(doc_id)] if doc_id else [{"system_source": f"Rule Pack {r.version}", "record_id": rule["id"]}]
            flags.append(flag_from_result("completeness", res, r, ev, code=code, document_id=doc_id, key=rule["document_type"]))
        elif t == "field_required":
            doc_id = d.get("document_id")
            flags.append(flag_from_result("completeness", res, r, [r.ev.field(doc_id, m) for m in d["missing"]] or [r.ev.doc(doc_id)], document_id=doc_id))
        elif t == "expiry":
            doc_id = d["document_id"]
            flags.append(flag_from_result("completeness", res, r, [r.ev.field(doc_id, rule["field"])], document_id=doc_id, key=rule["id"]))
        else:  # provisional occupancy certificate used beyond 2 consecutive academic years
            prov = [x for x in r.ev.of_type("OCCUPANCY_CERTIFICATE") if r.ev.value(x.id, "certificate_type") == "PROVISIONAL"]
            ev = [r.ev.field(x.id, n) for x in prov for n in ("certificate_type", "building_name")]
            ev.append({"system_source": "AICTE records (MOCK)", "record_id": r.ctx["facts"]["institution"]["aicte_id"], "field": "provisional_oc_history", "mock": True})
            flags.append(flag_from_result("completeness", res, r, ev, document_id=prov[0].id if prov else None))
    return flags
