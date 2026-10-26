# TatvaAI: feature list in simple words

## What the project does
Every year, colleges ask AICTE to renew their approval. They upload documents like fire safety and land certificates. Officers check them by hand, which is slow, and fake or expired papers can slip through.

TatvaAI reads those documents, checks them, and warns the officer about problems. It shows proof for every warning. It gives each college a risk colour: GREEN (no risk), AMBER (medium risk) or RED (high risk). It also makes a list of which colleges inspectors should visit first.

**The software never approves or rejects anyone. A human officer decides, and must write a reason.**

Status words: **Done** = works for real. **Fake for now** = the screen can be built, but the data is made up. **To build** = not started.

---

## 1. For the college
| Feature | What it means | Status |
|---|---|---|
| Login | Each person signs in as college, officer or inspector | Done |
| Start an application | Pick the year and type (renewal, more seats, name change) | Done |
| Upload documents | PDFs, photos and the faculty list are accepted and safety-checked | Done |
| Recognise documents | The system says what each file is, like "fire certificate, 97% sure" | Done |
| Pre-check | A plain to-do list of what to fix before submitting | Done |
| Submit | Locks the application; the officer can reopen it once | Done |

## 2. Reading the documents
| Feature | What it means | Status |
|---|---|---|
| Read the fields | Finds each value (dates, numbers, names) and remembers where it sits on the page | Done |
| Check digital signatures | Sees if a document was changed after it was signed, and shows what changed | Done |
| Read QR codes | Compares the QR with the printed text | Done |
| Read photo details | Where and when a photo was taken | Done |
| Read the faculty list | Turns the spreadsheet into records | Done |

## 3. Checking with the original source
| Feature | What it means | Status |
|---|---|---|
| Fake government sources | Pretend e-stamp, DigiLocker, CA, fire, building and AICTE systems | Done |
| Ask the source | Ask the right source if each document is real | Done |
| Six answers | Verified, mismatch, expired, pending, source down, needs manual check | Done |
| Source is down | The case goes to a person instead of getting stuck | Done |
| Reuse last year | A document already verified last year is not checked again | Done |

## 4. The five checkers (they raise warnings, called flags)
| Checker | What it looks for | Status |
|---|---|---|
| Source checker | Source says the document is fake, expired or unreachable | Done |
| Authenticity checker | Edited after signing, QR mismatch, copied documents | Done |
| Completeness checker | Missing, unsigned or expired documents and fields | Done |
| Consistency checker | The same fact disagrees between documents, years or the college website | Done |
| Rules checker | Not enough teachers, rooms, computers or building area; photos taken far from the campus | Done |

Every warning has a plain message, the proof it is based on, and the Handbook clause where it applies.

## 5. Rules, risk and inspections
| Feature | What it means | Status |
|---|---|---|
| Rules in a file | AICTE norms are kept in editable files, not hidden in code | Done |
| Evidence collection | All facts gathered with where each came from | Done |
| Risk score and colour | Warnings add up to GREEN, AMBER or RED | Done |
| Inspection list | RED colleges ranked, with reasons and an on-site checklist | Done |
| Rule editor for the officer | Test a rule change before turning it on | Done |

## 6. Officer and inspector screens
| Feature | What it means | Status |
|---|---|---|
| Review queue | All colleges, highest risk first | Done |
| Review page | Summary, warnings with proof, verification, rules, map | Done |
| Show the proof | Opens the document page with the exact spot highlighted | Done |
| Accept or dismiss | Officer decides each warning and must write a reason; there is no reject button | Done |
| Alerts | Missing info, expiring documents, suspicious findings | Done |
| PDF report | A full report with the proof images | Done |

## 7. Safety and trust
| Feature | What it means | Status |
|---|---|---|
| Each user sees only their data | Colleges see only their own application | Done |
| Tamper-proof history | Every action is logged in a chain that shows if anyone altered it | Done |
| Document viewing log | Who opened which document | Done |
| Extra login step | Code from a phone app, for officers | Done |
| Only invented data | All names, colleges and sources are fake and labelled | Done |

---

## What exists today
Everything above is built and covered by the automated tests (backend suite plus the frontend build and smoke test), working against three made-up colleges: A is clean, B has two problems, C has many hidden ones (a land record edited after signing, 12 duplicate teachers, a copied photo).

The inspector now has a per-document on-site checklist: for every flagged item they record **Confirmed** (the issue is real) or **Cleared** (false alarm) with a written note, and a progress bar shows how much of the visit is done. This is separate from the officer's earlier accept/dismiss screening.

Optional extras stay switched off by default (scanned-page OCR, PC counting in lab photos, a local model that drafts rules). All sources are fake and labelled MOCK.
