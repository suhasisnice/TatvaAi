"""Ingestion: validate type/size, store the original, hash it, then hand to document intelligence."""
import hashlib
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core import storage
from app.core.config import settings
from app.models import Application, Document
from app.services.audit import hash_chain as audit
from app.services.extraction.pipeline import process_document

ALLOWED = {"pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "csv": "text/csv"}
MAGIC = {"application/pdf": b"%PDF", "image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG"}


class UploadError(ValueError):
    pass


def check_upload(filename: str, data: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED:
        raise UploadError(f"File type .{ext} not allowed (PDF, JPG, PNG, CSV only)")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise UploadError(f"File larger than {settings.max_upload_mb} MB")
    ct = ALLOWED[ext]
    if ct in MAGIC and not data.startswith(MAGIC[ct]):
        raise UploadError("File content does not match its extension")
    if ct == "text/csv":
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise UploadError("CSV must be UTF-8 text")
    return ct


def ingest(db: Session, app: Application, filename: str, data: bytes, uploader_id: int | None) -> Document:
    ct = check_upload(filename, data)
    doc = Document(application_id=app.id, doc_type="UNKNOWN", filename=filename, content_type=ct, storage_key="", sha256=hashlib.sha256(data).hexdigest(),
                   size=len(data), uploaded_at=datetime.now(timezone.utc).replace(tzinfo=None), uploaded_by=uploader_id)
    db.add(doc)
    db.flush()
    doc.storage_key = f"documents/{app.id}/{doc.id}/original_{filename}"
    storage.put(doc.storage_key, data)
    process_document(db, doc, data, app)
    actor = f"user:{uploader_id}" if uploader_id else "system"
    audit.log(db, actor, "document.upload", f"document:{doc.id}", {"application_id": app.id, "filename": filename, "sha256": doc.sha256, "size": doc.size})
    audit.log(db, "system", "document.extract", f"document:{doc.id}", {"doc_type": doc.doc_type, "confidence": doc.classification_confidence, "dsc_status": doc.dsc_status,
                                                                      "pages": doc.page_count})
    db.commit()
    return doc
