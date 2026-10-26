# TatvaAI evaluation (synthetic ground truth)

Generated 2026-10-23 14:18 UTC by `scripts/evaluate.py` on freshly generated data (seed 2026), rule pack v1, in-process mock issuers.
All numbers are measured on **synthetic** documents with known templates; they show the pipeline works end to end, not real-world accuracy.

| Metric | Result |
|---|---|
| Documents classified correctly | 41/41 (100.0%) |
| Field extraction precision / recall / F1 | 1.000 / 1.000 / 1.000 (337 correct, 0 spurious, 0 missed) |
| Planted-anomaly recall | 15/15 (100.0%) |
| Planted-anomaly precision (non-INFO flags that are planted or documented consequences) | 16/16 (100.0%) |
| Risk tier correct (A GREEN, B AMBER, C RED) | 3/3 |
| Source-verification rate (automatic checks reaching VERIFIED / MISMATCH_DETECTED / EXPIRED) | 28/32 (87.5%); statuses: {'VERIFIED': 27, 'SOURCE_UNAVAILABLE': 4, 'MISMATCH_DETECTED': 1} |
| Average pipeline time per application | 4.85 s (min 4.15, max 5.45, 5 applications) |

## Field extraction by document type

| Document type | Correct | Spurious | Missed | Precision | Recall |
|---|---|---|---|---|---|
| AFFIDAVIT_2 | 55 | 0 | 0 | 1.000 | 1.000 |
| AUDITED_ACCOUNTS | 40 | 0 | 0 | 1.000 | 1.000 |
| FIRE_SAFETY_CERTIFICATE | 30 | 0 | 0 | 1.000 | 1.000 |
| LAND_DOCUMENT | 40 | 0 | 0 | 1.000 | 1.000 |
| OCCUPANCY_CERTIFICATE | 110 | 0 | 0 | 1.000 | 1.000 |
| SATELLITE_MAP | 25 | 0 | 0 | 1.000 | 1.000 |
| STRUCTURAL_STABILITY_CERTIFICATE | 7 | 0 | 0 | 1.000 | 1.000 |
| TER_RECEIPT | 30 | 0 | 0 | 1.000 | 1.000 |

Notes: field ground truth comes from the generator's manifest; photos and the faculty CSV have no field ground truth and are excluded. Source unavailability (503 / no API) is planted on purpose and lowers the verification rate by design.
