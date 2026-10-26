import json
import sys
from pathlib import Path

import yaml
from fastapi.testclient import TestClient
from jsonschema import validate

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402

c = TestClient(app)


def login(email="officer@pramaan.test"):
    r = c.post("/api/v1/auth/login", json={"email": email, "password": "Pramaan@2026"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_19_tables():
    assert len(Base.metadata.tables) == 19


def test_rule_pack_matches_schema():
    schema = json.loads((ROOT / "rulepacks/schema.json").read_text())
    validate(yaml.safe_load((ROOT / "rulepacks/APH-2024-27-v1/norms.yaml").read_text()), schema)


def test_queue_red_first_and_tiers():
    apps = c.get("/api/v1/applications", headers=login()).json()
    assert [a["risk"]["tier"] for a in apps] == ["RED", "AMBER", "GREEN"]


def test_institution_sees_only_own():
    h = login("inst-a@pramaan.test")
    assert [a["id"] for a in c.get("/api/v1/applications", headers=h).json()] == [1]
    assert c.get("/api/v1/applications/3", headers=h).status_code == 404


def test_decision_needs_reason():
    h = login()
    assert c.post("/api/v1/flags/3/decision", json={"decision": "DISMISS", "reason": ""}, headers=h).status_code == 422
    assert c.post("/api/v1/flags/3/decision", json={"decision": "DISMISS", "reason": "checked"}, headers=h).status_code == 200


def test_no_reject_route_and_committed_openapi_is_current():
    spec = app.openapi()
    assert not any("reject" in p for p in spec["paths"])
    assert json.loads((ROOT / "contracts/openapi.json").read_text()) == spec, "run backend/scripts/export_openapi.py"
