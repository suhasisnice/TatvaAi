"""Proves every planted issue is caught: runs the full pipeline on a fresh database and compares with expected_flags.json.

Usage: python scripts/verify_planted.py [--live-mock URL] [--keep-db PATH]
Exit code 0 only if every institution gets its expected tier, no planted flag is missed and carry-forward is as expected.
Unexpected flags are listed (informational)."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _harness import build_world  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--live-mock", help="base URL of a running mock-issuers service (default: in-process)")
ap.add_argument("--keep-db", help="write the SQLite database to this path instead of a temp dir")
args = ap.parse_args()
w = build_world(args.live_mock, args.keep_db)

from sqlalchemy import select  # noqa: E402

from app.models import Application, Document, Flag, Institution  # noqa: E402

expected = w["expected"]
ok = True
with w["db_factory"]() as db:
    print(f"\n{'Institution':<45} {'Expected':<9} {'Actual':<9} {'Caught':<8} {'Missed':<7} Unexpected flags (non-INFO / INFO)")
    for key in "abc":
        app = w["apps"][key, expected["academic_year"]]
        app = db.get(Application, app.id)
        inst = db.get(Institution, app.institution_id)
        flags = db.scalars(select(Flag).where(Flag.application_id == app.id)).all()
        codes = {f.code for f in flags}
        planted = [p["code"] for p in expected[key]["planted"]]
        missed = [c for c in planted if c not in codes]
        known = set(planted) | {o["code"] for o in expected[key]["optional"]}
        unexpected = [f for f in flags if f.code not in known]
        carried = sorted({d.doc_type for d in db.scalars(select(Document).where(Document.application_id == app.id)) if d.carried_forward_from})
        carry_ok = carried == sorted(expected[key]["carry_forward"])
        tier_ok = app.risk_tier == expected[key]["expected_tier"]
        ok &= tier_ok and not missed and carry_ok
        print(f"{inst.name:<45} {expected[key]['expected_tier']:<9} {str(app.risk_tier):<9} {len(planted) - len(missed)}/{len(planted):<6} {len(missed):<7} "
              f"{sum(f.severity != 'INFO' for f in unexpected)} / {sum(f.severity == 'INFO' for f in unexpected)}  {sorted({f.code for f in unexpected})}")
        if missed:
            print(f"   MISSED: {missed}")
        if not carry_ok:
            print(f"   CARRY-FORWARD expected {expected[key]['carry_forward']}, got {carried}")
        if not tier_ok:
            print(f"   TIER MISMATCH: score {app.risk_score}, reasons {[r['code'] for r in json.loads(app.risk_reasons or '[]')]}")
print("\nRESULT:", "PASS - every planted flag caught, tiers as expected" if ok else "FAIL")
sys.exit(0 if ok else 1)
