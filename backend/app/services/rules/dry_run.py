"""Dry-run a draft rule pack against all existing applications and report what would change: tier, flags appearing/disappearing.
Nothing is written. Rule-derived flags are recomputed with the draft pack; everything else (forensics, issuer, cross-checks) is kept as is."""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Flag, Institution
from app.services.engines import completeness, compliance, consistency
from app.services.engines.common import Evidence, Run, flag_from_result
from app.services.risk.scoring import tier_for
from app.services.rules import evaluator
from app.services.rules.context import build_context


class _F:  # minimal flag-like object for tiering
    def __init__(self, spec=None, row=None):
        s = spec or {k: getattr(row, k) for k in ("code", "severity", "message", "confidence", "forensic", "fingerprint", "status", "id")}
        self.code, self.severity, self.message, self.confidence = s["code"], s["severity"], s["message"], s["confidence"]
        self.forensic, self.fingerprint = s["forensic"], s["fingerprint"]
        self.status, self.id = s.get("status", "OPEN"), s.get("id")


def dry_run(db: Session, draft: dict, version: str) -> dict:
    changes, unchanged = [], 0
    for app in db.scalars(select(Application).order_by(Application.id)):
        flags = list(db.scalars(select(Flag).where(Flag.application_id == app.id)))
        if not flags and not app.risk_tier:
            continue
        ctx = build_context(db, app, draft)
        results = evaluator.evaluate_pack(draft, ctx)
        run = Run(db=db, app=app, pack=draft, version=version, ctx=ctx, results=results, ev=Evidence(db, app), rules={x["id"]: x for x in draft["rules"]})
        new_rule_specs = completeness.run(run) + consistency._rule_flags(run) + compliance.run(run)
        for res in results:  # accreditation eligibility is evaluated in the issuer engine
            if res["code"] == "ACCREDITATION_CLAIM_UNVERIFIED" and res["status"] == "FAIL":
                new_rule_specs.append(flag_from_result("issuer", res, run, []))
        kept = [f for f in flags if f.rule_id is None]
        # keep officer decisions on flags that persist
        old_status = {f.fingerprint: f.status for f in flags}
        hypo = [_F(row=f) for f in kept] + [_F(spec={**s, "status": old_status.get(s["fingerprint"], "OPEN")}) for s in new_rule_specs]
        tier, score, _ = tier_for(hypo, draft.get("risk"))
        old_rule = {f.fingerprint: f for f in flags if f.rule_id is not None}
        new_rule = {s["fingerprint"]: s for s in new_rule_specs}
        added = [dict(code=s["code"], rule_id=s["rule_id"], message=s["message"], severity=s["severity"]) for fp, s in new_rule.items() if fp not in old_rule]
        removed = [dict(code=f.code, rule_id=f.rule_id, message=f.message, severity=f.severity) for fp, f in old_rule.items() if fp not in new_rule]
        reworded = [dict(code=s["code"], rule_id=s["rule_id"], before=old_rule[fp].message, after=s["message"]) for fp, s in new_rule.items()
                    if fp in old_rule and old_rule[fp].message != s["message"]]
        if tier != app.risk_tier or added or removed or reworded:
            inst = db.get(Institution, app.institution_id)
            changes.append(dict(application_id=app.id, institution_name=inst.name, academic_year=app.academic_year, tier_before=app.risk_tier, tier_after=tier,
                                score_before=app.risk_score, score_after=score, tier_changed=tier != app.risk_tier, flags_added=added, flags_removed=removed, flags_reworded=reworded))
        else:
            unchanged += 1
    return dict(draft_version=version, applications_changed=len(changes), applications_unchanged=unchanged, tier_changes=sum(c["tier_changed"] for c in changes), changes=changes)
