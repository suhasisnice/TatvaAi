import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
PW = "Tatva@2026"
AY = "2027-28"


@pytest.fixture(scope="module")
def env(tmp_path_factory):
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
    from app.main import app
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
    api = TestClient(app)

    def login(email):
        r = api.post("/api/v1/auth/login", json={"email": email, "password": PW})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    yield dict(api=api, ids=ids, login=login, out=out)
    base.set_client_factory(None)


def test_queue_is_sorted_by_risk_with_text_labels(env):
    q = env["api"].get("/api/v1/risk/queue", headers=env["login"]("officer@tatva.test")).json()
    assert [(i["institution_name"][:5], i["tier"], i["tier_label"]) for i in q] == [("Chand", "RED", "High risk"), ("Bhava", "AMBER", "Medium risk"), ("Auror", "GREEN", "No risk")]
    assert q[0]["top_reason"] and q[0]["score"] > q[1]["score"] > q[2]["score"] == 0
    assert len(env["api"].get("/api/v1/risk/queue?academic_year=all", headers=env["login"]("officer@tatva.test")).json()) == 5
    assert env["api"].get("/api/v1/risk/queue?tier=RED", headers=env["login"]("officer@tatva.test")).json()[0]["tier"] == "RED"
    assert env["api"].get("/api/v1/risk/queue", headers=env["login"]("inst-a@tatva.test")).status_code == 403
    stats = env["api"].get("/api/v1/risk/stats", headers=env["login"]("officer@tatva.test")).json()
    assert stats["by_tier"] == {"GREEN": 1, "AMBER": 1, "RED": 1}


def test_tier_scoring_details(env):
    h = env["login"]("officer@tatva.test")
    a = env["api"].get(f"/api/v1/applications/{env['ids']['b', AY]}", headers=h).json()["risk"]
    assert a["tier"] == "AMBER" and a["score"] == 30 and a["routing"] == "FIX_LIST" and len(a["reasons"]) == 2 and a["rule_pack_version"] == "v1"
    c = env["api"].get(f"/api/v1/applications/{env['ids']['c', AY]}", headers=h).json()["risk"]
    assert c["tier"] == "RED" and c["routing"] == "INSPECTION_LIST" and c["reasons"][0]["contribution"] >= c["reasons"][-1]["contribution"]


def test_flag_decision_requires_reason_and_keeps_flag(env):
    api, ids = env["api"], env["ids"]
    off, insp = env["login"]("officer@tatva.test"), env["login"]("inspector@tatva.test")
    flags = api.get(f"/api/v1/flags?application_id={ids['c', AY]}", headers=off).json()
    target = next(f for f in flags if f["code"] == "DISCLOSURE_MISMATCH")
    assert target["evidence"] and target["status"] == "OPEN"
    before = api.get(f"/api/v1/applications/{ids['c', AY]}", headers=off).json()["risk"]["score"]
    assert api.post(f"/api/v1/flags/{target['id']}/decision", json={"decision": "DISMISS", "reason": "no"}, headers=off).status_code == 422
    assert api.post(f"/api/v1/flags/{target['id']}/decision", json={"decision": "REJECT", "reason": "not a thing"}, headers=off).status_code == 422
    assert api.post(f"/api/v1/flags/{target['id']}/decision", json={"decision": "DISMISS", "reason": "Website updated, verified by phone"}, headers=insp).status_code == 403
    r = api.post(f"/api/v1/flags/{target['id']}/decision", json={"decision": "DISMISS", "reason": "Website updated, verified by phone"}, headers=off).json()
    assert r["flag"]["status"] == "DISMISSED" and r["risk"]["score"] == before - 15 and r["flag"]["decisions"][0]["reason"].startswith("Website")
    assert any(f["id"] == target["id"] for f in api.get(f"/api/v1/flags?application_id={ids['c', AY]}", headers=off).json())  # dismissed, not deleted
    audit = api.get(f"/api/v1/audit?application_id={ids['c', AY]}&action=flag.decision", headers=off).json()
    assert audit and audit[0]["payload"]["reason"].startswith("Website") and audit[0]["payload"]["score_after"] == before - 15


def test_manual_verification_of_unavailable_source(env):
    api, ids, off = env["api"], env["ids"], env["login"]("officer@tatva.test")
    vs = api.get(f"/api/v1/applications/{ids['a', AY]}/verifications", headers=off).json()
    fire = [v for v in vs if v["source"].startswith("Karnataka fire")]
    assert [v["status"] for v in fire] == ["SOURCE_UNAVAILABLE", "MANUAL_REVIEW_REQUIRED"] and all(v["mock"] for v in vs)
    manual = fire[1]["id"]
    assert api.post(f"/api/v1/verifications/{manual}/manual", json={"note": "x"}, headers=off).status_code == 422
    assert api.post(f"/api/v1/verifications/{manual}/manual", json={"note": "Confirmed with the fire office by phone"}, headers=env["login"]("inst-a@tatva.test")).status_code == 403
    r = api.post(f"/api/v1/verifications/{manual}/manual", json={"note": "Confirmed with the fire office by phone"}, headers=off)
    assert r.json()["status"] == "VERIFIED"
    assert api.post(f"/api/v1/verifications/{manual}/manual", json={"note": "Confirmed again later"}, headers=off).status_code == 409


def test_precheck_submit_lock_reopen_once(env):
    api, ids = env["api"], env["ids"]
    b, off = env["login"]("inst-b@tatva.test"), env["login"]("officer@tatva.test")
    app_id = ids["b", AY]
    assert api.post(f"/api/v1/applications/{app_id}/precheck", headers=b).status_code == 409  # locked
    assert api.patch(f"/api/v1/applications/{app_id}", json={"form": {"signatory": {"name": "X"}}}, headers=b).status_code == 409
    assert api.post(f"/api/v1/applications/{app_id}/reopen", headers=b).status_code == 403
    r = api.post(f"/api/v1/applications/{app_id}/reopen", headers=off).json()
    assert r["locked"] is False and r["status"] == "REOPENED" and r["reopen_count"] == 1
    # pre-check: plain-language fix-list with citations, no officer-side risk data
    started = api.post(f"/api/v1/applications/{app_id}/precheck", headers=b)
    assert started.status_code == 202
    job = api.get(f"/api/v1/precheck/jobs/{started.json()['job_id']}", headers=b).json()
    assert job["status"] == "DONE"
    items = {i["code"]: i for g in job["fix_list"]["groups"] for i in g["items"]}
    assert set(items) == {"DOC_EXPIRES_BEFORE_AY", "PROVISIONAL_OC_LIMIT_EXCEEDED"}
    assert "Annexure-2 (v)" in items["DOC_EXPIRES_BEFORE_AY"]["citation"] and "p. 81" in items["DOC_EXPIRES_BEFORE_AY"]["citation"]
    assert "Annexure-3, 3.1 (c)" in items["PROVISIONAL_OC_LIMIT_EXCEEDED"]["citation"] and "p. 86" in items["PROVISIONAL_OC_LIMIT_EXCEEDED"]["citation"] and items["DOC_EXPIRES_BEFORE_AY"]["how_to_fix"]
    assert job["fix_list"]["ready_to_submit"] is False and "risk" not in api.get(f"/api/v1/applications/{app_id}", headers=b).json()
    assert api.get(f"/api/v1/precheck/jobs/{started.json()['job_id']}", headers=env["login"]("inst-a@tatva.test")).status_code == 404
    # edit while unlocked, submit locks again, second reopen refused
    assert api.patch(f"/api/v1/applications/{app_id}", json={"form": {"signatory": {"name": "Edited Signatory"}}}, headers=b).json()["form_data"]["signatory"]["name"] == "Edited Signatory"
    s = api.post(f"/api/v1/applications/{app_id}/submit", headers=b).json()
    assert s["locked"] is True and s["status"] == "SUBMITTED" and s["submitted_at"]
    flags = api.get(f"/api/v1/flags?application_id={app_id}", headers=off).json()
    assert not [f["message"] for f in flags if f["code"] == "METADATA_ANOMALY"]  # a live (real-date) submit must not make the synthetic photos look implausible
    assert api.post(f"/api/v1/applications/{app_id}/submit", headers=b).status_code == 409
    assert api.post(f"/api/v1/applications/{app_id}/reopen", headers=off).status_code == 409


def test_upload_blocked_when_locked_and_allowed_when_open(env):
    api, ids = env["api"], env["ids"]
    a = env["login"]("inst-a@tatva.test")
    sample = (env["out"] / "a/2027-28/docs/TER_RECEIPT.pdf").read_bytes()
    assert api.post(f"/api/v1/applications/{ids['a', AY]}/documents", files={"file": ("t.pdf", sample, "application/pdf")}, headers=a).status_code == 409
    new = api.post("/api/v1/applications", json={"academic_year": "2028-29"}, headers=a).json()
    assert new["status"] == "DRAFT" and new["locked"] is False
    assert api.post(f"/api/v1/applications/{new['id']}/documents", files={"file": ("t.pdf", sample, "application/pdf")}, headers=a).status_code == 201


def test_inspection_list_and_pdfs(env):
    api, ids, off = env["api"], env["ids"], env["login"]("officer@tatva.test")
    lst = api.get("/api/v1/risk/inspection-list", headers=env["login"]("inspector@tatva.test")).json()
    assert [i["institution_name"][:7] for i in lst] == ["Chandra"] and lst[0]["tier_label"] == "High risk" and lst[0]["rank"] == 1
    checks = {c["code"] for c in lst[0]["checklist"]}
    assert {"MODIFIED_AFTER_SIGNING", "DUPLICATE_PHOTO", "NORM_FACULTY_SHORTFALL"} <= checks
    pdf = api.get("/api/v1/risk/inspection-list.pdf", headers=off)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and pdf.headers["content-type"] == "application/pdf"
    rep = api.get(f"/api/v1/applications/{ids['c', AY]}/report.pdf", headers=off)
    assert rep.status_code == 200 and rep.content.startswith(b"%PDF")
    assert api.get(f"/api/v1/applications/{ids['c', AY]}/report.pdf", headers=env["login"]("inst-c@tatva.test")).status_code == 403
    gen = api.get(f"/api/v1/audit?action=report.generate", headers=off).json()
    import hashlib
    assert gen[0]["payload"]["file_sha256"] == hashlib.sha256(rep.content).hexdigest() and len(gen[0]["payload"]["content_sha256"]) == 64



def test_inspector_on_site_verdicts_grouped_by_document(env):
    api, insp, off = env["api"], env["login"]("inspector@tatva.test"), env["login"]("officer@tatva.test")
    entry = api.get("/api/v1/risk/inspection-list", headers=insp).json()[0]
    groups = entry["document_groups"]
    assert any(g["document_type"] == "Land Document" for g in groups) and groups[-1]["document_id"] is None  # institution-wide last
    items = [i for g in groups for i in g["items"]]
    assert entry["progress"] == {"resolved": 0, "total": len(items)} and all(i["inspection_status"] == "PENDING" for i in items)
    fid = items[0]["flag_id"]
    assert api.post(f"/api/v1/flags/{fid}/inspection", json={"status": "CONFIRMED", "note": "seen on site"}, headers=off).status_code == 403  # inspectors only
    assert api.post(f"/api/v1/flags/{fid}/inspection", json={"status": "CONFIRMED", "note": "no"}, headers=insp).status_code == 422  # note mandatory
    assert api.post(f"/api/v1/flags/{fid}/inspection", json={"status": "MAYBE", "note": "seen on site"}, headers=insp).status_code == 422
    ok = api.post(f"/api/v1/flags/{fid}/inspection", json={"status": "CONFIRMED", "note": "Original record matches DigiLocker"}, headers=insp)
    assert ok.status_code == 200 and ok.json()["inspection_status"] == "CONFIRMED"
    after = api.get("/api/v1/risk/inspection-list", headers=insp).json()[0]
    assert after["progress"]["resolved"] == 1
    done = next(i for g in after["document_groups"] for i in g["items"] if i["flag_id"] == fid)
    assert done["inspection_note"] == "Original record matches DigiLocker" and done["inspection_by"]
    assert api.get("/api/v1/audit?action=inspection", headers=off).json()[0]["action"] == "inspection.confirmed"

def test_report_footer_contains_content_hash():
    import pymupdf as fitz

    from app.core.db import SessionLocal
    from app.models import Application
    from app.services.reports.pdf import application_report

    with SessionLocal() as db:
        pdf, digest = application_report(db, db.scalars(select(Application).where(Application.academic_year == AY, Application.risk_tier == "RED")).first())
    doc = fitz.open(stream=pdf, filetype="pdf")
    text = " ".join(p.get_text() for p in doc)
    assert digest in text and "RED - High risk" in text and "PRELIMINARY INDICATOR" in text and "Citation:" in text


def test_alerts(env):
    api, ids = env["api"], env["ids"]
    off, c, b, a = env["login"]("officer@tatva.test"), env["login"]("inst-c@tatva.test"), env["login"]("inst-b@tatva.test"), env["login"]("inst-a@tatva.test")
    ao = api.get("/api/v1/alerts", headers=off).json()
    assert ao["unread_count"] >= 1 and any(x["kind"] == "ANOMALY" and x["application_id"] == ids["c", AY] for x in ao["alerts"])
    from app.core.db import SessionLocal
    from app.services.alerts.generate import generate_scheduled

    with SessionLocal() as db:
        made = generate_scheduled(db, today=date(2027, 5, 15))
        again = generate_scheduled(db, today=date(2027, 5, 15))
    assert made["DOC_EXPIRING"] >= 1 and sum(again.values()) == 0  # B's fire certificate (till 2027-06-30) is within 60 days; no duplicates on re-run
    bal = api.get("/api/v1/alerts", headers=b).json()
    expiring = next(x for x in bal["alerts"] if x["kind"] == "DOC_EXPIRING")
    assert "FIRE_SAFETY_CERTIFICATE" in expiring["message"] and expiring["read"] is False
    assert api.post(f"/api/v1/alerts/{expiring['id']}/read", headers=a).status_code == 404  # another institution's alert
    assert api.post(f"/api/v1/alerts/{expiring['id']}/read", headers=b).json() == {"read": True}
    assert api.get("/api/v1/alerts", headers=b).json()["unread_count"] == bal["unread_count"] - 1
    assert not any(x["kind"] == "ANOMALY" for x in api.get("/api/v1/alerts", headers=c).json()["alerts"])  # forensic alerts are officer-only


def test_retention_lists_without_deleting(env):
    from app.core.db import SessionLocal
    from app.models import Document
    from app.services.retention import due

    with SessionLocal() as db:
        n = db.query(Document).count()
        assert due(db, date(2026, 12, 31)) == [] and len(due(db, date(2045, 1, 1))) > 0
        assert db.query(Document).count() == n


def test_audit_chain_and_tamper_detection(env):
    api, off = env["api"], env["login"]("officer@tatva.test")
    v = api.get("/api/v1/audit/verify", headers=off).json()
    assert v["intact"] and v["entries"] > 50
    assert api.get("/api/v1/audit/verify", headers=env["login"]("inst-a@tatva.test")).status_code == 403
    assert api.get("/api/v1/audit/export?format=csv", headers=off).text.startswith("seq,ts,actor")
    from app.core.db import SessionLocal
    from app.models import AuditLog

    with SessionLocal() as db:
        row = db.get(AuditLog, v["entries"] // 2)
        original = row.payload_json
        row.payload_json = original.replace("}", ',"x":1}', 1)
        db.commit()
    broken = api.get("/api/v1/audit/verify", headers=off).json()
    assert broken["intact"] is False and broken["broken_at"] == v["entries"] // 2
    with SessionLocal() as db:
        db.get(AuditLog, v["entries"] // 2).payload_json = original
        db.commit()
    assert api.get("/api/v1/audit/verify", headers=off).json()["intact"]
    with SessionLocal() as db:  # deleting a row is detected too
        gone = db.get(AuditLog, 20)
        snapshot = {c.name: getattr(gone, c.name) for c in AuditLog.__table__.columns}
        db.delete(gone)
        db.commit()
    assert api.get("/api/v1/audit/verify", headers=off).json()["broken_at"] == 21
    with SessionLocal() as db:
        db.add(AuditLog(**snapshot))
        db.commit()
    assert api.get("/api/v1/audit/verify", headers=off).json()["intact"]


def test_dry_run_then_activate_keeps_old_results_last(env):
    api, ids, off = env["api"], env["ids"], env["login"]("officer@tatva.test")
    assert api.post("/api/v1/rulepacks", json={"from_dir": "APH-2024-27-v2-demo"}, headers=off).status_code == 201
    from app.core.db import SessionLocal
    from app.models import Flag, RuleResult

    with SessionLocal() as db:
        flags_before = db.query(Flag).count()
    d = api.post("/api/v1/rulepacks/v2-demo/dry-run", headers=off).json()
    by_inst = {c["institution_name"][:6]: c for c in d["changes"] if c["academic_year"] == AY}
    assert by_inst["Aurora"]["tier_before"] == "GREEN" and by_inst["Aurora"]["tier_after"] == "AMBER"
    assert [f["code"] for f in by_inst["Aurora"]["flags_added"]] == ["NORM_FACULTY_SHORTFALL"]
    assert by_inst["Chandr"]["tier_after"] == "RED" and by_inst["Chandr"]["flags_reworded"] and "shortfall 37" in by_inst["Chandr"]["flags_reworded"][0]["after"]
    assert "Bhavan" not in by_inst and d["tier_changes"] >= 1
    with SessionLocal() as db:
        assert db.query(Flag).count() == flags_before  # dry-run writes nothing
    assert api.post("/api/v1/rulepacks/v2-demo/activate", headers=off).status_code == 200
    with SessionLocal() as db:
        assert {r.rule_pack_version for r in db.scalars(select(RuleResult).where(RuleResult.application_id == ids["a", AY]))} == {"v1"}  # old results unchanged
    from app.models import Application
    from app.services.pipeline import run_pipeline

    with SessionLocal() as db:
        s = run_pipeline(db, db.get(Application, ids["a", AY]))
        assert s["rule_pack_version"] == "v2-demo" and s["tier"] == "AMBER"
    log = api.get("/api/v1/audit?action=rulepack", headers=off).json()
    assert [e["action"] for e in log][:3][::-1] == ["rulepack.create", "rulepack.dry_run", "rulepack.activate"]


def test_flags_roll_up_into_the_two_checking_features(env):
    api, off = env["api"], env["login"]("officer@tatva.test")
    flags = api.get(f"/api/v1/flags?application_id={env['ids']['c', AY]}", headers=off).json()
    by_code = {f["code"]: f for f in flags}
    assert by_code["NORM_FACULTY_SHORTFALL"]["feature"] == 1 and by_code["NORM_FACULTY_SHORTFALL"]["feature_label"] == "Handbook rule checker"
    assert by_code["MODIFIED_AFTER_SIGNING"]["feature"] == 2 and by_code["DUPLICATE_FACULTY_CROSS_INSTITUTION"]["feature_label"] == "Document & consistency check"
    assert {f["feature"] for f in flags} == {1, 2}
    stats = api.get("/api/v1/risk/stats", headers=off).json()["flags_by_feature"]
    assert set(stats) == {"Handbook rule checker", "Document & consistency check"} and sum(stats.values()) > 0


def test_course_and_intake_settings_are_validated_and_drive_the_norms(env):
    api, a = env["api"], env["login"]("inst-a@tatva.test")
    app_id = api.post("/api/v1/applications", json={"category": "EOA", "academic_year": "2028-29"}, headers=a).json()["id"]
    bad = [[], [{"course": "", "level": "UG", "intake": 60}], [{"course": "CSE", "level": "XX", "intake": 60}], [{"course": "CSE", "level": "UG", "intake": 0}], [{"course": "CSE", "level": "UG", "intake": "many"}]]
    for programmes in bad:
        assert api.patch(f"/api/v1/applications/{app_id}", json={"form": {"programmes": programmes}}, headers=a).status_code == 422
    ok = api.patch(f"/api/v1/applications/{app_id}", json={"form": {"programmes": [{"course": "Computer Science and Engineering", "level": "ug", "intake": 240, "duration": 4}]}}, headers=a)
    assert ok.status_code == 200
    p = ok.json()["form_data"]["programmes"][0]
    assert p["level"] == "UG" and p["divisions"] == 4 and p["programme"] == "ENGINEERING_AND_TECHNOLOGY"
    off = env["login"]("officer@tatva.test")
    assert api.post(f"/api/v1/applications/{app_id}/verify", headers=off).status_code == 200
    rules = api.get(f"/api/v1/applications/{app_id}/rule-results", headers=off).json()
    ratio = next(r for r in rules if r["rule_id"] == "FAC-UG-ENGG-RATIO")
    assert ratio["status"] == "FAIL"  # 240 seats x 4 years needs 48 faculty; the form still declares 26
