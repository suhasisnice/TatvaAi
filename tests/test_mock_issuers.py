import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def mock(tmp_path_factory):
    out = tmp_path_factory.mktemp("mockdata")
    subprocess.run([sys.executable, str(ROOT / "scripts/generate_synthetic.py"), "--out", str(out), "--expected", str(out / "e.json")],
                   check=True, capture_output=True)
    os.environ["MOCK_DB"] = str(out / "mock_db.json")
    sys.path.insert(0, str(ROOT / "mock_issuers"))
    import importlib
    import main as mi
    importlib.reload(mi)
    return TestClient(mi.app), json.loads((out / "mock_db.json").read_text())


def test_all_responses_flagged_mock_and_lookups(mock):
    c, db = mock
    stamp = next(iter(db["shcil"]))
    r = c.get("/shcil/verify", params={"cert_no": stamp}).json()
    assert r["mock"] is True and r["record"]["value"] == 100
    assert c.get("/shcil/verify", params={"cert_no": "nope"}).status_code == 404
    assert c.get("/naac/grades").json()["grades"]["SYN-AICTE-1001"] == 3.22
    assert c.get("/health").json()["mock"] is True


def test_portal_failure_modes(mock):
    c, db = mock
    assert c.get("/fire/karnataka/verify", params={"cert_no": "x"}).status_code == 503
    assert c.get("/occupancy/maharashtra/verify", params={"cert_no": "x"}).status_code == 501
    cert = next(iter(db["fire"]["maharashtra"]))
    assert c.get("/fire/maharashtra/verify", params={"cert_no": cert}).json()["record"]["valid_till"] == "2027-06-30"


def test_faculty_registry_duplicates_and_web_and_geo(mock):
    c, _ = mock
    regs = c.get("/aicte/faculty-registry/AICTE-FAC-900001").json()["registrations"]
    assert {r["institution_aicte_id"] for r in regs} == {"SYN-AICTE-1004", "SYN-AICTE-1003"}
    assert 'id=\'faculty\'>85<' in c.get("/web/inst-c/mandatory-disclosure").text
    feats = c.get("/geo/footprints/inst-c-main").json()["features"]
    assert sum(f["properties"]["area_m2"] for f in feats) == 6025
    assert [f["properties"]["first_seen_year"] for f in feats][-1] == 2026
    assert c.get("/aicte/records/SYN-AICTE-1002").json()["record"]["provisional_oc_history"][0]["academic_years"] == ["2025-26", "2026-27"]
