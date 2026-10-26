import copy
from pathlib import Path

import pytest

from app.services.rules import evaluator as ev
from app.services.rules import loader

RP = Path(__file__).resolve().parents[1] / "rulepacks"


@pytest.fixture(scope="module")
def v1():
    return loader.load_dir(RP / "APH-2024-27-v1")


def rule(pack, rid):
    return next(r for r in pack["rules"] if r["id"] == rid)


def faculty_ctx(**kw):
    base = dict(sum_approved_intake_all_years=2400, avg_admitted_3yr=100, avg_sanctioned_3yr=120, valid_full_time_faculty=97)
    return {**base, **kw}


def test_packs_validate_and_have_citations(v1):
    assert loader.validate_pack(v1) == []
    assert loader.validate_pack(loader.load_dir(RP / "APH-2024-27-v2-demo")) == []
    assert all(r["citation"]["page"] for r in v1["rules"])
    ids = {r["id"] for r in v1["rules"]}
    assert {"FAC-UG-ENGG-RATIO", "DOC-EOA-AFFIDAVIT-2", "DOC-INCREASE-IN-INTAKE-AFFIDAVIT-8", "DOC-NAME-CHANGE-INSTITUTION-NOC-AFFILIATING-UNIVERSITY"} <= ids
    # inheritance: INCREASE_IN_INTAKE also requires the EoA documents
    assert "DOC-INCREASE-IN-INTAKE-FIRE-SAFETY-CERTIFICATE" in ids


def test_validation_reports_errors(v1):
    bad = copy.deepcopy(v1)
    bad["rules"][0].pop("citation")
    bad["rules"].append(dict(bad["rules"][1]))  # duplicate id
    bad["rules"][2]["check"] = "valid >= "
    errs = loader.validate_pack(bad)
    assert any("citation" in e for e in errs) and any("duplicate" in e for e in errs) and any("bad expression" in e for e in errs)


def test_faculty_ratio_c_example_from_brief(v1):
    r = ev.evaluate_formula(rule(v1, "FAC-UG-ENGG-RATIO"), faculty_ctx())
    assert r["status"] == "FAIL" and r["computed"]["required"] == 120
    assert "shortfall 23" in r["message"] and "required 120" in r["message"] and r["citation"]["page"] == 95


def test_faculty_relief_60_to_45(v1):
    # APH Annexure-5 p.96 example: requirement 60 falls to 45 when avg admissions <= 50% of sanctioned intake
    ctx = faculty_ctx(sum_approved_intake_all_years=1200, avg_admitted_3yr=50, avg_sanctioned_3yr=120, valid_full_time_faculty=45)
    r = ev.evaluate_formula(rule(v1, "FAC-UG-ENGG-RATIO"), ctx)
    assert r["computed"]["base_required"] == 60 and r["computed"]["relief"] == 0.25 and r["computed"]["required"] == 45 and r["status"] == "PASS"
    no_relief = ev.evaluate_formula(rule(v1, "FAC-UG-ENGG-RATIO"), {**ctx, "avg_admitted_3yr": 61})
    assert no_relief["computed"]["required"] == 60 and no_relief["status"] == "FAIL"


def test_missing_evidence_is_insufficient_not_fail(v1):
    ctx = faculty_ctx()
    del ctx["valid_full_time_faculty"]
    assert ev.evaluate_formula(rule(v1, "FAC-UG-ENGG-RATIO"), ctx)["status"] == "INSUFFICIENT_EVIDENCE"


def test_v2_demo_changes_ratio_only():
    v2 = loader.load_dir(RP / "APH-2024-27-v2-demo")
    r = ev.evaluate_formula(rule(v2, "FAC-UG-ENGG-RATIO"), faculty_ctx(sum_approved_intake_all_years=2400))
    assert r["computed"]["required"] == 134  # ceil(2400/18)
    assert ev.evaluate_formula(rule(v2, "FAC-PG-ENGG-RATIO"), faculty_ctx())["computed"]["base_required"] == 160  # PG unchanged (1:15)


def test_structural_certificate_only_if_building_older_than_30_years(v1):
    def ctx(age):
        return dict(category="EOA", docs={}, max_building_age_years=age, groups=[])

    def missing(age):
        out = ev.evaluate_pack(v1, ctx(age), only_types={"document_required"})
        return [r for r in out if r["rule_id"] == "DOC-EOA-STRUCTURAL-STABILITY-CERTIFICATE"]

    assert missing(30.5)[0]["status"] == "FAIL" and missing(30.5)[0]["details"]["problem"] == "missing"
    assert missing(29.9) == []  # rule not applicable


def test_document_requirements_and_expiry(v1):
    doc = dict(id=1, fields={"valid_till": "2027-06-30"}, checks={"dsc_valid": False})
    ctx = dict(category="EOA", docs={"FIRE_SAFETY_CERTIFICATE": [doc]}, academic_year_start="2027-08-01", submission_date="2027-03-01", groups=[], max_building_age_years=1)
    out = {r["rule_id"]: r for r in ev.evaluate_pack(v1, ctx)}
    assert out["DOC-EOA-FIRE-SAFETY-CERTIFICATE"]["details"]["code"] == "DOC_UNSIGNED"
    assert out["EXP-FIRE-AY"]["status"] == "FAIL" and out["EXP-FIRE-NOW"]["status"] == "PASS"


def test_name_normalisation_tolerates_case_and_abbreviation():
    assert ev.similarity("Aurora Institute of Technology (Synthetic)", "AURORA INSTITUTE OF TECHNOLOGY (SYNTHETIC)") == 1.0
    assert ev.similarity("Aurora Inst. of Tech.", "Aurora Institute of Technology") > 0.9
    assert ev.similarity("Aurora Institute", "Bhavani College") < 0.5


def test_no_eval_of_dangerous_expressions():
    r = dict(id="X", title="t", type="formula", severity="MAJOR", message="m", citation={}, check="__import__('os').system('echo hi')")
    assert ev.evaluate_formula(r, {})["status"] == "INSUFFICIENT_EVIDENCE"  # refused, not executed
