"""Evaluation of the prototype against the synthetic ground truth. Writes reports/evaluation.md.

Metrics: document classification accuracy; field-level extraction precision/recall/F1; planted-anomaly recall and precision;
tier accuracy; source-verification rate (share of automatic checks reaching a definitive status); average pipeline time per application.
Usage: python scripts/evaluate.py [--live-mock URL] [--out reports/evaluation.md]"""
import argparse
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _harness import ROOT, build_world  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--live-mock")
ap.add_argument("--out", default=str(ROOT / "reports/evaluation.md"))
args = ap.parse_args()
w = build_world(args.live_mock)

from sqlalchemy import select  # noqa: E402

from app.models import Application, Document, ExtractedField, Flag, Verification  # noqa: E402

DEFINITIVE = {"VERIFIED", "MISMATCH_DETECTED", "EXPIRED"}
prf = lambda tp, fp, fn: (tp / (tp + fp) if tp + fp else 1.0, tp / (tp + fn) if tp + fn else 1.0)
f1 = lambda p, r: 2 * p * r / (p + r) if p + r else 0.0

with w["db_factory"]() as db:
    # --- classification and field extraction (every PDF with ground-truth fields, all years)
    cls_ok = cls_n = 0
    tp = fp = fn = 0
    per_type: dict[str, list[int]] = {}
    for m in w["manifest"]["documents"]:
        app = w["apps"][m["institution"], m["academic_year"]]
        doc = db.scalar(select(Document).where(Document.application_id == app.id, Document.filename == Path(m["file"]).name))
        cls_n += 1
        cls_ok += doc.doc_type == m["doc_type"]
        got = {(f.name, f.value) for f in db.scalars(select(ExtractedField).where(ExtractedField.document_id == doc.id)) if not f.name.startswith("_")}
        truth = {(k, v["value"]) for k, v in m["fields"].items()}
        a, b, c = len(got & truth), len(got - truth), len(truth - got)
        tp, fp, fn = tp + a, fp + b, fn + c
        t = per_type.setdefault(m["doc_type"], [0, 0, 0])
        t[0] += a; t[1] += b; t[2] += c
    p, r = prf(tp, fp, fn)

    # --- planted anomalies (current academic year)
    ex = w["expected"]
    planted_total = caught = 0
    flagged_non_info = known_non_info = 0
    tier_ok = 0
    for key in "abc":
        app = w["apps"][key, ex["academic_year"]]
        app = db.get(Application, app.id)
        flags = db.scalars(select(Flag).where(Flag.application_id == app.id)).all()
        codes = {f.code for f in flags}
        planted = [x["code"] for x in ex[key]["planted"]]
        planted_total += len(planted)
        caught += sum(c in codes for c in planted)
        known = set(planted) | {o["code"] for o in ex[key]["optional"]}
        non_info = [f for f in flags if f.severity != "INFO"]
        flagged_non_info += len(non_info)
        known_non_info += sum(f.code in known for f in non_info)
        tier_ok += app.risk_tier == ex[key]["expected_tier"]
    a_recall = caught / planted_total
    a_precision = known_non_info / flagged_non_info if flagged_non_info else 1.0

    # --- source verification: automatic checks only (the auto-routed MANUAL_REVIEW_REQUIRED rows are follow-ups, not checks)
    vers = [v for v in db.scalars(select(Verification)) if v.status != "MANUAL_REVIEW_REQUIRED" or v.adapter == "manual"]
    auto = [v for v in vers if v.adapter != "manual" and v.carried_forward_from is None]
    by_status = Counter(v.status for v in auto)
    ver_rate = sum(by_status[s] for s in DEFINITIVE) / len(auto)

    times = list(w["timings"].values())

out = Path(args.out)
out.parent.mkdir(parents=True, exist_ok=True)
rows = "\n".join(f"| {t} | {a} | {b} | {c} | {prf(a, b, c)[0]:.3f} | {prf(a, b, c)[1]:.3f} |" for t, (a, b, c) in sorted(per_type.items()))
out.write_text(f"""# TatvaAI evaluation (synthetic ground truth)

Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} by `scripts/evaluate.py` on freshly generated data (seed 2026), rule pack v1, in-process mock issuers.
All numbers are measured on **synthetic** documents with known templates; they show the pipeline works end to end, not real-world accuracy.

| Metric | Result |
|---|---|
| Documents classified correctly | {cls_ok}/{cls_n} ({cls_ok / cls_n:.1%}) |
| Field extraction precision / recall / F1 | {p:.3f} / {r:.3f} / {f1(p, r):.3f} ({tp} correct, {fp} spurious, {fn} missed) |
| Planted-anomaly recall | {caught}/{planted_total} ({a_recall:.1%}) |
| Planted-anomaly precision (non-INFO flags that are planted or documented consequences) | {known_non_info}/{flagged_non_info} ({a_precision:.1%}) |
| Risk tier correct (A GREEN, B AMBER, C RED) | {tier_ok}/3 |
| Source-verification rate (automatic checks reaching VERIFIED / MISMATCH_DETECTED / EXPIRED) | {sum(by_status[s] for s in DEFINITIVE)}/{len(auto)} ({ver_rate:.1%}); statuses: {dict(by_status)} |
| Average pipeline time per application | {statistics.mean(times):.2f} s (min {min(times):.2f}, max {max(times):.2f}, {len(times)} applications) |

## Field extraction by document type

| Document type | Correct | Spurious | Missed | Precision | Recall |
|---|---|---|---|---|---|
{rows}

Notes: field ground truth comes from the generator's manifest; photos and the faculty CSV have no field ground truth and are excluded. Source unavailability (503 / no API) is planted on purpose and lowers the verification rate by design.
""", encoding="utf-8")
print(f"wrote {out}")
print(f"classification {cls_ok}/{cls_n}; fields P={p:.3f} R={r:.3f}; anomalies recall {a_recall:.2f} precision {a_precision:.2f}; verification rate {ver_rate:.2f}; mean time {statistics.mean(times):.2f}s")
sys.exit(0 if cls_ok == cls_n and a_recall == 1.0 and tier_ok == 3 else 1)
