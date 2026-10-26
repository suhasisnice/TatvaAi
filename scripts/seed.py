"""Seed demo users, rule packs, synthetic institutions/applications/documents, and run the full pipeline on every application.

Usage: python scripts/seed.py [--reset] [--inprocess-mock]
  --reset            regenerate synthetic data and recreate all tables
  --inprocess-mock   call the mock issuers in-process (no mock-issuers service needed; for running without Docker)"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.core.db import Base, SessionLocal, engine  # noqa: E402
import app.models  # noqa: E402,F401
from app.models import Application, RulePack  # noqa: E402
from app.services.demo_seed import seed_users  # noqa: E402
from app.services.pipeline import run_all  # noqa: E402
from app.services.rules import store  # noqa: E402
from app.services.synthetic_loader import load_synthetic  # noqa: E402

if __name__ == "__main__":
    data = ROOT / "data/synthetic"
    if "--reset" in sys.argv or not (data / "manifest.json").exists():
        subprocess.run([sys.executable, str(ROOT / "scripts/generate_synthetic.py")], check=True)
    if "--inprocess-mock" in sys.argv:
        import os
        os.environ["MOCK_DB"] = str(data / "mock_db.json")
        sys.path.insert(0, str(ROOT / "mock_issuers"))
        import main as mock_app
        from fastapi.testclient import TestClient
        from app.adapters import base
        base.set_client_factory(lambda: TestClient(mock_app.app))
    if "--reset" in sys.argv:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)  # no-op when alembic already created the schema
    settings.trust_root_path = str(data / "pki/ca.pem")
    with SessionLocal() as db:
        for role, email, pw in seed_users(db):
            print(f"{role:12} {email:28} {pw}")
        if not db.query(RulePack).count():
            store.import_dir(db, "APH-2024-27-v1", status="active")
            store.import_dir(db, "APH-2024-27-v2-demo")  # draft, for the versioning demo
            print("rule packs: v1 active, v2-demo draft")
        if not db.query(Application).count():
            apps = load_synthetic(db, data, drafts=("b",))  # B stays an editable draft for the pre-check demo
            print(f"loaded {len(apps)} applications and their documents")
            for s in run_all(db):
                print(f"  application {s['application_id']}: {s['tier']} (score {s['score']}), {s['flags']} flags, {s['verifications']} verification rows")
