from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
)
from sqlalchemy.orm import relationship

from app.core.db import Base


class Institution(Base):
    __tablename__ = "institutions"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    state = Column(String)
    aicte_id = Column(String)
    trust_name = Column(String)
    survey_no = Column(String)
    lat = Column(Float)
    lon = Column(String)
    declared_faculty = Column(Integer, default=0)
    declared_built_up_m2 = Column(Float, default=0)
    footprint_estimate_m2 = Column(Float, nullable=True)
    approved_intake = Column(Integer, default=0)
    website_faculty_count = Column(Integer, nullable=True)
    # Declared infrastructure / cadre figures from the online form (see engines.norm_flags).
    infrastructure = Column(JSON, default=dict)

    users = relationship("User", back_populates="institution")
    applications = relationship("Application", back_populates="institution")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)  # institution, officer, inspector
    password_hash = Column(String, nullable=False)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=True)
    totp_secret = Column(String, nullable=True)
    mfa_enabled = Column(Boolean, default=False)
    active = Column(Boolean, default=True)

    institution = relationship("Institution", back_populates="users")


class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True)
    institution_id = Column(Integer, ForeignKey("institutions.id"), nullable=False)
    category = Column(String, default="EOA")
    academic_year = Column(String, nullable=False)
    status = Column(String, default="DRAFT")  # DRAFT, SUBMITTED, REOPENED
    submitted_at = Column(DateTime, nullable=True)
    reopen_count = Column(Integer, default=0)
    risk_tier = Column(String, nullable=True)  # GREEN, AMBER, RED
    risk_score = Column(Float, default=0)
    top_reasons = Column(JSON, default=list)
    form_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    institution = relationship("Institution", back_populates="applications")
    documents = relationship("Document", back_populates="application", cascade="all, delete-orphan")
    flags = relationship("Flag", back_populates="application", cascade="all, delete-orphan")
    verifications = relationship("Verification", back_populates="application", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    doc_type = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    sha256 = Column(String, nullable=False)
    classification_confidence = Column(Float, default=0.9)
    signed = Column(Boolean, default=False)
    signature_status = Column(String, default="UNSIGNED")  # SIGNED_VALID, SIGNED_MODIFIED, UNSIGNED
    extracted_fields = Column(JSON, default=dict)
    proof_level = Column(String, default="FORENSIC_ONLY")
    carried_forward_from = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="documents")


class Flag(Base):
    __tablename__ = "flags"
    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    engine = Column(String, nullable=False)
    code = Column(String, nullable=False)
    severity = Column(String, nullable=False)  # CRITICAL, MAJOR, MINOR, INFO
    confidence = Column(Float, default=1.0)
    forensic = Column(Boolean, default=False)
    message = Column(Text, nullable=False)
    explanation = Column(Text, default="")
    citation = Column(String, default="")
    evidence = Column(JSON, default=list)
    status = Column(String, default="OPEN")  # OPEN, ACCEPTED, DISMISSED
    decision_reason = Column(Text, nullable=True)
    fingerprint = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # EVC / inspection committee's own on-site verdict for this flag, separate
    # from the officer's accept/dismiss above (an officer screens findings
    # before inspection; an inspector records what they actually found on site).
    inspection_status = Column(String, default="PENDING")  # PENDING, CONFIRMED, CLEARED
    inspection_note = Column(Text, nullable=True)
    inspection_by = Column(String, nullable=True)
    inspected_at = Column(DateTime, nullable=True)

    application = relationship("Application", back_populates="flags")


class Verification(Base):
    __tablename__ = "verifications"
    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    adapter = Column(String, nullable=False)
    source_name = Column(String, nullable=False)
    status = Column(String, nullable=False)  # VERIFIED, MISMATCH_DETECTED, EXPIRED, VERIFICATION_PENDING, SOURCE_UNAVAILABLE, MANUAL_REVIEW_REQUIRED
    summary = Column(Text, default="")
    carried_forward_from = Column(String, nullable=True)
    manual_note = Column(Text, nullable=True)
    manual_by = Column(String, nullable=True)
    checked_at = Column(DateTime, default=datetime.utcnow)

    application = relationship("Application", back_populates="verifications")


class IssuerRecord(Base):
    """The 'ground truth' held by a mock issuing authority (SHCIL, DigiLocker,
    state fire/occupancy portal, AICTE faculty registry, ...) for one document
    type of one institution. Always MOCK, as the real APIs are not available."""
    __tablename__ = "issuer_records"
    id = Column(Integer, primary_key=True)
    institution_slug = Column(String, nullable=False)
    doc_type = Column(String, nullable=False)
    source_name = Column(String, nullable=False)
    available = Column(Boolean, default=True)
    expected_fields = Column(JSON, default=dict)
    registered_sha256 = Column(String, nullable=True)


class FacultyRegistryEntry(Base):
    """Mock AICTE national faculty registry: which institution each faculty
    id is registered full-time with."""
    __tablename__ = "faculty_registry"
    id = Column(Integer, primary_key=True)
    faculty_id = Column(String, nullable=False)
    institution_slug = Column(String, nullable=False)
    name = Column(String, default="")


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    seq = Column(Integer, nullable=False)
    actor = Column(String, nullable=False)
    action = Column(String, nullable=False)
    entity = Column(String, default="")
    payload = Column(JSON, default=dict)
    prev_hash = Column(String, default="")
    hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    audience = Column(String, nullable=False)  # institution, officer
    kind = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
