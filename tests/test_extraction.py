import json
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def loaded(tmp_path_factory):
    out = tmp_path_factory.mktemp("syn")
    subprocess.run([sys.executable, str(ROOT / "scripts/generate_synthetic.py"), "--out", str(out), "--expected", str(out / "e.json")],
                   check=True, capture_output=True)
    from app.core.config import settings
    settings.storage_dir = str(tmp_path_factory.mktemp("store"))
    settings.trust_root_path = str(out / "pki/ca.pem")
    from app.core.db import Base, SessionLocal, engine
    import app.models  # noqa: F401
    from app.services.demo_seed import seed_users
    from app.services.synthetic_loader import load_synthetic

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_users(db)
        apps = load_synthetic(db, out)
        ids = {k: a.id for k, a in apps.items()}
    return json.loads((out / "manifest.json").read_text()), ids, out


def test_every_document_classified_and_fields_match_ground_truth(loaded):
    from app.core.db import SessionLocal
    from app.models import Document, ExtractedField

    manifest, ids, _ = loaded
    n = 0
    with SessionLocal() as db:
        for m in manifest["documents"]:
            doc = db.scalar(select(Document).where(Document.application_id == ids[m["institution"], m["academic_year"]], Document.filename == Path(m["file"]).name))
            assert doc.doc_type == m["doc_type"], m["file"]
            got = {f.name: f for f in db.scalars(select(ExtractedField).where(ExtractedField.document_id == doc.id))}
            for k, spec in m["fields"].items():
                f = got[k]
                assert f.value == spec["value"], (m["file"], k, f.value, spec["value"])
                assert f.page == 1 and f.confidence > 0.9
                assert 0 <= f.x0 < f.x1 <= 1 and 0 <= f.y0 < f.y1 <= 1, (m["file"], k)
                n += 1
    assert n > 250


def test_signatures_qr_and_photos(loaded):
    from app.core.db import SessionLocal
    from app.models import Document, ExtractedField

    manifest, ids, _ = loaded
    with SessionLocal() as db:
        def docs(inst, year):
            return list(db.scalars(select(Document).where(Document.application_id == ids[inst, year])))

        for inst in "abc":
            for d in docs(inst, "2027-28"):
                if d.content_type == "application/pdf":
                    want = "SIGNED_MODIFIED" if (inst == "c" and d.doc_type == "LAND_DOCUMENT") else "SIGNED_VALID"
                    assert d.dsc_status == want, (inst, d.filename, d.dsc_status)
        for m in manifest["documents"]:
            if "qr_payload" in m:
                d = db.scalar(select(Document).where(Document.application_id == ids[m["institution"], m["academic_year"]], Document.filename == Path(m["file"]).name))
                assert json.loads(d.qr_payload) == json.loads(m["qr_payload"])
        c_fire = next(d for d in docs("c", "2027-28") if d.doc_type == "FIRE_SAFETY_CERTIFICATE")
        assert json.loads(c_fire.qr_payload)["valid_till"] == "2026-12-31"
        photos = {d.filename: {f.name: f.value for f in db.scalars(select(ExtractedField).where(ExtractedField.document_id == d.id))} for d in docs("c", "2027-28") if d.doc_type == "INFRA_PHOTO"}
        assert len(photos) == 3 and all(p["camera"] and p["phash"] and p["taken_at"] for p in photos.values())
        assert float(photos["classroom_1.jpg"]["gps_lat"]) - 11.05 > 0.3  # ~40 km off-site
        assert abs(float(photos["library_1.jpg"]["gps_lat"]) - 11.05) < 0.01


def test_faculty_loaded(loaded):
    from app.core.db import SessionLocal
    from app.models import FacultyRecord

    _, ids, _ = loaded
    with SessionLocal() as db:
        assert db.query(FacultyRecord).filter_by(application_id=ids["c", "2027-28"]).count() == 109


def test_upload_api_last(loaded, client, login):  # `client` resets the DB, so keep this test last in the module
    _, _, out = loaded
    a_head, b_head = login("inst-a@pramaan.test"), login("inst-b@pramaan.test")
    app_id = client.post("/api/v1/applications", json={}, headers=a_head).json()["id"]
    sample = (out / "a/2027-28/docs/TER_RECEIPT.pdf").read_bytes()
    r = client.post(f"/api/v1/applications/{app_id}/documents", files={"file": ("x.pdf", sample, "application/pdf")}, headers=a_head)
    assert r.status_code == 201 and r.json()["doc_type"] == "TER_RECEIPT"
    assert r.json()["dsc_status"] == "SIGNED_VALID"
    did = r.json()["id"]
    assert client.get(f"/api/v1/documents/{did}/fields", headers=a_head).json()[0]["bbox"]
    assert client.get(f"/api/v1/documents/{did}/pages/1.png", headers=a_head).headers["content-type"] == "image/png"
    assert client.get(f"/api/v1/documents/{did}/file", headers=b_head).status_code == 404  # other institution
    post = lambda name, data: client.post(f"/api/v1/applications/{app_id}/documents", files={"file": (name, data, "application/octet-stream")}, headers=a_head)
    assert post("x.pdf", b"not a pdf").status_code == 422
    assert post("x.exe", b"MZ").status_code == 422
