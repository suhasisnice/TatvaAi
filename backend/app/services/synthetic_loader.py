"""Loads the generated synthetic institutions/applications/documents into the database via the normal ingestion path."""
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Campus, Institution
from app.services.ingestion.upload import ingest

PREV, CUR = "2026-27", "2027-28"


def load_synthetic(db: Session, data_dir: Path, status_current: str = "SUBMITTED", drafts: tuple = ()) -> dict[tuple[str, str], Application]:
    """drafts: institution keys whose current-year application stays an editable DRAFT (for the pre-check demo)."""
    apps = {}
    for key in "abc":
        inst = db.scalar(select(Institution).where(Institution.slug == f"inst-{key}"))
        for ay in (PREV, CUR):
            base = data_dir / key / ay
            if not base.exists():
                continue
            form = json.loads((base / "application.json").read_text())
            if not db.scalar(select(Campus).where(Campus.institution_id == inst.id)):
                i = form["institution"]
                db.add(Campus(institution_id=inst.id, address=i["address"], state=i["state"], lat=i["lat"], lon=i["lon"]))
            draft = ay == CUR and key in drafts
            app = Application(institution_id=inst.id, category="EOA", academic_year=ay, form_data=json.dumps(form),
                              status="DRAFT" if draft else ("SUBMITTED" if ay == PREV else status_current), locked=not draft,
                              submitted_at=None if draft else (datetime(int(ay[:4]), 3, 1) if ay == PREV else datetime(2027, 3, 1)))
            db.add(app)
            db.flush()
            for f in sorted((base / "docs").glob("*.pdf")) + sorted((base / "photos").glob("*.jpg")) + [base / "faculty.csv"]:
                ingest(db, app, f.name, f.read_bytes(), None)
            apps[key, ay] = app
    db.commit()
    return apps
