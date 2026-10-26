# TatvaAI: feature list in simple words

Follows the [feature map](docs/FEATURE_MAP.md).

## What the project does
Every year, colleges ask AICTE to renew their approval. They upload documents like fire safety and land certificates. Officers check them by hand, which is slow, and fake or expired papers can slip through.

TatvaAI reads those documents, checks them, and warns the officer about problems. It shows proof for every warning. It gives each college a risk colour: GREEN (no risk), AMBER (medium risk) or RED (high risk). It also makes a list of which colleges inspectors should visit first.

**The software never approves or rejects anyone. A human officer decides, and must write a reason.**

Status words: **Done** = works for real and is covered by tests.

## The three main features

### Feature 1: Handbook rule checker
| Feature | What it means | Status |
|---|---|---|
| Teachers, rooms, computers, bandwidth | Checked against the AICTE Handbook numbers | Done |
| Built-up area | Declared building area compared with the buildings on the map | Done |
| Certificate dates | Expired certificates, or ones that run out before the academic year starts | Done |
| Clause and page on every warning | Each warning says which Handbook rule it comes from | Done |
| Rules in files | The norms are editable files, not hidden in code | Done |

### Feature 2: Document & consistency check
| Feature | What it means | Status |
|---|---|---|
| Genuine document check | Sees if a document was changed after it was signed, and shows what changed; QR codes compared with the printed text | Done |
| Source check | Asks the issuing source (fake e-stamp, DigiLocker, CA, fire, building, AICTE systems, all labelled MOCK) if the document is real | Done |
| Six answers | Verified, mismatch, expired, pending, source down, needs manual check | Done |
| Facts agree | The same fact is compared across documents, years, colleges and the college website | Done |
| Ghost teachers | A teacher listed full-time at two colleges is caught | Done |
| Copied photos | Reused or far-away photos are caught | Done |

### Feature 3: Risk ranking & officer review
| Feature | What it means | Status |
|---|---|---|
| Risk score and colour | Warnings add up to GREEN, AMBER or RED | Done |
| Review queue | All colleges, highest risk first | Done |
| Review page | Summary, warnings with proof, verification, rules, map | Done |
| Accept or dismiss | The officer decides each warning and must write a reason; there is no reject button | Done |
| Decision support only | A banner on every officer and inspector page says so | Done |

## Smaller features that keep them working
| Feature | What it means | Status |
|---|---|---|
| Document sorter | Says what each file is ("fire certificate, 97% sure") and finds each field | Done |
| Last year's records | A document already verified last year is not checked again | Done |
| Course & intake settings | The college sets its courses and seats; the norms are worked out from them | Done |
| Evidence viewer | Opens the document page with the exact spot highlighted | Done |
| Plain-language reasons | Every warning has a message in simple words | Done |
| Rule versions with dry-run | Test a rule change on every application before turning it on | Done |
| Rule-draft helper | An AI drafts a rule from Handbook text; a human must approve it (off unless switched on) | Done |
| Audit log | Every decision is logged in a chain that shows if anyone altered it | Done |
| Fix-list before submit | The college sees what to fix, in plain words, before submitting | Done |
| Alerts, PDF report, phone-app login | Missing info and expiry alerts, a full report with proof images, a code from a phone app for officers | Done |

## What each person gets
- **The inspector:** a ranked list instead of random picks, and a PDF on-site checklist. On site, the inspector marks each flagged item **Confirmed** or **Cleared** with a note, and a progress bar shows how much of the visit is done.
- **The college:** a fix-list before it submits. A college only ever sees its own application.

## Why it is different
| | |
|---|---|
| U1 Explainable | Every warning cites its Handbook clause and page |
| U2 Cross-checking | Facts are checked across documents, years and colleges |
| U3 Human in control | Decision support only, never auto approve or reject |
| U4 Audit | Tamper-evident, hash-chained log of every decision |
| U5 Prevention | Colleges fix problems before they submit |
| U6 Targeting | Red, amber and green tiers send inspectors to the riskiest colleges first |
| U7 Maintainability | Rules update without redeploying: an AI drafts, a human approves, a dry-run shows the effect |

## What exists today
Everything above is built and covered by the automated tests (backend suite plus the frontend build and smoke test), working against three made-up colleges: A is clean, B has two problems, C has many hidden ones (a land record edited after signing, 12 duplicate teachers, a copied photo). Optional extras stay switched off by default (scanned-page OCR, PC counting in lab photos, the AI rule-draft helper). All sources are fake and labelled MOCK.
