import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def gen(out: Path) -> dict:
    subprocess.run([sys.executable, str(ROOT / "scripts/generate_synthetic.py"), "--out", str(out), "--expected", str(out / "exp.json")],
                   check=True, capture_output=True)
    return json.loads((out / "manifest.json").read_text())


@pytest.fixture(scope="module")
def two_runs(tmp_path_factory):
    return gen(tmp_path_factory.mktemp("g1")), gen(tmp_path_factory.mktemp("g2")), tmp_path_factory.getbasetemp() / "g10"


def test_deterministic(two_runs):
    m1, m2, _ = two_runs
    assert m1["files"] == m2["files"]  # includes mock_db.json, signed PDFs, photos, CSVs


def test_planted_documents_and_carry_forward(two_runs):
    m, _, _ = two_runs
    sha = {(d["institution"], d["academic_year"], d["doc_type"], d["name"]): d["sha256"] for d in m["documents"]}
    # A's land document is byte-identical across years (carry-forward); C's differs (tampered this year)
    assert sha["a", "2027-28", "LAND_DOCUMENT", "LAND_DOCUMENT"] == sha["a", "2026-27", "LAND_DOCUMENT", "LAND_DOCUMENT"]
    assert sha["c", "2027-28", "LAND_DOCUMENT", "LAND_DOCUMENT"] != sha["c", "2026-27", "LAND_DOCUMENT", "LAND_DOCUMENT"]
    types_b = {d["doc_type"] for d in m["documents"] if d["institution"] == "b"}
    assert "STRUCTURAL_STABILITY_CERTIFICATE" in types_b  # B's main block is >30 years old
    assert "STRUCTURAL_STABILITY_CERTIFICATE" not in {d["doc_type"] for d in m["documents"] if d["institution"] in "ac"}
    flagged = {c for d in m["documents"] if d["institution"] == "c" and d["academic_year"] == "2027-28" for c in d["planted"]}
    assert {"MODIFIED_AFTER_SIGNING", "QR_MISMATCH", "TIMELINE_IMPOSSIBLE"} <= flagged


def test_pdf_signatures(two_runs, tmp_path_factory):
    from pyhanko.keys import load_cert_from_pemder
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko_certvalidator import ValidationContext

    m, _, base = two_runs
    root = Path(base).parent / "g0"
    out = next(p for p in Path(base).parent.glob("g?*") if (p / "manifest.json").exists())
    vc = ValidationContext(trust_roots=[load_cert_from_pemder(out / "pki/ca.pem")], allow_fetching=False)

    def status(rel):
        with open(out / rel, "rb") as f:
            sig = PdfFileReader(f).embedded_signatures[0]
            return validate_pdf_signature(sig, vc)

    ok = status("a/2027-28/docs/LAND_DOCUMENT.pdf")
    assert ok.intact and ok.valid and ok.trusted
    bad = status("c/2027-28/docs/LAND_DOCUMENT.pdf")
    assert bad.intact and bad.valid  # signed bytes untouched, but...
    assert bad.modification_level is not None and bad.modification_level.name != "LTA_UPDATES"  # ...document changed after signing
