"""Authenticity: proof before prediction.
1. Cryptographic: PDF signature intact/valid/trusted, not modified after signing, QR payload matches printed fields.
2. Forensics (Error Level Analysis heatmap, font inconsistency inside field regions, metadata anomalies); they add weight only where
   step 1 could not prove authenticity. Proof level per document: CRYPTOGRAPHIC | ISSUER_VERIFIED | FORENSIC_ONLY.
# ponytail: copy-move (ORB) and the DocTamper model are optional (FEATURE_DTD) and not wired; add behind the flag if needed."""
import io
import json
import re
from collections import Counter
from datetime import date

import cv2
import numpy as np
import pymupdf
from sqlalchemy import select

from app.core import storage
from app.models import DocumentPage, Verification
from app.services.extraction.fields import extract_pdf_fields
from app.services.extraction.signature import signed_revision
from app.services.optional import count_pcs
from app.services.engines.common import Run, make_flag

QR_MAP = {  # QR payload key -> printed field
    "OCCUPANCY_CERTIFICATE": {"no": "certificate_no", "type": "certificate_type", "issued": "issue_date"},
    "FIRE_SAFETY_CERTIFICATE": {"no": "certificate_no", "issued": "issue_date", "valid_till": "valid_till"},
}
EDITORS = ("photoshop", "gimp", "acrobat", "foxit", "pdf-xchange", "pymupdf", "lightroom", "snapseed", "canva", "paint")
CRYPTO_FAILURES = ("SIGNATURE_INVALID", "MODIFIED_AFTER_SIGNING", "QR_MISMATCH")


def ela(image_png_or_jpg: bytes, quality: int = 90) -> tuple[bytes, np.ndarray]:
    """Error Level Analysis: recompress and amplify the difference. Returns (heatmap PNG, grayscale error map)."""
    img = cv2.imdecode(np.frombuffer(image_png_or_jpg, np.uint8), cv2.IMREAD_COLOR)
    _, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    diff = cv2.absdiff(img, cv2.imdecode(enc, cv2.IMREAD_COLOR)).max(axis=2).astype(np.float32)
    norm = (diff / max(float(diff.max()), 1.0) * 255).astype(np.uint8)
    return cv2.imencode(".png", cv2.applyColorMap(norm, cv2.COLORMAP_JET))[1].tobytes(), diff


def font_findings(pdf: bytes, fields: list[dict]) -> list[dict]:
    """Fonts used by the value of each extracted field; a value in a font unlike the document's majority is suspicious."""
    d = pymupdf.open(stream=pdf, filetype="pdf")
    seen = []
    for f in fields:
        page = d[f["page"] - 1]
        w, h = page.rect.width, page.rect.height
        x0, y0, x1, y1 = f["bbox"]
        rect = pymupdf.Rect(x0 * w + 1, y0 * h + 1, x1 * w - 1, y1 * h - 1)
        fonts = {s["font"] for b in page.get_text("dict", clip=rect)["blocks"] if b["type"] == 0 for ln in b["lines"] for s in ln["spans"] if s["text"].strip()}
        if fonts:
            seen.append((f, sorted(fonts)[0]))
    if not seen:
        return []
    modal = Counter(font for _, font in seen).most_common(1)[0][0]
    return [dict(field=f["field"], font=font, expected_font=modal, page=f["page"], bbox=f["bbox"]) for f, font in seen if font != modal]


def _pdf_date(s: str | None) -> str | None:
    m = re.match(r"D:(\d{4})(\d{2})(\d{2})", s or "")
    return f"{m[1]}-{m[2]}-{m[3]}" if m else None


def metadata_findings(info: dict, signed_at: str | None) -> list[str]:
    meta, out = info.get("pdf_meta") or {}, []
    mod, created, producer = _pdf_date(meta.get("modDate")), _pdf_date(meta.get("creationDate")), (meta.get("producer") or "").lower()
    if signed_at:
        s = signed_at[:10]
        if mod and (date.fromisoformat(mod) - date.fromisoformat(s)).days > 1:
            out.append(f"Document metadata was modified on {mod}, after it was signed on {s}")
        if created and created > s:
            out.append(f"Document was created on {created}, after it was signed on {s}")
    if any(e in producer for e in EDITORS if e != "pymupdf"):
        out.append(f"Produced by editing software ({meta.get('producer')})")
    return out


def _changed_after_signing(r: Run, d) -> list[dict]:
    """Fields whose value in the signed revision differs from the current file."""
    try:
        rev = signed_revision(storage.get(d.storage_key))
        old = {f["name"]: f["value"] for f in extract_pdf_fields(pymupdf.open(stream=rev, filetype="pdf")) if f["value"] is not None}
    except Exception:
        return []
    return [dict(field=n, before=v, after=r.ev.value(d.id, n)) for n, v in old.items() if r.ev.value(d.id, n) is not None and r.ev.value(d.id, n) != v]


def run(r: Run) -> list[dict]:
    flags = []
    verified_docs = {v.document_id for v in r.db.query(Verification).filter_by(application_id=r.app.id, status="VERIFIED").all()}
    for d in r.ev.docs:
        forensics, doc_flags, crypto_ok = {}, [], False
        if d.content_type == "application/pdf":
            info = json.loads(d.dsc_info or "{}")
            sig = (info.get("signatures") or [{}])[0]
            if d.dsc_status == "SIGNED_INVALID":
                doc_flags.append(make_flag("authenticity", "SIGNATURE_INVALID", "CRITICAL", f"The digital signature on {d.doc_type} is invalid or the document was altered",
                                           [r.ev.doc(d.id)], explanation=sig.get("error", "Signature validation failed."), document_id=d.id))
            elif d.dsc_status == "SIGNED_UNTRUSTED":
                doc_flags.append(make_flag("authenticity", "SIGNATURE_INVALID", "MAJOR", f"The signer of {d.doc_type} is not trusted by the test CA",
                                           [r.ev.doc(d.id)], explanation=f"Signer: {sig.get('signer')}", document_id=d.id))
            elif d.dsc_status == "SIGNED_MODIFIED":
                changed = _changed_after_signing(r, d)
                what = "; ".join(f"{c['field']} was {c['before']!r} when signed, now {c['after']!r}" for c in changed)
                doc_flags.append(make_flag("authenticity", "MODIFIED_AFTER_SIGNING", "CRITICAL",
                                           f"{d.doc_type} was changed after it was digitally signed (signed {str(sig.get('signed_at'))[:10]})" + (f": {what}" if what else ""),
                                           [dict(r.ev.field(d.id, c["field"]), before=c["before"]) for c in changed] or [r.ev.doc(d.id)],
                                           explanation=f"Signature covers {sig.get('coverage')}; a later revision changed the content (modification level {sig.get('modification_level')}). "
                                           "The signed revision was re-read and compared field by field with the current file.", document_id=d.id))
            qr_bad = False
            if d.qr_payload and d.doc_type in QR_MAP:
                try:
                    payload = json.loads(d.qr_payload)
                except ValueError:
                    payload = {}
                for k, fname in QR_MAP[d.doc_type].items():
                    printed = r.ev.value(d.id, fname)
                    if payload.get(k) != printed:
                        qr_bad = True
                        doc_flags.append(make_flag("authenticity", "QR_MISMATCH", "MAJOR",
                                                   f"QR code on {d.doc_type} says {fname.replace('_', ' ')} {payload.get(k)!r}, but the printed text says {printed!r}",
                                                   [r.ev.field(d.id, fname), {"document_id": d.id, "page": 1, "bbox": None, "field": "qr_code", "value": d.qr_payload}],
                                                   explanation="The QR payload is machine-readable issuer data; a different printed value suggests the text was changed.", document_id=d.id, key=fname))
            crypto_ok = d.dsc_status == "SIGNED_VALID" and not qr_bad
            # --- step 2: forensics
            fields = [r.ev.field(d.id, n) for (did, n), f in r.ev._fields.items() if did == d.id and f.x0 is not None and f.page]
            odd = font_findings(storage.get(d.storage_key), fields)
            meta = metadata_findings(info, sig.get("signed_at"))
            page1 = r.db.scalar(select(DocumentPage).where(DocumentPage.document_id == d.id, DocumentPage.page_no == 1))
            if page1:
                heat, err = ela(storage.get(page1.image_key))
                key = f"forensics/{r.app.id}/{d.id}/ela_p1.png"
                storage.put(key, heat)
                forensics.update(ela_key=key, ela_mean=round(float(err.mean()), 4))
            forensics.update(font_findings=odd, metadata_findings=meta)
            corroborated = any(f["code"] in CRYPTO_FAILURES for f in doc_flags) or any(
                v["document_id"] == d.id and v["status"] == "MISMATCH_DETECTED" for v in r.verifs)
            proof = "ISSUER_VERIFIED" if crypto_ok and d.id in verified_docs else "CRYPTOGRAPHIC" if crypto_ok else "FORENSIC_ONLY"
            weight = {"FORENSIC_ONLY": "MAJOR", "CRYPTOGRAPHIC": "MINOR", "ISSUER_VERIFIED": "INFO"}[proof]
            if odd:
                ev = [dict(r.ev.field(d.id, o["field"]), font=o["font"]) for o in odd]
                if forensics.get("ela_key"):
                    ev.append(dict(r.ev.doc(d.id), artifact="ela_heatmap", artifact_key=forensics["ela_key"]))
                doc_flags.append(make_flag("authenticity", "TAMPER_SUSPECTED", "CRITICAL" if corroborated else weight,
                                           f"{d.doc_type}: {', '.join(o['field'] for o in odd)} is in a different font ({odd[0]['font']}) from the rest of the document ({odd[0]['expected_font']})",
                                           ev, explanation="Inconsistent fonts inside a field region are a common sign of text edited after the document was produced. "
                                           + ("Corroborated by a cryptographic or issuer failure on the same document." if corroborated else f"Proof level {proof}, so this finding is weighted {weight}."),
                                           confidence=min(0.95, 0.6 + 0.15 * len(odd)), document_id=d.id, forensic=True))
            for m in meta:
                doc_flags.append(make_flag("authenticity", "METADATA_ANOMALY", "MINOR" if proof == "FORENSIC_ONLY" else "INFO", m, [r.ev.doc(d.id)],
                                           confidence=0.5, document_id=d.id, forensic=True, key=m[:30]))
        elif d.content_type in ("image/jpeg", "image/png"):
            proof = "FORENSIC_ONLY"
            heat, err = ela(storage.get(d.storage_key))
            key = f"forensics/{r.app.id}/{d.id}/ela_p1.png"
            storage.put(key, heat)
            forensics.update(ela_key=key, ela_mean=round(float(err.mean()), 4))
            pcs = count_pcs(storage.get(d.storage_key)) if d.filename.startswith("lab") else None  # FEATURE_YOLO (off by default)
            if pcs is not None:
                forensics["yolo_pc_count"] = pcs
                declared = r.ctx.get("pcs")
                if declared is not None and pcs > declared:
                    doc_flags.append(make_flag("authenticity", "METADATA_ANOMALY", "MINOR", f"Lab photo {d.filename} shows {pcs} computers, more than the {declared} declared in total",
                                               [r.ev.doc(d.id)], confidence=0.5, document_id=d.id, forensic=True, key="yolo"))
            soft = (r.ev.value(d.id, "software") or "").lower()
            if any(e in soft for e in EDITORS):
                doc_flags.append(make_flag("authenticity", "METADATA_ANOMALY", "MINOR", f"Photo was saved by editing software ({r.ev.value(d.id, 'software')})",
                                           [r.ev.doc(d.id)], confidence=0.6, document_id=d.id, forensic=True))
        else:
            continue
        d.proof_level, d.forensics = proof, json.dumps(forensics)
        flags += doc_flags
    r.db.commit()
    return flags
