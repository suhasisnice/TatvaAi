from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.feature_flags import enabled
from app.core.security import current_user, require_roles
from app.models import RulePack, User
from app.services.audit import hash_chain as audit
from app.services.rules import dry_run as dry, loader, store

router = APIRouter(prefix="/rulepacks", tags=["rules"])


class PackIn(BaseModel):
    yaml: str | None = None
    from_dir: str | None = None  # e.g. APH-2024-27-v2-demo (a pack folder under rulepacks/)


def _row(db: Session, version: str) -> RulePack:
    r = db.scalar(select(RulePack).where(RulePack.version == version))
    if not r:
        raise HTTPException(404, "Rule pack not found")
    return r


def _summary(r: RulePack) -> dict:
    return dict(version=r.version, status=r.status, effective_from=r.effective_from, created_at=r.created_at.isoformat(), rule_count=len(loader.parse(r.yaml_blob)["rules"]))


@router.get("")
def list_packs(user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    return [_summary(r) for r in db.scalars(select(RulePack).order_by(RulePack.id))]


@router.get("/{version}")
def get_pack(version: str, user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    r = _row(db, version)
    return dict(**_summary(r), yaml=r.yaml_blob)


@router.post("", status_code=201)
def create_pack(body: PackIn, user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    if body.from_dir:
        d = (loader.RULEPACK_DIR / body.from_dir).resolve()
        if loader.RULEPACK_DIR.resolve() not in d.parents or not d.is_dir():
            raise HTTPException(422, "Unknown rule pack folder")
        pack = loader.load_dir(d)
    elif body.yaml:
        try:
            pack = loader.parse(body.yaml)
        except Exception as e:
            raise HTTPException(422, {"errors": [f"YAML parse error: {e}"]})
    else:
        raise HTTPException(422, "Provide yaml or from_dir")
    errors = loader.validate_pack(pack)
    if errors:
        raise HTTPException(422, {"errors": errors})
    if db.scalar(select(RulePack).where(RulePack.version == pack["version"])):
        raise HTTPException(409, "Version already exists; packs are immutable once created")
    row = store.create_draft(db, pack, user.id)
    audit.log(db, user, "rulepack.create", f"rulepack:{row.version}", {"version": row.version, "rules": len(pack["rules"])})
    db.commit()
    return _summary(row)


class YamlIn(BaseModel):
    yaml: str


@router.post("/validate-yaml")
def validate_yaml(body: YamlIn, user: User = Depends(require_roles("officer"))):
    """Inline validation for the officer editor: nothing is stored."""
    try:
        pack = loader.parse(body.yaml)
    except Exception as e:
        return dict(valid=False, errors=[f"YAML parse error: {e}"])
    if not isinstance(pack, dict):
        return dict(valid=False, errors=["The pack must be a YAML mapping"])
    errors = loader.validate_pack(pack)
    return dict(valid=not errors, errors=errors)


@router.post("/{version}/validate")
def validate(version: str, user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    errors = loader.validate_pack(loader.parse(_row(db, version).yaml_blob))
    audit.log(db, user, "rulepack.validate", f"rulepack:{version}", {"version": version, "valid": not errors, "errors": len(errors)})
    db.commit()
    return dict(valid=not errors, errors=errors)


@router.post("/{version}/dry-run")
def dry_run(version: str, user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    """What would change if this pack were active? Nothing is written except an audit entry."""
    r = _row(db, version)
    result = dry.dry_run(db, loader.parse(r.yaml_blob), version)
    audit.log(db, user, "rulepack.dry_run", f"rulepack:{version}", {"version": version, "applications_changed": result["applications_changed"], "tier_changes": result["tier_changes"]})
    db.commit()
    return result


@router.post("/{version}/activate")
def activate(version: str, user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    r = _row(db, version)
    errors = loader.validate_pack(loader.parse(r.yaml_blob))
    if errors:
        raise HTTPException(422, {"errors": errors})
    if r.status == "active":
        raise HTTPException(409, "Already active")
    row = store.activate(db, version, user.id)
    audit.log(db, user, "rulepack.activate", f"rulepack:{version}", {"version": version, "effective_from": row.effective_from})
    db.commit()
    return _summary(row)


class TextIn(BaseModel):
    text: str


@router.post("/draft-from-text")
def draft_from_text(body: TextIn, user: User = Depends(require_roles("officer")), db: Session = Depends(get_db)):
    """FEATURE_LLM: a local LLM drafts YAML from pasted Handbook text. Returned for review only; it stays a draft until an officer saves and activates it."""
    if not enabled("llm"):
        raise HTTPException(501, "FEATURE_LLM is off")
    from app.services.optional import draft_rules_from_text

    try:
        text = draft_rules_from_text(body.text)
    except Exception as e:
        raise HTTPException(502, f"The local LLM could not be reached: {e}")
    audit.log(db, user, "rulepack.llm_draft", "rulepack:draft", {"chars_in": len(body.text), "chars_out": len(text)})
    db.commit()
    return dict(draft_yaml=text, status="UNREVIEWED_DRAFT", note="Review, validate and save as a new draft; nothing has been stored.")
