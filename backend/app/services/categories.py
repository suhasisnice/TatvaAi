"""Category -> required document checklist (categories.yaml equivalent).

Only EoA is wired for the demo; the pattern (document type, severity if
missing, citation) is the same one PramaanAI's full rule pack uses, just
trimmed to what the prototype needs today.
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

CATEGORIES = {
    "EOA": EOA_REQUIRED_DOCS,
}
