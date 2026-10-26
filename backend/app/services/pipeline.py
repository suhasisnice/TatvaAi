"""Full validation pipeline for one application. Order = proof before prediction:
carry-forward -> facts -> rules -> issuer verification -> authenticity (cryptographic, then forensics) -> completeness -> consistency -> compliance -> scoring."""
import json
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Application, Flag, FlagDecision, RuleResult
from app.services.alerts.generate import alerts_from_flags
from app.services.audit import hash_chain as audit
from app.services.engines import authenticity, completeness, compliance, consistency, infrastructure, issuer
from app.services.engines.common import Evidence, Run
from app.services.evidence.carry_forward import carry_forward
from app.services.evidence.graph import build_facts
from app.services.risk.scoring import risk_summary, score_application
from app.services.rules import evaluator, store
from app.services.rules.context import build_context


def _save_rule_results(db: Session, app: Application, version: str, results: list[dict], now) -> None:
    db.execute(delete(RuleResult).where(RuleResult.application_id == app.id))
    for x in results:
        db.add(RuleResult(application_id=app.id, rule_id=x["rule_id"], rule_pack_version=version, scope=x["scope"], status=x["status"],
                          result_json=json.dumps(x, default=str), evaluated_at=now))


def _save_flags(db: Session, app: Application, specs: list[dict], now) -> list[Flag]:
    """Upsert by fingerprint so officer decisions (status) survive a re-run; flags that no longer apply are removed."""
    existing = {f.fingerprint: f for f in db.scalars(select(Flag).where(Flag.application_id == app.id))}
    seen, out = {}, []
    for s in specs:
        fp = s["fingerprint"]
        seen[fp] = seen.get(fp, 0) + 1
        if seen[fp] > 1:
            fp = s["fingerprint"] = f"{fp}#{seen[fp]}"
        row = existing.pop(fp, None) or Flag(application_id=app.id, fingerprint=fp, status="OPEN", created_at=now)
        for k in ("engine", "code", "severity", "confidence", "message", "explanation", "rule_id", "rule_pack_version", "document_id", "forensic"):
            setattr(row, k, s[k])
        row.evidence, row.citation = json.dumps(s["evidence"], default=str), json.dumps(s["citation"]) if s["citation"] else None
        db.add(row)
        out.append(row)
    for stale in existing.values():
        db.execute(delete(FlagDecision).where(FlagDecision.flag_id == stale.id))
        db.delete(stale)
    db.flush()
    return out


def run_pipeline(db: Session, app: Application, actor=None) -> dict:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    version, pack = store.active(db)
    carry_forward(db, app)
    build_facts(db, app)
    ctx = build_context(db, app, pack)
    results = evaluator.evaluate_pack(pack, ctx)
    _save_rule_results(db, app, version, results, now)
    run = Run(db=db, app=app, pack=pack, version=version, ctx=ctx, results=results, ev=Evidence(db, app), rules={x["id"]: x for x in pack["rules"]})
    app.rule_pack_version = version
    specs = []
    for engine in (issuer, authenticity, completeness, consistency, compliance, infrastructure):  # fixed order; later engines read earlier verifications
        out = engine.run(run)
        audit.log(db, actor, "engine.run", f"application:{app.id}", {"engine": engine.__name__.rsplit(".", 1)[-1], "flags": len(out), "rule_pack_version": version})
        specs += out
    for v in run.verifs:
        audit.log(db, actor, "verification.call", f"application:{app.id}", {k: v[k] for k in ("document_id", "adapter", "status", "source")})
    flags = _save_flags(db, app, specs, now)
    alerts_from_flags(db, app)
    summary = score_application(db, app)
    audit.log(db, actor, "risk.score", f"application:{app.id}", {"tier": summary["tier"], "score": summary["score"], "rule_pack_version": version})
    db.commit()
    return dict(application_id=app.id, rule_pack_version=version, flags=len(flags), verifications=len(run.verifs), tier=summary["tier"], score=summary["score"],
                rule_results={s: sum(x["status"] == s for x in results) for s in ("PASS", "FAIL", "INSUFFICIENT_EVIDENCE")})


def run_all(db: Session, actor=None) -> list[dict]:
    """Oldest academic year first, so last year's verified documents can be carried forward."""
    apps = db.scalars(select(Application).order_by(Application.academic_year, Application.id)).all()
    return [run_pipeline(db, a, actor) for a in apps]
