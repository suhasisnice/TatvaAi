# PLAN

Folder tree: see the brief, section 4 (followed as written; `reports/` is created at runtime).

- [ ] **1. Foundations** — layout, compose, FastAPI + 10 routers, Alembic, auth/roles/MFA, React shell
  - [x] Backend skeleton, 10 routers, auth + MFA, institution isolation, tests
  - [x] Alembic initial migration, Dockerfiles, compose, seed script
  - [x] Frontend login + role routing (build + smoke test pass)
  - [ ] `docker compose up` verified end to end (compose file validates with `docker compose config`; the daemon was not available on the dev machine, so the user verifies it separately)
- [x] **2. Synthetic data** — deterministic PKI, generator (67 files, same sha256 on two runs), mock issuers service, expected_flags.json; tests in tests/test_synthetic.py, tests/test_mock_issuers.py
- [x] **3. Ingestion + extraction** — upload/hash/render, classifier, anchor extraction with page+bbox, QR, pyHanko signature status, EXIF + phash, faculty CSV; documents API; tests/test_extraction.py (every synthetic doc classified, every field matches ground truth)
- [x] **4. Evidence graph + Rule Pack** — facts with provenance, carry-forward, YAML loader + JSON schema + simpleeval evaluator, APH v1 and v2-demo packs, rulepack API (list/get/create/validate/activate; dry-run lands in phase 6); tests/test_rules.py, tests/test_evidence.py
- [x] **5. Engines** — issuer (six statuses, auto-routing to manual review), authenticity (cryptographic then forensic, proof levels, ELA heatmaps), completeness, consistency (rule-based, cross-year, cross-institution, disclosure), compliance + infrastructure evidence; pipeline runner with fingerprinted flag upsert; tests/test_engines.py
- [x] **6. Risk + workflow** — scoring/tiers/routing, queue, inspection list, flag decisions (reason mandatory), submit lock + reopen once, pre-check fix-list, alerts + nightly Celery job, rule-pack dry-run, manual verification; `scripts/verify_planted.py` passes (A GREEN, B AMBER, C RED, 0 missed); tests/test_workflow.py, tests/test_planted.py
- [x] **7. Audit + reports** — hash-chained audit log with verify/export, `scripts/tamper_audit_demo.py`, application report PDF (evidence thumbnails, citations, content hash in footer), inspection checklist PDF
- [x] **8. Frontend complete** — institution portal (form, upload, pre-check fix-list, submit lock), officer queue (KPIs, charts, filters) + workbench (Summary, Flags & Evidence with react-pdf bbox viewer + ELA toggle + decisions, Verification with six badges + manual confirmation, Compliance, Infrastructure map/gallery/duplicates, Timeline, Audit), inspections + PDF, inspector view with per-document on-site verdicts, officer rule packs (YAML editor, inline validation, dry-run diff, activate), audit chain banner, alerts bell, MFA setup. Walked through in the browser against the seeded data; Vitest smoke tests.
- [x] **9. Evaluation + polish** — `scripts/evaluate.py` -> `reports/evaluation.md`, CI workflow, Makefile + PowerShell commands, README (setup, architecture, demo script, limits), optional features (OCR/YOLO/LLM hooks), migrations tested against the models
