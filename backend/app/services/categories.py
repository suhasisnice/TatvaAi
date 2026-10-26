"""Category -> required document checklist (categories.yaml equivalent).

Three of the Handbook's 17 Chapter II application types are wired. Adding
another is an entry here (title, whether the infrastructure/faculty norms
apply, and its documents with severity and citation); the completeness
engine and the UI both read this table.
"""

EOA_REQUIRED_DOCS = [
    ("AFFIDAVIT_2", "CRITICAL", "Annexure-2, 2.1 (i), p.81"),
    ("TER_RECEIPT", "CRITICAL", "Annexure-2, 2.1 (ii), p.81"),
    ("OCCUPANCY_CERTIFICATE", "CRITICAL", "Annexure-2, 2.1 (iii), p.81"),
    ("FIRE_SAFETY_CERTIFICATE", "CRITICAL", "Annexure-2, 2.1 (v), p.81"),
    ("SATELLITE_MAP", "MAJOR", "Annexure-2, 2.1 (vi), p.81"),
    ("AUDITED_ACCOUNTS", "MAJOR", "Annexure-2, 2.1 (vii), p.81"),
    ("FACULTY_LIST", "MAJOR", "Clause 6.14 (c), p.55"),
    ("INFRA_PHOTO", "MINOR", "Clause 1.9 (f)-(g), p.8"),
]

INCREASE_IN_INTAKE_REQUIRED_DOCS = EOA_REQUIRED_DOCS + [
    ("AFFIDAVIT_8", "CRITICAL", "Annexure-2, 2.6 (i), p.82"),
    ("TRUST_RESOLUTION", "CRITICAL", "Annexure-2, 2.6 (iii), Format 3, p.82"),
]

NAME_CHANGE_REQUIRED_DOCS = [
    ("NOC_AFFILIATING_UNIVERSITY", "CRITICAL", "Annexure-2, 2.10 (i), Format 2, p.83"),
    ("TRUST_RESOLUTION", "CRITICAL", "Annexure-2, 2.10 (ii), Format 3, p.83"),
]

CATEGORIES = {
    "EOA": EOA_REQUIRED_DOCS,
    "INCREASE_IN_INTAKE": INCREASE_IN_INTAKE_REQUIRED_DOCS,
    "NAME_CHANGE_INSTITUTION": NAME_CHANGE_REQUIRED_DOCS,
}

# norms=True: faculty / infrastructure / built-up norms apply (Table 2.3, p.30:
# a name change is scrutiny-only, so those checks are skipped for it).
CATEGORY_META = {
    "EOA": {"title": "Extension of Approval (self-disclosure)", "norms": True},
    "INCREASE_IN_INTAKE": {"title": "Increase in intake / additional courses", "norms": True},
    "NAME_CHANGE_INSTITUTION": {"title": "Change in name of the institution", "norms": False},
}


def applies_norms(category: str) -> bool:
    return CATEGORY_META.get(category, {}).get("norms", False)
