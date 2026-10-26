import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

_run = subprocess.run


def _run_showing_stderr(*args, **kwargs):
    """The fixtures run scripts/generate_synthetic.py with capture_output=True, so a failure would only say 'CalledProcessError'.
    Put the child's stderr in the pytest report instead. ponytail: patches subprocess.run for the whole session; fine while the only check=True callers are those fixtures."""
    try:
        return _run(*args, **kwargs)
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        sys.stderr.write(f"\n--- exit {e.returncode} from {e.cmd}; stderr (last 4000 characters) ---\n{err[-4000:]}\n")
        raise


subprocess.run = _run_showing_stderr

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.demo_seed import DEMO_PASSWORD, seed_users  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_users(db)
    return TestClient(app)


@pytest.fixture()
def login(client):
    def _login(email: str) -> dict:
        r = client.post("/api/v1/auth/login", json={"email": email, "password": DEMO_PASSWORD})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _login
