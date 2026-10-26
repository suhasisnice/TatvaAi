"""Retention policy (DPDP Act 2023 principle: storage limitation). Lists documents past retention; never deletes automatically."""
from datetime import date

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document
from app.services.rules.loader import RULEPACK_DIR


def due(db: Session, today: date | None = None) -> list[dict]:
    today = today or date.today()
    cfg = yaml.safe_load((RULEPACK_DIR / "config/retention.yaml").read_text())
    out = []
    for d in db.scalars(select(Document)):
        years = cfg["document_types"].get(d.doc_type, cfg["default_years"])
        expires = d.uploaded_at.date().replace(year=d.uploaded_at.year + years)
        if expires <= today:
            out.append(dict(document_id=d.id, doc_type=d.doc_type, uploaded_at=d.uploaded_at.date().isoformat(), retention_years=years, due_since=expires.isoformat()))
    return out
