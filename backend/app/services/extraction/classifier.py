"""Document-type classification. Default: keyword rules on the text layer (title first, then body).
# ponytail: keyword rules cover the synthetic templates; FEATURE_LAYOUTLM swaps in a model later."""
DOC_TYPES = (
    "AFFIDAVIT_2", "TER_RECEIPT", "OCCUPANCY_CERTIFICATE", "STRUCTURAL_STABILITY_CERTIFICATE", "FIRE_SAFETY_CERTIFICATE",
    "SATELLITE_MAP", "AUDITED_ACCOUNTS", "LAND_DOCUMENT", "NOC_AFFILIATING_UNIVERSITY", "TRUST_RESOLUTION", "FACULTY_LIST", "INFRA_PHOTO",
)
# (doc_type, title keywords) - checked against the first lines of page 1
TITLE_RULES = [
    ("AFFIDAVIT_2", ("affidavit 2",)),
    ("TER_RECEIPT", ("payment receipt", "ter)")),
    ("OCCUPANCY_CERTIFICATE", ("occupancy certificate", "completion certificate", "building licence")),
    ("STRUCTURAL_STABILITY_CERTIFICATE", ("structural stability",)),
    ("FIRE_SAFETY_CERTIFICATE", ("fire and life safety", "fire safety")),
    ("SATELLITE_MAP", ("satellite map",)),
    ("AUDITED_ACCOUNTS", ("audited statement", "statement of accounts")),
    ("LAND_DOCUMENT", ("land ownership", "sale deed", "lease deed")),
    ("NOC_AFFILIATING_UNIVERSITY", ("no objection certificate", "affiliating university")),
    ("TRUST_RESOLUTION", ("trust resolution", "resolution of the")),
]
BODY_RULES = {
    "AFFIDAVIT_2": ("notar", "e-stamp"), "TER_RECEIPT": ("receipt no", "amount"), "OCCUPANCY_CERTIFICATE": ("occupancy", "completion date"),
    "FIRE_SAFETY_CERTIFICATE": ("fire", "valid till"), "SATELLITE_MAP": ("latitude", "longitude"), "AUDITED_ACCOUNTS": ("udin", "auditor"),
    "LAND_DOCUMENT": ("survey no", "registration"), "STRUCTURAL_STABILITY_CERTIFICATE": ("structural", "engineer"),
}


def classify(filename: str, text: str, content_type: str) -> tuple[str, float]:
    if content_type in ("image/jpeg", "image/png"):
        return "INFRA_PHOTO", 0.9
    if content_type == "text/csv":
        return "FACULTY_LIST", 0.9
    head = " ".join(text.lower().split("\n")[:3])
    for doc_type, kws in TITLE_RULES:
        if any(k in head for k in kws):
            return doc_type, 0.95
    low = text.lower()
    scored = sorted(((sum(k in low for k in kws) / len(kws), t) for t, kws in BODY_RULES.items()), reverse=True)
    if scored and scored[0][0] >= 1.0 and (len(scored) < 2 or scored[1][0] < 1.0):
        return scored[0][1], 0.6
    return "UNKNOWN", 0.0
