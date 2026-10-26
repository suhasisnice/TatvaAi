from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    doc_type: Mapped[str] = mapped_column(String(50))
    classification_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    filename: Mapped[str] = mapped_column(String(300))
    content_type: Mapped[str] = mapped_column(String(100))
    storage_key: Mapped[str] = mapped_column(String(300))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # UNSIGNED | SIGNED_VALID | SIGNED_MODIFIED | SIGNED_INVALID | SIGNED_UNTRUSTED
    dsc_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    dsc_info: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: signatures + pdf metadata
    qr_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    carried_forward_from: Mapped[str | None] = mapped_column(String(10), nullable=True)
    proof_level: Mapped[str | None] = mapped_column(String(20), nullable=True)  # CRYPTOGRAPHIC | ISSUER_VERIFIED | FORENSIC_ONLY
    forensics: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: ELA artifact key/score, font findings, metadata findings


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    page_no: Mapped[int] = mapped_column(Integer)
    width: Mapped[float] = mapped_column(Float)
    height: Mapped[float] = mapped_column(Float)
    image_key: Mapped[str] = mapped_column(String(300))
    has_text: Mapped[bool] = mapped_column(Boolean, default=True)


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="EXTRACTED")  # or MANUAL_REVIEW_REQUIRED
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    x0: Mapped[float | None] = mapped_column(Float, nullable=True)  # normalised 0-1 bbox
    y0: Mapped[float | None] = mapped_column(Float, nullable=True)
    x1: Mapped[float | None] = mapped_column(Float, nullable=True)
    y1: Mapped[float | None] = mapped_column(Float, nullable=True)


class FacultyRecord(Base):
    __tablename__ = "faculty_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)
    faculty_id: Mapped[str] = mapped_column(String(50), index=True)  # masked in API responses
    national_id_hash: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(200))
    designation: Mapped[str] = mapped_column(String(50))
    qualification: Mapped[str] = mapped_column(String(100))
    full_time: Mapped[bool] = mapped_column(Boolean)
    joined_date: Mapped[str] = mapped_column(String(10))
    department: Mapped[str] = mapped_column(String(200))


class DocumentAccess(Base):
    __tablename__ = "document_access"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    at: Mapped[datetime] = mapped_column(DateTime)
    what: Mapped[str] = mapped_column(String(30))
