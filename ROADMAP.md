# TatvaAI / PramaanAI — 10-phase work plan

Starting point: the lean demo already pushed to the repo (3 dashboards, 5-engine
rule-based pipeline, GREEN/AMBER/RED scoring, inspector checklist, hash-chained
audit log). Each phase ends in something demoable. `DECISIONS.md` lists what the
demo simplified; this plan retires those simplifications in order of judge impact.

| # | Phase | Est. |
|---|-------|------|
| 1 | Officer audit log + chain verify + reopen-once | 1 day |
| 2 | Alerts bell + PDF validation report | 1 day |
| 3 | More categories + missing Handbook norms | 1–2 days |
| 4 | Real DSC signing (pyHanko test PKI) | 2 days |
| 5 | Real QR codes + font/ELA forensics | 2 days |
| 6 | Photo GPS + geo footprints + map tab | 2–3 days |
| 7 | Handbook-as-code: YAML rule packs | 2–3 days |
| 8 | Rule-pack screen (officer): validate, dry-run, activate | 1–2 days |
| 9 | Platform: mock-issuer service, Celery/Redis, Postgres, Docker | 3 days |
| 10 | Evaluation, tests, CI, demo hardening, docs | 2 days |

## Phase 1 — Officer audit log + chain verify + reopen-once
There is no admin role in this project: the roles are institution, officer and inspector only.
- New officer page `frontend/src/pages/officer/AuditLog.tsx` (route `/officer/audit`, nav link in `Shell.tsx`): log table, chain status, Verify again.
- Reuse `GET /api/v1/audit` and `/audit/verify` (`routers/audit_router.py`, officer-only).
- Reopen-once button on the officer Workbench, calling `POST /applications/{id}/reopen` (officer-only, refused the second time).
- Add `backend/scripts/tamper_audit_demo.py` (edit a row, restore with `--restore`).
- **Done when:** officer sees "Chain intact", tampers a row, sees "Broken at entry N"; reopening a submitted application works once.

## Phase 2 — Alerts bell + PDF validation report
- `alerts` writes in `services/pipeline.py` (MISSING_INFO, DOC_EXPIRING, ANOMALY); `GET /alerts`, mark-read; bell in `components/Shell.tsx`.
- `services/report.py` (reportlab, already installed) + `GET /applications/{id}/report.pdf`; button on officer Workbench.
- **Done when:** AMBER institution sees an alert; officer downloads a PDF listing flags, citations and decisions.

## Phase 3 — More categories + missing Handbook norms
- Extend `services/categories.py` with INCREASE_IN_INTAKE and NAME_CHANGE_INSTITUTION.
- Add missing checks to `services/engines.py`: cadre ratio, classrooms/labs, PC ratio, bandwidth.
- Add category selector on the institution "start application" screen.
- **Done when:** a name-change application shows its own checklist; seeded data still scores A=0, B=30, C=RED.

## Phase 4 — Real DSC signing
- Add `pyhanko`; `scripts/make_test_pki.py` (root CA + signer certs, deterministic).
- Sign PDFs in `services/generate_docs.py`; replace `extraction.signature_marker` with pyHanko validation → SIGNED_VALID / SIGNED_MODIFIED / UNSIGNED.
- Build Chandra's land record as a real incremental edit after signing.
- **Done when:** `MODIFIED_AFTER_SIGNING` fires from the real signature, and names the changed field.

## Phase 5 — Real QR codes + font/ELA forensics
- Generate real QR images on fire/occupancy certificates; decode with OpenCV `QRCodeDetector` (pyzbar optional, Windows DLL risk).
- Font-per-span detector replacing the `Tampered-Field:` marker; ELA heatmap endpoint (staff only) + viewer toggle.
- Keep forensic flags labelled "Preliminary indicator", weighted by confidence.
- **Done when:** hand-tamper a different field and it is still flagged with no code change.

## Phase 6 — Photo GPS + geo footprints + map tab
- Seed GeoJSON footprints (area, floors, first-seen year); EXIF GPS in photos.
- New flags in `compliance_engine`: PHOTO_GPS_OFFSITE (>1 km), BUILDING_NOT_VISIBLE_ON_DATE; replace scalar `footprint_estimate_m2`.
- Leaflet "Infrastructure" tab on Workbench (campus radius, footprints, photo markers).
- **Done when:** Chandra's off-site photo shows red on the map and raises the flag.

## Phase 7 — Handbook-as-code: YAML rule packs
- `rulepacks/<pack>/{documents,norms,timelines,risk}.yaml` + JSON schema; every rule carries clause + page.
- Evaluator using `simpleeval`; missing inputs → INSUFFICIENT_EVIDENCE, never a silent pass.
- Port rule-shaped checks out of `engines.py`; keep hash/photo-duplicate checks in Python.
- Move severity weights and tier thresholds into `risk.yaml`; store results with rule-pack version.
- **Done when:** results are identical to Phase 3 baseline, now rule-id + version stamped.

## Phase 8 — Rule-pack screen (officer): validate, dry-run, activate
- `rule_packs` table (draft → active → retired, immutable once saved).
- Officer-only screen: YAML editor, Validate, Dry-run (re-score all apps, write nothing), Activate with confirm.
- Ship a `v2-demo` pack (faculty ratio 1:18) to show Aurora GREEN → AMBER in dry-run.
- **Done when:** dry-run table shows tier/score before vs after; activation is audited.

## Phase 9 — Platform: services, queue, database
- Split IssuerRecord logic into a separate `mock_issuers/` FastAPI service with configurable base URL (adapters per source).
- Celery + Redis: background pre-check, nightly 02:00 expiry/pending alert job.
- PostgreSQL (+ PostGIS optional) via `DATABASE_URL`, Alembic migrations, MinIO storage option, `docker-compose.yml`, `.env.example`.
- Security pass: TOTP MFA (pyotp), document-access log, optional Fernet encryption at rest.
- **Done when:** `docker compose up` + seed runs the full demo.

## Phase 10 — Evaluation, tests, CI, demo hardening
- `scripts/verify_planted.py` (all planted problems caught, exit 1 otherwise) and `scripts/evaluate.py` (classification, extraction P/R/F1, tier accuracy, time per application → `reports/evaluation.md`).
- pytest suite for engines, scoring, rules, audit chain; frontend smoke tests; GitHub Actions CI.
- Update README, DECISIONS.md and a team guide; 5-minute demo script and Q&A notes; state clearly that all metrics are on synthetic data.
- **Done when:** CI green, fresh-clone-to-demo takes one command sequence.

## Dependencies and parallel work
- 1→2 sequential (shared officer/shell UI). 3 can start any time.
- 4→5 sequential (both touch extraction/authenticity). 6 is independent of 4–5.
- 7→8 sequential. 9 needs 7–8 stable. 10 runs continuously but closes last.
- Two-person split: A takes 4→5→6, B takes 1→2→3→7→8; both join for 9–10.
