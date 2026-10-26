# Design decisions &mdash; lean demo build

The team guide (`PramaanAI_SIH26261_Team_Guide.pdf`) describes a much larger
target system: 5 engines, 53 Handbook rules, OCR/LayoutLMv3/YOLOv8/
face-recognition, PostGIS + satellite imagery, Celery/Redis, a full PKI with
pyHanko DSC signing, 19 database tables, a hash-chained audit log. That is
weeks of work. This build keeps the same architecture and the same tech
stack (React/Vite/FastAPI/SQLAlchemy) but trims the implementation so a
working, demoable prototype exists today. Every trim below is a scope cut,
not a silent shortcut &mdash; this file says so, and the roadmap says what to
add first.

## What's real (not stubbed)
- Full auth (bcrypt + JWT), 4 roles, role-scoped data access.
- A real document pipeline: upload &rarr; PDF text extraction (pypdf) &rarr;
  classification &rarr; field extraction &rarr; 5 engines &rarr; flags &rarr;
  GREEN/AMBER/RED scoring, same severity weights and thresholds as the guide
  (CRITICAL 40 / MAJOR 15 / MINOR 5 / INFO 0; RED on any CRITICAL or score
  &ge;60; AMBER on any MAJOR or score &ge;20).
- Real SHA-256 integrity checks (a tampered document's hash genuinely no
  longer matches the issuer's registered hash &mdash; this is how
  `MODIFIED_AFTER_SIGNING` is detected, not a hardcoded flag).
- Real perceptual-hash photo-duplicate detection (Pillow + imagehash) across
  institutions &mdash; the planted "Chandra reused Aurora's lab photo" case is
  caught by an actual image comparison, not a lookup table.
- A real hash-chained audit log (`app/services/audit.py`).
- Flag fingerprinting + upsert on re-run, so officer decisions survive a
  re-validation, matching the guide's behaviour.
- Mandatory reason (&ge;5 chars) on every accept/dismiss and manual
  verification; no reject/approve endpoint exists anywhere.

## What's simplified, and why
- **No real PKI / pyHanko DSC signing.** A full certificate authority +
  per-document signing pipeline was out of scope for one session. Documents
  carry a `Digitally Signed By:` text marker instead, and "signature
  validity" is simulated by comparing the file's SHA-256 against the hash
  the mock issuer registered at signing time. This preserves the property
  being demonstrated (any post-signing edit is detectable) without the PKI
  machinery. **Upgrade path:** `scripts/make_test_pki.py` + pyHanko, as in
  the guide.
- **No OCR/LayoutLM/YOLO/face-recognition.** All demo documents have a text
  layer (pypdf reads it directly), so OCR was never required for the demo
  to work; the heavier models stay on the roadmap, exactly as the guide
  itself keeps them behind off-by-default feature flags.
- **No font/ELA image forensics.** `TAMPER_SUSPECTED` is a real flag, but
  instead of detecting a font mismatch from pixel data, the generator marks
  the tampered field with a `Tampered-Field:` line that the authenticity
  engine reads, carrying the same confidence/severity/corroboration logic
  the real detector would feed into. **Upgrade path:** font-cluster + ELA
  heatmap, as in the guide's `authenticity.py`.
- **No satellite imagery / PostGIS.** Built-up-area plausibility is checked
  against a `footprint_estimate_m2` value seeded directly on the
  institution, instead of computing it from building footprints &times;
  floors via a geo dataset. `BUILDING_NOT_VISIBLE_ON_DATE` and photo-GPS
  checks are not implemented.
- **No mock-issuer microservice.** Issuer "ground truth" lives in an
  `IssuerRecord` table in the same database instead of a separate FastAPI
  service, to cut one moving part. The adapter pattern (one row per source,
  `available` flag, `expected_fields`) is the same shape, so splitting it
  out later is a refactor, not a redesign.
- **No Celery/Redis/nightly alerts.** The pipeline runs synchronously on
  upload/pre-check/submit; there's no background worker or alert bell.
- **3 synthetic institutions, EoA only.** The other 16 Chapter II categories
  and multi-year carry-forward are not wired.
- **SQLite, not PostgreSQL+PostGIS/MinIO.** `DATABASE_URL` is swappable.

## Immediate next steps if continuing past the demo
1. Swap the text-marker signing for real pyHanko DSC signing.
2. Add the font/ELA forensic detector for `TAMPER_SUSPECTED`.
3. Pull built-up-area and photo-GPS checks onto real geo data.
4. Split mock issuers into their own service (matches the guide's
   `mock_issuers/` design) so swapping in a real authorised API later is a
   config change, not a code change.
5. Add the alerts bell + nightly job, and the officer-side rule-pack editor (there is no admin role)
   (versioned YAML rules instead of the current Python `engines.py`).
