"""Document intelligence: classify, extract fields (+page/bbox), decode QR, read signatures / EXIF. Synchronous in-process;
the Celery task in phase 6 simply calls process_document."""
import csv
import io
import json

import pymupdf
from PIL import Image
from sqlalchemy.orm import Session

from app.core import storage
from app.core.feature_flags import enabled
from app.models import Document, DocumentPage, ExtractedField, FacultyRecord
from app.services.extraction.classifier import classify
from app.services.extraction.fields import extract_pdf_fields
from app.services.optional import ocr_spans
from app.services.extraction.media import decode_qr, image_facts
from app.services.extraction.signature import signature_info

QR_TYPES = ("OCCUPANCY_CERTIFICATE", "FIRE_SAFETY_CERTIFICATE")


def _add_fields(db: Session, doc: Document, fields: list[dict]) -> None:
    for f in fields:
        b = f.get("bbox") or (None,) * 4
        db.add(ExtractedField(document_id=doc.id, name=f["name"], value=None if f["value"] is None else str(f["value"]), confidence=f["confidence"],
                              status=f["status"], page=f["page"], x0=b[0], y0=b[1], x1=b[2], y1=b[3]))


def process_document(db: Session, doc: Document, data: bytes, application) -> Document:
    """Fills doc (type, pages, fields, signature, QR). Caller commits."""
    if doc.content_type == "application/pdf":
        pdf = pymupdf.open(stream=data, filetype="pdf")
        text = "\n".join(p.get_text("text") for p in pdf)
        ocr = ocr_spans if enabled("ocr") else None  # FEATURE_OCR: scanned pages only; otherwise they stay MANUAL_REVIEW_REQUIRED
        fields = extract_pdf_fields(pdf, ocr)
        if not text.strip():  # scanned document: classify from the OCR output (title first, as for a text layer)
            text = "\n".join(f"{f['name']}: {f['value']}" for f in fields if f["value"])
        doc.doc_type, doc.classification_confidence = classify(doc.filename, text, doc.content_type)
        doc.page_count = len(pdf)
        first_png = None
        for n, page in enumerate(pdf, start=1):
            png = page.get_pixmap(dpi=150).tobytes("png")
            first_png = first_png or png
            key = f"documents/{doc.application_id}/{doc.id}/page_{n}.png"
            storage.put(key, png)
            db.add(DocumentPage(document_id=doc.id, page_no=n, width=page.rect.width, height=page.rect.height, image_key=key, has_text=bool(page.get_text("text").strip())))
        _add_fields(db, doc, fields)
        sig = signature_info(data)
        doc.dsc_status, doc.dsc_info = sig["status"], json.dumps(sig)
        if doc.doc_type in QR_TYPES:
            doc.qr_payload = decode_qr(first_png)
    elif doc.content_type in ("image/jpeg", "image/png"):
        doc.doc_type, doc.classification_confidence = classify(doc.filename, "", doc.content_type)
        img = Image.open(io.BytesIO(data))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        key = f"documents/{doc.application_id}/{doc.id}/page_1.png"
        storage.put(key, buf.getvalue())
        doc.page_count = 1
        db.add(DocumentPage(document_id=doc.id, page_no=1, width=img.width, height=img.height, image_key=key, has_text=False))
        _add_fields(db, doc, [dict(name=k, value=v, confidence=0.99, status="EXTRACTED", page=1, bbox=None) for k, v in image_facts(data).items()])
        doc.dsc_status = "UNSIGNED"
    else:  # CSV faculty list
        doc.doc_type, doc.classification_confidence = classify(doc.filename, "", doc.content_type)
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
        for r in rows:
            db.add(FacultyRecord(application_id=doc.application_id, institution_id=application.institution_id, faculty_id=r["faculty_id"],
                                 national_id_hash=r["national_id_hash"], name=r["name"], designation=r["designation"], qualification=r["qualification"],
                                 full_time=r["full_time"].upper().startswith("Y"), joined_date=r["joined_date"], department=r["department"]))
        _add_fields(db, doc, [dict(name="row_count", value=len(rows), confidence=1.0, status="EXTRACTED", page=None, bbox=None)])
    return doc
