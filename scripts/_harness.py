"""Shared setup for verify_planted.py and evaluate.py: fresh SQLite DB + freshly generated synthetic data + full pipeline run."""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build_world(live_mock: str | None = None, keep_db: str | None = None) -> dict:
    """Returns dict(db_factory, apps, expected, manifest, data_dir, timings). Must be called before any `app.*` import."""
    tmp = Path(tempfile.mkdtemp(prefix="pramaan-run-"))
    os.environ["DATABASE_URL"] = f"sqlite:///{Path(keep_db) if keep_db else tmp / 'run.db'}"
    os.environ["STORAGE_DIR"] = str(tmp / "storage")
    data = tmp / "synthetic"
    subprocess.run([sys.executable, str(ROOT / "scripts/generate_synthetic.py"), "--out", str(data), "--expected", str(tmp / "expected.json")], check=True, capture_output=True)
    os.environ["TRUST_ROOT_PATH"] = str(data / "pki/ca.pem")
    os.environ["MOCK_DB"] = str(data / "mock_db.json")
    for p in (ROOT / "backend", ROOT / "mock_issuers"):
        sys.path.insert(0, str(p))

    from app.adapters import base
    from app.core.db import Base, SessionLocal, engine
    import app.models  # noqa: F401
    from app.services.demo_seed import seed_users
    from app.services.pipeline import run_pipeline
    from app.services.rules import loader, store
    from app.services.synthetic_loader import load_synthetic
    from sqlalchemy import select
    from app.models import Application

    if live_mock:
        from app.core.config import settings
        settings.mock_issuers_url = live_mock
    else:
        from fastapi.testclient import TestClient
        import main as mock_app
        base.set_client_factory(lambda: TestClient(mock_app.app))

    Base.metadata.create_all(engine)
    timings = {}
    with SessionLocal() as db:
        seed_users(db)
        apps = load_synthetic(db, data)
        store.create_draft(db, loader.load_dir(loader.RULEPACK_DIR / "APH-2024-27-v1"), None, status="active")
        for a in db.scalars(select(Application).order_by(Application.academic_year, Application.id)).all():
            t = time.perf_counter()
            run_pipeline(db, a)
            timings[a.id] = time.perf_counter() - t
    return dict(db_factory=SessionLocal, apps=apps, expected=json.loads((tmp / "expected.json").read_text()), manifest=json.loads((data / "manifest.json").read_text()),
                data_dir=data, timings=timings)
