"""Compliance: Rule Pack formula/threshold rules (faculty ratio with relief, cadre, rooms, areas, PCs, bandwidth).
Output per rule is PASS / FAIL / INSUFFICIENT_EVIDENCE with inputs, computed values and citation (stored as rule_results);
only FAIL becomes a flag. Infrastructure *evidence* checks (photos, footprints, imagery) live in infrastructure.py."""
from app.services.engines import completeness
from app.services.engines.common import Run, flag_from_result, form_source


def handles(rule: dict, res: dict) -> bool:
    return rule["type"] in ("formula", "threshold") and not completeness.handles(rule, res) and res.get("code") != "ACCREDITATION_CLAIM_UNVERIFIED"


def run(r: Run) -> list[dict]:
    flags = []
    inst = r.ctx["facts"]["institution"]
    for res in r.results:
        rule = r.rules[res["rule_id"]]
        if res["status"] != "FAIL" or not handles(rule, res):
            continue
        ev = [form_source(r, "application:" + str(r.app.id))]
        doc_id = None
        if rule["id"].startswith("FAC-"):
            fl = r.ev.of_type("FACULTY_LIST")
            doc_id = fl[0].id if fl else None
            ev = ([r.ev.doc(doc_id)] if doc_id else []) + [{"system_source": "AICTE faculty registry (MOCK)", "record_id": inst["aicte_id"], "mock": True}, ev[0]]
        flags.append(flag_from_result("compliance", res, r, ev, document_id=doc_id))
    return flags
