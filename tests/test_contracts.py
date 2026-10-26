"""The frozen contracts: 19 tables, and the committed OpenAPI file matches the running app."""
import json
from pathlib import Path

from app.core.db import Base
from app.main import app

ROOT = Path(__file__).resolve().parents[1]


def test_19_tables():
    import app.models  # noqa: F401  (registers every table on Base)
    assert len(Base.metadata.tables) == 19


def test_openapi_contract_is_current():
    committed = json.loads((ROOT / "contracts/openapi.json").read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(app.openapi())), "run: python backend/scripts/export_openapi.py"


def test_no_admin_role_anywhere():
    from app.core.security import ROLES
    assert ROLES == ("institution", "officer", "inspector")
    assert not [p for p in app.openapi()["paths"] if "/auth/users" in p]
