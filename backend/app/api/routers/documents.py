import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import storage
from app.core.db import get_db
from app.core.security import current_user, require_roles
from app.models import Application, Document, DocumentAccess, DocumentPage, ExtractedField, User
from app.services.ingestion.upload import UploadError, ingest

router = APIRouter(tags=["documents"])


def _app(db: Session, user: User, app_id: int) -> Application:
    a = db.get(Application, app_id)
    if not a or (user.role == "institution" and a.institution_id != user.institution_id):
        raise HTTPException(404, "Application not found")
    return a


def _doc(db: Session, user: User, doc_id: int) -> Document:
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "Document not found")
    _app(db, user, d.application_id)
    return d


def _log(db: Session, doc: Document, user: User, what: str) -> None:
    db.add(DocumentAccess(document_id=doc.id, user_id=user.id, at=datetime.now(timezone.utc).replace(tzinfo=None), what=what))
    db.commit()


def doc_out(d: Document) -> dict:
    return dict(id=d.id, application_id=d.application_id, doc_type=d.doc_type, classification_confidence=d.classification_confidence,
                filename=d.filename, content_type=d.content_type, sha256=d.sha256, size=d.size, page_count=d.page_count,
                uploaded_at=d.uploaded_at.isoformat(), dsc_status=d.dsc_status, dsc_info=json.loads(d.dsc_info) if d.dsc_info else None,
                qr_payload=d.qr_payload, carried_forward_from=d.carried_forward_from, proof_level=d.proof_level,
                has_ela=bool(d.forensics and json.loads(d.forensics).get("ela_key")))


@router.post("/applications/{app_id}/documents", status_code=201)
def upload(app_id: int, file: UploadFile, user: User = Depends(require_roles("institution")), db: Session = Depends(get_db)):
    # sync endpoint on purpose: pyHanko's sync validators cannot run inside the event loop
    a = _app(db, user, app_id)
    if a.locked:
        raise HTTPException(409, "Application is submitted and locked")
    try:
        return doc_out(ingest(db, a, file.filename or "upload", file.file.read(), user.id))
    except UploadError as e:
        raise HTTPException(422, str(e))


@router.get("/applications/{app_id}/documents")
def list_documents(app_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _app(db, user, app_id)
    return [doc_out(d) for d in db.scalars(select(Document).where(Document.application_id == app_id).order_by(Document.id))]


@router.get("/documents/{doc_id}")
def get_document(doc_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return doc_out(_doc(db, user, doc_id))


@router.get("/documents/{doc_id}/file")
def get_file(doc_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _doc(db, user, doc_id)
    _log(db, d, user, "file")
    return Response(storage.get(d.storage_key), media_type=d.content_type)


@router.get("/documents/{doc_id}/pages/{n}.png")
def get_page(doc_id: int, n: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _doc(db, user, doc_id)
    p = db.scalar(select(DocumentPage).where(DocumentPage.document_id == d.id, DocumentPage.page_no == n))
    if not p:
        raise HTTPException(404, "Page not found")
    _log(db, d, user, f"page{n}")
    return Response(storage.get(p.image_key), media_type="image/png")


@router.get("/documents/{doc_id}/forensics/ela.png")
def get_ela(doc_id: int, user: User = Depends(require_roles("officer", "inspector")), db: Session = Depends(get_db)):
    d = _doc(db, user, doc_id)
    key = (json.loads(d.forensics) if d.forensics else {}).get("ela_key")
    if not key:
        raise HTTPException(404, "No ELA heatmap for this document")
    _log(db, d, user, "ela")
    return Response(storage.get(key), media_type="image/png")


@router.get("/documents/{doc_id}/fields")
def get_fields(doc_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = _doc(db, user, doc_id)
    return [dict(name=f.name, value=f.value, confidence=f.confidence, status=f.status, page=f.page,
                 bbox=None if f.x0 is None else [f.x0, f.y0, f.x1, f.y1])
            for f in db.scalars(select(ExtractedField).where(ExtractedField.document_id == d.id).order_by(ExtractedField.id))]
