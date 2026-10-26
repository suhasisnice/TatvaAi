import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
AY = "2027-28"


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("syn")
    subprocess.run([sys.executable, str(ROOT / "scripts/generate_synthetic.py"), "--out", str(out), "--expected", str(out / "expected.json")], check=True, capture_output=True)
    from app.core.config import settings
    settings.storage_dir = str(tmp_path_factory.mktemp("store"))
    settings.trust_root_path = str(out / "pki/ca.pem")
    os.environ["MOCK_DB"] = str(out / "mock_db.json")
    sys.path.insert(0, str(ROOT / "mock_issuers"))
    import importlib
    import main as mi
    importlib.reload(mi)
    from app.adapters import base
    base.set_client_factory(lambda: TestClient(mi.app))
    from app.core.db import Base, SessionLocal, engine
    import app.models  # noqa: F401
    from app.services.demo_seed import seed_users
    from app.services.pipeline import run_all
    from app.services.rules import loader, store
    from app.services.synthetic_loader import load_synthetic

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_users(db)
        ids = {k: a.id for k, a in load_synthetic(db, out).items()}
        store.create_draft(db, loader.load_dir(loader.RULEPACK_DIR / "APH-2024-27-v1"), None, status="active")
        run_all(db)
    yield ids, json.loads((out / "expected.json").read_text())
    base.set_client_factory(None)


def flags_of(ids, key, ay=AY):
    from app.core.db import SessionLocal
    from app.models import Flag

    with SessionLocal() as db:
        return [dict(code=f.code, severity=f.severity, engine=f.engine, message=f.message, evidence=json.loads(f.evidence), forensic=f.forensic,
                     explanation=f.explanation, rule_id=f.rule_id, citation=f.citation, confidence=f.confidence)
                for f in db.scalars(select(Flag).where(Flag.application_id == ids[key, ay]))]


def test_every_planted_flag_is_caught(world):
    ids, expected = world
    for key in "abc":
        codes = {f["code"] for f in flags_of(ids, key)}
        missed = [p["code"] for p in expected[key]["planted"] if p["code"] not in codes]
        assert not missed, (key, missed, sorted(codes))


def test_a_has_only_info_flags(world):
    ids, _ = world
    fl = flags_of(ids, "a")
    assert {f["severity"] for f in fl} <= {"INFO"}, [f for f in fl if f["severity"] != "INFO"]
    assert [f["code"] for f in fl].count("ISSUER_UNAVAILABLE") >= 1


def test_b_has_exactly_the_two_planted_majors(world):
    ids, _ = world
    big = sorted(f["code"] for f in flags_of(ids, "b") if f["severity"] != "INFO")
    assert big == ["DOC_EXPIRES_BEFORE_AY", "PROVISIONAL_OC_LIMIT_EXCEEDED"], big


def test_c_flag_details(world):
    ids, expected = world
    fl = flags_of(ids, "c")
    by = {}
    for f in fl:
        by.setdefault(f["code"], []).append(f)
    tamper = by["TAMPER_SUSPECTED"][0]
    assert tamper["severity"] == "CRITICAL" and tamper["forensic"] and tamper["explanation"].startswith("Preliminary indicator — requires human verification")
    assert any(e.get("field") == "survey_no" and e["bbox"] for e in tamper["evidence"]) and any(e.get("artifact") == "ela_heatmap" for e in tamper["evidence"])
    mod = by["MODIFIED_AFTER_SIGNING"][0]
    assert mod["severity"] == "CRITICAL" and "SY-118/4B" in mod["message"] and "SY-118/9C" in mod["message"]  # what changed after signing
    assert mod["evidence"][0]["field"] == "survey_no" and mod["evidence"][0]["bbox"] and mod["evidence"][0]["before"] == "SY-118/4B"
    assert "2026-12-31" in by["QR_MISMATCH"][0]["message"] and "2028-12-31" in by["QR_MISMATCH"][0]["message"]
    assert "shortfall 23" in by["NORM_FACULTY_SHORTFALL"][0]["message"] and json.loads(by["NORM_FACULTY_SHORTFALL"][0]["citation"])["page"] == 95
    assert "31,500" in by["BUILTUP_AREA_IMPLAUSIBLE"][0]["message"] and "24,100" in by["BUILTUP_AREA_IMPLAUSIBLE"][0]["message"]
    assert "Block C" in by["BUILDING_NOT_VISIBLE_ON_DATE"][0]["message"] and "2026" in by["BUILDING_NOT_VISIBLE_ON_DATE"][0]["message"]
    assert "85" in by["DISCLOSURE_MISMATCH"][0]["message"] and "109" in by["DISCLOSURE_MISMATCH"][0]["message"]
    assert by["DUPLICATE_FACULTY_CROSS_INSTITUTION"][0]["severity"] == "MAJOR" and "12 faculty" in by["DUPLICATE_FACULTY_CROSS_INSTITUTION"][0]["message"]
    assert by["PHOTO_GPS_OFFSITE"][0]["severity"] == "MAJOR" and "classroom_1.jpg" in by["PHOTO_GPS_OFFSITE"][0]["message"]
    dup = [f for f in by["DUPLICATE_PHOTO"] if f["severity"] == "MAJOR"]
    assert len(dup) == 1 and "lab_1.jpg" in dup[0]["message"]
    assert by["TIMELINE_IMPOSSIBLE"][0]["evidence"][0]["bbox"]
    assert "ISSUER_MISMATCH" in by and "MISMATCH_CROSS_YEAR" in by
    print("C unexpected:", sorted({f["code"] for f in fl} - {p["code"] for p in expected["c"]["planted"]} - {p["code"] for p in expected["c"]["optional"]}))


def test_a_photo_reuse_gives_earlier_owner_only_info(world):
    ids, _ = world
    dups = [f for f in flags_of(ids, "a") if f["code"] == "DUPLICATE_PHOTO"]
    assert dups and {f["severity"] for f in dups} == {"INFO"}


def test_every_flag_points_to_evidence_and_has_rule_citation_when_rule_based(world):
    ids, _ = world
    for key in "abc":
        for f in flags_of(ids, key):
            assert f["evidence"], f
            for e in f["evidence"]:
                assert ("document_id" in e) or ("system_source" in e), f
            if f["forensic"]:
                assert f["explanation"].startswith("Preliminary indicator — requires human verification")
            if f["rule_id"]:
                assert f["citation"]


def test_verifications_proof_levels_and_carry_forward(world):
    ids, _ = world
    from app.core.db import SessionLocal
    from app.models import Document, Verification

    with SessionLocal() as db:
        def ver(key, adapter, ay=AY):
            return [v.status for v in db.scalars(select(Verification).where(Verification.application_id == ids[key, ay], Verification.adapter == adapter))]

        def doc(key, dtype):
            return db.scalar(select(Document).where(Document.application_id == ids[key, AY], Document.doc_type == dtype))

        assert ver("a", "shcil_estamp") == ["VERIFIED"]
        assert ver("a", "fire_noc") == ["SOURCE_UNAVAILABLE", "MANUAL_REVIEW_REQUIRED"]
        assert ver("a", "accreditation_lists") == ["VERIFIED"]
        assert ver("b", "occupancy").count("SOURCE_UNAVAILABLE") == 2 and ver("b", "manual") == ["MANUAL_REVIEW_REQUIRED"]
        assert ver("c", "digilocker") == ["MISMATCH_DETECTED"] and ver("c", "fire_noc") == ["VERIFIED"]
        assert ver("a", "digilocker", "2026-27") == ["VERIFIED"]
        a_land = doc("a", "LAND_DOCUMENT")
        assert a_land.carried_forward_from == "2026-27" and ver("a", "digilocker") == ["VERIFIED"]
        assert "carried forward from 2026-27" in db.scalar(select(Verification).where(Verification.document_id == a_land.id)).response_summary
        assert a_land.proof_level == "ISSUER_VERIFIED"
        assert doc("c", "LAND_DOCUMENT").proof_level == "FORENSIC_ONLY"
        assert doc("a", "FIRE_SAFETY_CERTIFICATE").proof_level == "CRYPTOGRAPHIC"
        assert doc("a", "AFFIDAVIT_2").proof_level == "ISSUER_VERIFIED"
        from app.core import storage
        assert storage.get(json.loads(doc("c", "LAND_DOCUMENT").forensics)["ela_key"]).startswith(b"\x89PNG")


def test_status_mapping_covers_all_six(world):
    from app.adapters.base import Result
    from app.services.engines.issuer import _status

    ok = lambda status=200, body=None: Result("s", status, body or {}, "h", "h")
    assert _status(ok(), [], None)[0] == "VERIFIED"
    assert _status(ok(), [dict(field="x", printed=1, issuer=2)], None)[0] == "MISMATCH_DETECTED"
    assert _status(ok(), [], "2026-01-01")[0] == "EXPIRED"
    assert _status(ok(body={"status": "PENDING"}), [], None)[0] == "VERIFICATION_PENDING"
    assert _status(ok(503), [], None)[0] == "SOURCE_UNAVAILABLE" and _status(Result("s", None, None, "h", None), [], None)[0] == "SOURCE_UNAVAILABLE"
    assert _status(ok(501), [], None)[0] == "SOURCE_UNAVAILABLE"  # "no API" portals are unavailable too -> routed to MANUAL_REVIEW_REQUIRED


def test_rule_results_stored_with_pack_version(world):
    ids, _ = world
    from app.core.db import SessionLocal
    from app.models import RuleResult

    with SessionLocal() as db:
        rows = db.scalars(select(RuleResult).where(RuleResult.application_id == ids["c", AY])).all()
        assert rows and {r.rule_pack_version for r in rows} == {"v1"}
        assert {r.status for r in rows} <= {"PASS", "FAIL", "INSUFFICIENT_EVIDENCE"}


def test_rerun_is_idempotent_and_keeps_decisions(world):
    ids, _ = world
    from app.core.db import SessionLocal
    from app.models import Application, Flag
    from app.services.pipeline import run_pipeline

    with SessionLocal() as db:
        before = db.query(Flag).filter_by(application_id=ids["c", AY]).count()
        f = db.scalar(select(Flag).where(Flag.application_id == ids["c", AY], Flag.code == "DISCLOSURE_MISMATCH"))
        f.status = "DISMISSED"
        db.commit()
        run_pipeline(db, db.get(Application, ids["c", AY]))
        assert db.query(Flag).filter_by(application_id=ids["c", AY]).count() == before
        assert db.scalar(select(Flag).where(Flag.application_id == ids["c", AY], Flag.code == "DISCLOSURE_MISMATCH")).status == "DISMISSED"


def test_verify_api_and_ela_endpoint_last(world, client, login):
    # `client` resets the DB; this only checks roles on the new endpoints
    inst, off = login("inst-a@tatva.test"), login("officer@tatva.test")
    assert client.post("/api/v1/applications/1/verify", headers=inst).status_code == 403
    assert client.post("/api/v1/applications/999/verify", headers=off).status_code == 404
    assert client.get("/api/v1/applications/999/verifications", headers=off).status_code == 404
