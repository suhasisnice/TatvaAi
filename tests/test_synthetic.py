"""Checks the generated synthetic data really contains what the ground truth says. Run scripts first (see the project notes)."""
import json
import subprocess
import sys
from pathlib import Path

import pymupdf
import pytest
from pyhanko.keys import load_cert_from_pemder
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "synthetic"


@pytest.fixture(scope="module", autouse=True)
def generated():
    if not (DATA / "manifest.json").exists():
        subprocess.run([sys.executable, "scripts/make_test_pki.py"], cwd=ROOT, check=True)
        subprocess.run([sys.executable, "-W", "ignore", "scripts/generate_synthetic.py"], cwd=ROOT, check=True)


def status(path):
    ctx = ValidationContext(trust_roots=[load_cert_from_pemder(DATA / "pki" / "ca.pem")])
    with open(path, "rb") as f:
        s = validate_pdf_signature(PdfFileReader(f).embedded_signatures[0], ctx)
    return s.intact, s.valid, s.trusted, s.modification_level.name


def test_every_pdf_is_validly_signed_except_c_land():
    manifest = json.loads((DATA / "manifest.json").read_text())
    for d in manifest["docs"]:
        intact, valid, trusted, mod = status(DATA / d["path"])
        assert intact and valid and trusted, d["path"]
        if d["path"] == "c/2027-28/docs/land_record.pdf":
            assert mod != "NONE", "C land record must be modified after signing"
        else:
            assert mod == "NONE", d["path"]


def test_c_land_survey_changed_and_digilocker_keeps_original():
    p = DATA / "c/2027-28/docs/land_record.pdf"
    text = pymupdf.open(p)[0].get_text()
    assert "SY-118/9C" in text
    db = json.loads((DATA / "mock_db.json").read_text())
    assert db["digilocker"]["in.gov.synthetic-digilocker/LAND/00003"]["fields"]["survey_no"] == "SY-118/4B"


def test_planted_numbers():
    db = json.loads((DATA / "mock_db.json").read_text())
    assert sum(f["footprint_m2"] * f["floors"] for f in db["footprints"]["SYN-AICTE-1003"]) == 24100
    assert sum(1 for line in (DATA / "c/2027-28/faculty.csv").read_text().splitlines()[1:]) == 109
    assert len(db["faculty_registry"]) == 12
    assert db["websites"]["SYN-AICTE-1003"]["faculty_count"] == 85


def test_mock_issuers_serve_records_and_503_when_down():
    sys.path.insert(0, str(ROOT / "mock_issuers"))
    from fastapi.testclient import TestClient
    from main import app as mock
    c = TestClient(mock)
    r = c.get("/fire/FIRE/TN/3", params={"state": "TN"}).json()
    assert r["mock"] and r["status"] == "FOUND" and r["record"]["valid_till"] == "2028-12-31"
    assert c.get("/fire/FIRE/KA/1", params={"state": "KA"}).status_code == 503
    assert c.get("/estamp/IN-TN1003").json()["record"]["issue_date"] == "2027-01-20"
