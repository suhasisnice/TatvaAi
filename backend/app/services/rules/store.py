from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RulePack
from app.services.rules import loader


def create_draft(db: Session, pack: dict, user_id: int | None, status: str = "draft") -> RulePack:
    row = RulePack(version=pack["version"], status=status, effective_from=pack.get("effective_from"), yaml_blob=loader.dump(pack),
                   created_by=user_id, created_at=datetime.now(timezone.utc).replace(tzinfo=None))
    db.add(row)
    db.commit()
    return row


def import_dir(db: Session, name: str, user_id: int | None = None, status: str = "draft") -> RulePack:
    pack = loader.load_dir(loader.RULEPACK_DIR / name)
    return create_draft(db, pack, user_id, status)


def get(db: Session, version: str) -> RulePack | None:
    return db.scalar(select(RulePack).where(RulePack.version == version))


def active(db: Session) -> tuple[str, dict]:
    row = db.scalar(select(RulePack).where(RulePack.status == "active"))
    if not row:
        raise LookupError("No active rule pack")
    return row.version, loader.parse(row.yaml_blob)


def activate(db: Session, version: str, user_id: int) -> RulePack:
    row = db.scalar(select(RulePack).where(RulePack.version == version))
    for old in db.scalars(select(RulePack).where(RulePack.status == "active")):
        old.status = "retired"  # exactly one active pack; retired packs stay readable so old results keep their version
    row.status, row.approved_by = "active", user_id
    db.commit()
    return row
