"""Anchor-based field extraction from the PDF text layer: 'Label:' span + value span(s) on the same line.
Every field carries page number and a normalised (0-1) bounding box. No text layer -> OCR (FEATURE_OCR) or MANUAL_REVIEW_REQUIRED."""
import re

import pymupdf

from app.core.feature_flags import enabled

# label -> field name; unknown labels fall back to snake_case
LABELS = {
    "Institution": "institution_name", "Trust/Society": "trust_name", "Notary": "notary_name", "Signatory": "signatory_name",
    "Designation": "signatory_designation", "E-Stamp Certificate No": "estamp_cert_no", "E-Stamp Value (Rs)": "estamp_value",
    "E-Stamp Issue Date": "estamp_issue_date", "Entity": "entity_name", "Chartered Accountant": "ca_name", "Firm": "firm_name",
    "Total Income (Rs)": "total_income", "Owner": "owner_name", "Area (acres)": "area_acres", "Built-up Area (sq m)": "built_up_area_m2",
    "Building": "building_name", "Structural Engineer": "engineer_name", "Marked Location": "location_label", "Imagery Date": "capture_date",
    "Amount (Rs)": "amount", "AICTE ID": "aicte_id", "DigiLocker URI": "digilocker_uri",
}


def field_name(label: str) -> str:
    return LABELS.get(label) or re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def page_text(page: pymupdf.Page) -> str:
    return page.get_text("text")


def extract_from_spans(spans: list[dict], w: float, h: float, pno: int, confidence: float = 0.99) -> list[dict]:
    """Anchor logic shared by the text-layer and OCR paths: a 'Label:' span followed by value span(s) on the same line."""
    out = []
    for lab in (s for s in spans if s["text"].strip().endswith(":")):
        lx0, ly0, lx1, ly1 = lab["bbox"]
        vals = [s for s in spans if s is not lab and s["bbox"][0] >= lx1 - 1 and min(ly1, s["bbox"][3]) - max(ly0, s["bbox"][1]) > 0.5 * (ly1 - ly0)]
        if not vals:
            continue
        vals.sort(key=lambda s: s["bbox"][0])
        box = (vals[0]["bbox"][0], min(s["bbox"][1] for s in vals), max(s["bbox"][2] for s in vals), max(s["bbox"][3] for s in vals))
        out.append(dict(name=field_name(lab["text"].strip()[:-1]), value=" ".join(s["text"].strip() for s in vals), confidence=confidence,
                        status="EXTRACTED", page=pno, bbox=(box[0] / w, box[1] / h, box[2] / w, box[3] / h)))
    return out


def extract_pdf_fields(doc: pymupdf.Document, ocr=None) -> list[dict]:
    """ocr: optional callable(png_bytes, width_pt, height_pt) -> spans, used only for pages without a text layer (FEATURE_OCR)."""
    out = []
    for pno, page in enumerate(doc, start=1):
        w, h = page.rect.width, page.rect.height
        spans = [s | {"bbox": tuple(s["bbox"])} for b in page.get_text("dict")["blocks"] if b["type"] == 0
                 for ln in b["lines"] for s in ln["spans"] if s["text"].strip()]
        conf = 0.99
        if not spans and ocr:
            spans, conf = ocr(page.get_pixmap(dpi=150).tobytes("png"), w, h) or [], 0.85  # OCR is less certain than a text layer
        if not spans:
            out.append(dict(name="_page_text", value=None, confidence=0.0, status="MANUAL_REVIEW_REQUIRED", page=pno, bbox=None))
            continue
        out += extract_from_spans(spans, w, h, pno, conf)
    return out
