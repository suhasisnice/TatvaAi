# TatvaAI feature map (SIH26261, AICTE Regulation Bureau)

The product follows this map. Three main features turn a college's yearly application into a ranked list for inspectors; the smaller features keep each one working.

```
College uploads ─► Document sorter ─┬─► Feature 1  Handbook rule checker ───┐
 (fix-list before    (finds each    │                                        ├─► flag + evidence
  submit)             field)        └─► Feature 2  Document & consistency ───┘        │
                                                                                      ▼
   Inspector gets  ◄── Feature 3  Risk ranking & officer review  ◄── officer sees the flag, accepts or dismisses with a written reason
   ranked list + PDF       (GREEN / AMBER / RED)                       Decision support only: no approve / reject
   on-site checklist
```

## The three main features

| # | Feature | What it does | Where it lives |
|---|---|---|---|
| 1 | **Handbook rule checker** | Faculty, rooms, computers, bandwidth, built-up area and certificate dates against the Handbook. Every flag cites its clause and page. | engines `compliance` + `completeness`, rule pack `rulepacks/APH-2024-27-v1` |
| 2 | **Document & consistency check** | Is the document genuine, and do the facts agree across documents, years and colleges? Ghost faculty, expired or edited certificates. | engines `authenticity` + `issuer` + `consistency` |
| 3 | **Risk ranking & officer review** | GREEN / AMBER / RED tiers. The officer accepts or dismisses each flag with a written reason. No approve or reject authority. | `services/risk/`, officer queue and workbench |

Flags carry `feature` (1 or 2) and `feature_label`; the review screens filter and chart by feature. `backend/app/services/features.py` is the single mapping from engine to feature.

## Smaller features that support them

| Feature | Supports | Where |
|---|---|---|
| Document sorter: reads each upload and finds each field | 1 and 2 | `services/extraction/` |
| Issuer lookup (always labelled MOCK) | 2 | `services/engines/issuer.py`, `mock_issuers/` |
| Last year's records, reused (a verified, unchanged file is not re-checked) | 2 | `services/evidence/carry_forward.py` |
| Course & intake settings (the norms are calculated from them) | 1 | institution page, `PATCH /applications/{id}` with `programmes` |
| Evidence viewer (document page with the exact box highlighted) | 3 | officer workbench |
| Plain-language reasons | 3 | flag `message` + `explanation`, pre-check texts |
| Rule versions with dry-run | 1 (maintainability) | officer Rule packs screen |
| Rule-draft helper (an AI drafts, a human approves) | 1 (maintainability) | `POST /rulepacks/draft-from-text`, Rule packs screen; off unless `FEATURE_LLM=true` |
| Hash-chained audit log of every decision | 3 | officer Audit log screen |
| Fix-list before the college submits | prevention | institution pre-check |

## Outputs
- **Inspector:** a ranked list and a PDF on-site checklist (the inspector records Confirmed or Cleared with a note for each item).
- **College:** a fix-list before it submits.

## Unique value propositions

| | |
|---|---|
| U1 Explainable | Every flag cites its Handbook clause and page, so a finding can be checked in seconds and defended on appeal. No black-box score. |
| U2 Cross-checking | Facts are checked across documents, years and colleges: ghost faculty, edited or expired certificates, numbers that quietly change between filings. |
| U3 Human in control | Decision support only. The officer accepts or dismisses each flag with a written reason; nothing is auto-approved or auto-rejected. |
| U4 Audit | A tamper-evident, hash-chained log records every decision. |
| U5 Prevention | Colleges see their problems in plain reasons and fix them before submitting. |
| U6 Targeting | Red, amber and green tiers send inspectors to the riskiest colleges first, with a PDF and on-site checklist ready to carry. |
| U7 Maintainability | Rules update without redeploying: an AI drafts, a human approves, versions with dry-run show the effect before it goes live. |
