# TatvaAI (PramaanAI prototype) &mdash; SIH26261

AI-powered application validation, document authentication and regulatory
compliance verification for AICTE's Extension of Approval process.

Three core features, three dashboards:

1. **Document verification & authenticity** &mdash; signature/hash integrity
   checks, QR-vs-print consistency, mock issuer verification (SHCIL/DigiLocker/
   state portals), cross-document and cross-institution consistency.
2. **GREEN / AMBER / RED flagging** &mdash; every finding is evidence-linked and
   cites a Handbook clause; the officer accepts or dismisses with a reason.
   The software never approves or rejects &mdash; decision support only.
3. **Risk-targeted inspection list** &mdash; RED applications ranked by score
   with a concrete on-site checklist, replacing random EVC selection.

Dashboards: **Institution** (upload, pre-check, submit), **Officer**
(review queue, workbench, flag decisions, manual verification), **Inspector**
(risk-ranked inspection list with checklists).

## Status: lean demo build

This build trims the full target architecture (OCR/LayoutLM/YOLO/face-recognition,
PostGIS/satellite imagery, Celery/Redis, full PKI) down to what's needed for a
working, demoable prototype today, on the same stack (React/Vite + FastAPI/
SQLAlchemy). It keeps the five-engine, evidence-first, GREEN/AMBER/RED
architecture; see `DECISIONS.md` for exactly what was simplified and why, and
what the next pass should add.

## Running it

### Backend
```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m app.seed        # resets the DB and loads 3 demo institutions
.venv/Scripts/python -m uvicorn app.main:app --port 8011 --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173.

### Demo accounts (password `Pramaan@2026` for all)
| Role | Email |
|---|---|
| Institution (GREEN) | inst-aurora@pramaan.test |
| Institution (AMBER, left as draft) | inst-bhavani@pramaan.test |
| Institution (RED) | inst-chandra@pramaan.test |
| Officer | officer@pramaan.test |
| Inspector | inspector@pramaan.test |

Aurora and Chandra are pre-submitted so the officer/inspector queues show
GREEN and RED immediately. Bhavani is left as an editable draft so you can
run pre-check and submit live (AMBER, score 30) during a demo recording.

### Trying the other application types
Pick a category when starting a new application (Extension of Approval, Increase in intake, Change of
institution name). Sample documents for the last two are generated at
`backend/data/synthetic/aurora/` (`affidavit_8.pdf`, `trust_resolution.pdf`,
`noc_affiliating_university.pdf`); upload them as `inst-aurora@pramaan.test`.
