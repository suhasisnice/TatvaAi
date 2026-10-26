"""Regenerate contracts/openapi.json. Run from the repo root: python backend/scripts/export_openapi.py"""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "backend"))
from app.main import app  # noqa: E402

(root / "contracts" / "openapi.json").write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
print("wrote contracts/openapi.json")
