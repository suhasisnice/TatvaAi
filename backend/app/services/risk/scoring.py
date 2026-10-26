"""Risk scoring and tiering. GREEN = no risk, AMBER = medium risk, RED = high risk. Dismissed flags do not count (but are never deleted)."""
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Flag
from app.services.rules import loader
from app.services.rules import store

TIER_LABEL = {"GREEN": "No risk", "AMBER": "Medium risk", "RED": "High risk"}
TIER_RANK = {"RED": 2, "AMBER": 1, "GREEN": 0}
ROUTING = {"GREEN": "FAST_TRACK", "AMBER": "FIX_LIST", "RED": "INSPECTION_LIST"}
ROUTING_TEXT = {"FAST_TRACK": "Fast-track: officer confirms", "FIX_LIST": "Fix-list sent to the institution with a rectification window",
                "INSPECTION_LIST": "Added to the ranked inspection list"}
DEFAULT = dict(weights={"CRITICAL": 40, "MAJOR": 15, "MINOR": 5, "INFO": 0}, tiers={"RED": {"any_severity": "CRITICAL", "min_score": 60}, "AMBER": {"any_severity": "MAJOR", "min_score": 20}})


def contribution(flag, weights: dict) -> float:
    w = weights.get(flag.severity, 0)
    return round(w * (flag.confidence if flag.forensic else 1.0), 2)  # forensic indicators count weight x confidence


def tier_for(flags: list, risk_cfg: dict) -> tuple[str, float, list[dict]]:
    cfg = {**DEFAULT, **(risk_cfg or {})}
    live = [f for f in flags if f.status != "DISMISSED"]
    rows = sorted(({"code": f.code, "severity": f.severity, "message": f.message, "contribution": contribution(f, cfg["weights"]), "flag_id": f.id, "forensic": f.forensic}
                   for f in live), key=lambda x: (-x["contribution"], x["code"]))
    score = round(sum(x["contribution"] for x in rows), 2)
    sevs = {f.severity for f in live}
    t = cfg["tiers"]
    tier = "RED" if (t["RED"]["any_severity"] in sevs or score >= t["RED"]["min_score"]) else "AMBER" if (t["AMBER"]["any_severity"] in sevs or score >= t["AMBER"]["min_score"]) else "GREEN"
    return tier, score, [x for x in rows if x["severity"] != "INFO"][:6]


def pack_for(db: Session, app: Application) -> tuple[str, dict]:
    if app.rule_pack_version:
        row = store.get(db, app.rule_pack_version)
        if row:
            return row.version, loader.parse(row.yaml_blob)
    return store.active(db)


def score_application(db: Session, app: Application) -> dict:
    version, pack = pack_for(db, app)
    flags = list(db.scalars(select(Flag).where(Flag.application_id == app.id)))
    tier, score, reasons = tier_for(flags, pack.get("risk"))
    app.risk_tier, app.risk_score, app.rule_pack_version = tier, score, version
    app.risk_reasons, app.scored_at = json.dumps(reasons), datetime.now(timezone.utc).replace(tzinfo=None)
    db.flush()
    return risk_summary(app)


def risk_summary(app: Application) -> dict:
    tier = app.risk_tier
    return dict(application_id=app.id, tier=tier, tier_label=TIER_LABEL.get(tier), score=app.risk_score, routing=ROUTING.get(tier), routing_text=ROUTING_TEXT.get(ROUTING.get(tier)),
                reasons=json.loads(app.risk_reasons) if app.risk_reasons else [], rule_pack_version=app.rule_pack_version)
