import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    out = tmp_path_factory.mktemp("syn")
    subprocess.run([sys.executable, str(ROOT / "scripts/generate_synthetic.py"), "--out", str(out), "--expected", str(out / "e.json")], check=True, capture_output=True)
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
    from app.services.rules import loader, store
    from app.services.synthetic_loader import load_synthetic

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_users(db)
        ids = {k: a.id for k, a in load_synthetic(db, out).items()}
        store.create_draft(db, loader.load_dir(loader.RULEPACK_DIR / "APH-2024-27-v1"), None, status="active")
    yield ids
    base.set_client_factory(None)


def run_rules(app_id, only=None):
    from app.core.db import SessionLocal
    from app.models import Application
    from app.services.evidence.graph import build_facts
    from app.services.rules import evaluator, store
    from app.services.rules.context import build_context

    with SessionLocal() as db:
        app = db.get(Application, app_id)
        build_facts(db, app)
        _, pack = store.active(db)
        return evaluator.evaluate_pack(pack, build_context(db, app, pack), only)


def fails(results):
    return {(r["rule_id"], r["scope"]) for r in results if r["status"] == "FAIL"}


def test_a_is_clean_and_every_rule_has_evidence(world):
    res = run_rules(world["a", "2027-28"])
    assert fails(res) == set(), [r for r in res if r["status"] != "PASS"]
    assert not [r for r in res if r["status"] == "INSUFFICIENT_EVIDENCE"], [r["rule_id"] for r in res if r["status"] == "INSUFFICIENT_EVIDENCE"]
    assert any(r["rule_id"] == "ELIG-3YR-NAAC" and r["status"] == "PASS" for r in res)  # A's claim is supported by the (mock) NAAC list


def test_b_planted_rule_failures(world):
    res = run_rules(world["b", "2027-28"])
    assert fails(res) == {("EXP-FIRE-AY", None), ("TL-PROVISIONAL-OC-LIMIT", None)}, [r for r in res if r["status"] == "FAIL"]
    prov = next(r for r in res if r["rule_id"] == "TL-PROVISIONAL-OC-LIMIT")
    assert prov["computed"]["years_used"] == 3
    # >30-year main block: structural certificate required and supplied
    assert next(r for r in res if r["rule_id"] == "DOC-EOA-STRUCTURAL-STABILITY-CERTIFICATE")["status"] == "PASS"
    assert not [r for r in res if r["status"] == "INSUFFICIENT_EVIDENCE"]


def test_c_planted_rule_failures_and_faculty_numbers(world):
    res = run_rules(world["c", "2027-28"])
    f = fails(res)
    assert ("FAC-UG-ENGG-RATIO", "ENGINEERING_AND_TECHNOLOGY/UG") in f
    assert ("TL-ESTAMP-BEFORE-NOTARY", None) in f and ("CONS-SURVEY-NO", None) in f
    fac = next(r for r in res if r["rule_id"] == "FAC-UG-ENGG-RATIO")
    assert (fac["computed"]["S"], fac["computed"]["required"], fac["inputs"]["valid_full_time_faculty"]) == (2400, 120, 97)
    assert "shortfall 23" in fac["message"] and fac["citation"]["page"] == 95
    assert not any(rid.startswith(("INFRA-", "FAC-CADRE", "DOC-")) for rid, _ in f), f
    # A structural certificate is not required for C (youngest-to-oldest building is < 30 years)
    assert not [r for r in res if r["rule_id"] == "DOC-EOA-STRUCTURAL-STABILITY-CERTIFICATE"]


def test_evidence_graph_provenance(world):
    from app.core.db import SessionLocal
    from app.models import Application
    from app.services.evidence.graph import graph_json

    with SessionLocal() as db:
        g = graph_json(db, db.get(Application, world["c", "2027-28"]))
    land = next(f for f in g["facts"] if f["subject"] == "doc:LAND_DOCUMENT#1" and f["attribute"] == "survey_no")
    assert land["value"] == "SY-118/9C" and land["source"]["page"] == 1 and len(land["source"]["bbox"]) == 4 and land["source"]["type"] == "document"
    dups = next(f for f in g["facts"] if f["attribute"] == "duplicates_cross_institution")
    assert len(dups["value"]) == 12 and dups["source"]["mock"] is True and "MOCK" in dups["source"]["system_source"]
    form = next(f for f in g["facts"] if f["subject"] == "institution" and f["attribute"] == "survey_no")
    assert form["value"] == "SY-118/4B" and form["source"]["type"] == "form"
    assert {d["subject"] for d in g["documents"]} >= {"doc:AFFIDAVIT_2#1", "doc:OCCUPANCY_CERTIFICATE#3"}


def test_carry_forward_only_unchanged_verified_documents(world):
    from app.core.db import SessionLocal
    from app.models import Document, Verification
    from app.services.evidence.carry_forward import carry_forward

    with SessionLocal() as db:
        def doc(key, ay, dtype):
            return db.scalar(select(Document).where(Document.application_id == world[key, ay], Document.doc_type == dtype))

        for key in "ac":
            land_prev = doc(key, "2026-27", "LAND_DOCUMENT")
            db.add(Verification(application_id=world[key, "2026-27"], document_id=land_prev.id, adapter="digilocker", status="VERIFIED", source="DigiLocker (MOCK)",
                                response_summary="owner and survey number match", checked_at=datetime(2026, 3, 2)))
        db.commit()
        assert carry_forward(db, db.get(__import__("app.models", fromlist=["Application"]).Application, world["a", "2027-28"])) == [doc("a", "2027-28", "LAND_DOCUMENT").id]
        assert doc("a", "2027-28", "LAND_DOCUMENT").carried_forward_from == "2026-27"
        v = db.scalar(select(Verification).where(Verification.document_id == doc("a", "2027-28", "LAND_DOCUMENT").id))
        assert v.status == "VERIFIED" and "carried forward from 2026-27" in v.response_summary
        # C's land document changed (tampered), so nothing is carried forward even though last year's copy was verified
        assert carry_forward(db, db.get(__import__("app.models", fromlist=["Application"]).Application, world["c", "2027-28"])) == []
        assert doc("a", "2027-28", "OCCUPANCY_CERTIFICATE").carried_forward_from is None  # identical bytes but never verified before


def test_rulepack_api_last(world, client, login):
    off = login("officer@tatva.test")
    assert client.get("/api/v1/rulepacks", headers=off).status_code == 200
    r = client.post("/api/v1/rulepacks", json={"from_dir": "APH-2024-27-v1"}, headers=off)
    assert r.status_code == 201 and r.json()["status"] == "draft"
    assert client.post("/api/v1/rulepacks", json={"from_dir": "APH-2024-27-v1"}, headers=off).status_code == 409  # immutable versions
    bad = client.post("/api/v1/rulepacks", json={"yaml": "pack: x\nversion: z\nrules: []"}, headers=off)
    assert bad.status_code == 422 and bad.json()["detail"]["errors"]
    v2 = client.post("/api/v1/rulepacks", json={"from_dir": "APH-2024-27-v2-demo"}, headers=off)
    assert client.post("/api/v1/rulepacks/v1/activate", headers=off).json()["status"] == "active"
    assert client.post("/api/v1/rulepacks/v2-demo/activate", headers=off).json()["status"] == "active"
    statuses = {p["version"]: p["status"] for p in client.get("/api/v1/rulepacks", headers=off).json()}
    assert statuses == {"v1": "retired", "v2-demo": "active"}
