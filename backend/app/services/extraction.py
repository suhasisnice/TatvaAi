"""Document classification and field extraction.

Lazy-but-real: reads the PDF text layer with pypdf and parses "Label: Value"
lines. No OCR/layout model — our synthetic documents have a text layer, so
this mirrors PramaanAI's own text-layer path (OCR is optional there too).
"""
import hashlib
import re
from pathlib import Path

from pypdf import PdfReader

TITLE_KEYWORDS = {
    "AFFIDAVIT_2": ["affidavit 2", "affidavit-2"],
    "TER_RECEIPT": ["ter receipt", "payment receipt"],
    "OCCUPANCY_CERTIFICATE": ["occupancy certificate", "completion certificate"],
    "FIRE_SAFETY_CERTIFICATE": ["fire safety certificate", "fire and life safety"],
    "SATELLITE_MAP": ["satellite map"],
    "AUDITED_ACCOUNTS": ["audited statement", "statement of accounts"],
    "LAND_DOCUMENT": ["land ownership", "sale deed", "land record"],
    "AFFIDAVIT_8": ["affidavit 8", "affidavit-8"],
    "NOC_AFFILIATING_UNIVERSITY": ["no objection certificate", "affiliating university"],
    "TRUST_RESOLUTION": ["trust resolution", "resolution of the"],
}

LABEL_LINE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 /_-]{1,40}):\s*(.+?)\s*$")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix != ".pdf":
        return ""
    try:
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


def classify(filename: str, text: str) -> tuple[str, float]:
    haystack = (filename + "\n" + text).lower()
    first_lines = "\n".join(text.splitlines()[:3]).lower()
    for doc_type, keywords in TITLE_KEYWORDS.items():
        for kw in keywords:
            if kw in first_lines:
                return doc_type, 0.97
    for doc_type, keywords in TITLE_KEYWORDS.items():
        for kw in keywords:
            if kw in haystack:
                return doc_type, 0.65
    ext = Path(filename).suffix.lower()
    if ext == ".csv":
        return "FACULTY_LIST", 0.9
    if ext in (".jpg", ".jpeg", ".png"):
        return "INFRA_PHOTO", 0.9
    return "UNKNOWN", 0.3


def extract_fields(text: str) -> dict:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        m = LABEL_LINE.match(line)
        if not m:
            continue
        label = m.group(1).strip().lower().replace(" ", "_").replace("-", "_").replace("/", "_")
        value = m.group(2).strip()
        fields[label] = value
    return fields


def analyze(path: Path, filename: str) -> tuple[str, float, dict]:
    """Classify a stored upload and extract its fields, including real signature status."""
    from app.services import signature
    text = extract_text(path)
    doc_type, confidence = classify(filename, text)
    fields = extract_fields(text)
    sig = signature.inspect(path)
    fields["_sig"] = sig
    fields["_signed"] = sig["status"] != "UNSIGNED"
    fields["_signer"] = sig["signer"]
    marker = [ln for ln in text.splitlines() if ln.strip().lower().startswith("tampered-field:")]
    if marker:
        fields["_tampered_field"] = marker[0].split(":", 1)[1].strip()
    return doc_type, confidence, fields
