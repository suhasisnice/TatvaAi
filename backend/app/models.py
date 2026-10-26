"""CONTRACT 2: the 19 tables. Column changes are `contract:` commits.
Tables are created with create_all for now (see DECISIONS.md #4); add Alembic before Postgres."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _pk():
    return mapped_column(Integer, primary_key=True)


def _now():
    return mapped_column(DateTime, default=datetime.utcnow)


class Institution(Base):
    __tablename__ = "institutions"
    id: Mapped[int] = _pk()
    name: Mapped[str] = mapped_column(String)
    slug: Mapped[str] = mapped_column(String, unique=True)
    state: Mapped[str] = mapped_column(String)
    aicte_id: Mapped[str] = mapped_column(String)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = _pk()
    email: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)  # institution|officer|inspector|admin
    institution_id: Mapped[int | None] = mapped_column(ForeignKey("institutions.id"))
    password_hash: Mapped[str] = mapped_column(String)
    totp_secret: Mapped[str | None] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Campus(Base):
    __tablename__ = "campuses"
    id: Mapped[int] = _pk()
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    address: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String)
    lat: Mapped[float] = mapped_column(Float)  # plain lat/lon, no PostGIS
    lon: Mapped[float] = mapped_column(Float)


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = _pk()
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    category: Mapped[str] = mapped_column(String)
    academic_year: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="DRAFT")  # DRAFT|SUBMITTED|REOPENED
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    reopen_count: Mapped[int] = mapped_column(Integer, default=0)
    rule_pack_version: Mapped[str | None] = mapped_column(String)
    risk_tier: Mapped[str | None] = mapped_column(String)
    risk_score: Mapped[float | None] = mapped_column(Float)
    top_reasons: Mapped[list | None] = mapped_column(JSON)
    form_data: Mapped[dict | None] = mapped_column(JSON)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = _pk()
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    type: Mapped[str] = mapped_column(String)
    classification_confidence: Mapped[float] = mapped_column(Float, default=0)
    file_name: Mapped[str] = mapped_column(String)
    content_type: Mapped[str] = mapped_column(String)
    storage_key: Mapped[str] = mapped_column(String)
    sha256: Mapped[str] = mapped_column(String, index=True)
    size: Mapped[int] = mapped_column(Integer)
    pages: Mapped[int] = mapped_column(Integer, default=1)
    uploaded_at: Mapped[datetime] = _now()
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    signature_status: Mapped[str] = mapped_column(String, default="UNSIGNED")
    signature_details: Mapped[dict | None] = mapped_column(JSON)
    qr_payload: Mapped[str | None] = mapped_column(Text)
    carried_forward_from: Mapped[str | None] = mapped_column(String)
    proof_level: Mapped[str | None] = mapped_column(String)
    forensics: Mapped[dict | None] = mapped_column(JSON)


class DocumentPage(Base):
    __tablename__ = "document_pages"
    id: Mapped[int] = _pk()
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    page: Mapped[int] = mapped_column(Integer)
    image_key: Mapped[str] = mapped_column(String)  # 150-dpi PNG


class ExtractedField(Base):
    __tablename__ = "extracted_fields"
    id: Mapped[int] = _pk()
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    name: Mapped[str] = mapped_column(String)
    value: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="OK")
    page: Mapped[int] = mapped_column(Integer)
    bbox: Mapped[list | None] = mapped_column(JSON)  # [x0,y0,x1,y1] in 0-1


class FacultyRecord(Base):
    __tablename__ = "faculty_records"
    id: Mapped[int] = _pk()
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    faculty_id: Mapped[str] = mapped_column(String)
    national_id_hash: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    designation: Mapped[str] = mapped_column(String)
    qualification: Mapped[str] = mapped_column(String)
    full_time: Mapped[bool] = mapped_column(Boolean)
    joining_date: Mapped[str | None] = mapped_column(String)
    department: Mapped[str] = mapped_column(String)


class DocumentAccess(Base):
    __tablename__ = "document_access"
    id: Mapped[int] = _pk()
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    what: Mapped[str] = mapped_column(String)  # file|page|ela
    at: Mapped[datetime] = _now()


class FactRow(Base):
    __tablename__ = "facts"
    id: Mapped[int] = _pk()
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    subject: Mapped[str] = mapped_column(String)
    attribute: Mapped[str] = mapped_column(String)
    value: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String)
    source: Mapped[dict] = mapped_column(JSON)  # schemas.Evidence


class VerificationRow(Base):
    __tablename__ = "verifications"
    id: Mapped[int] = _pk()
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    adapter: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(Text)
    checked_at: Mapped[datetime] = _now()
    request_hash: Mapped[str | None] = mapped_column(String)
    response_hash: Mapped[str | None] = mapped_column(String)
    carried_forward_from: Mapped[str | None] = mapped_column(String)
    manual_note: Mapped[str | None] = mapped_column(Text)
    officer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class RulePack(Base):
    __tablename__ = "rule_packs"
    id: Mapped[int] = _pk()
    version: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="draft")  # draft|active|retired
    effective_date: Mapped[str | None] = mapped_column(String)
    yaml: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class RuleResultRow(Base):
    __tablename__ = "rule_results"
    id: Mapped[int] = _pk()
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    rule_id: Mapped[str] = mapped_column(String)
    outcome: Mapped[str] = mapped_column(String)
    values: Mapped[dict | None] = mapped_column(JSON)
    rule_pack_version: Mapped[str] = mapped_column(String)


class FlagRow(Base):
    __tablename__ = "flags"
    id: Mapped[int] = _pk()
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"))
    engine: Mapped[str] = mapped_column(String)
    code: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    message: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    rule_id: Mapped[str | None] = mapped_column(String)
    rule_pack_version: Mapped[str | None] = mapped_column(String)
    citation: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="OPEN")
    forensic: Mapped[bool] = mapped_column(Boolean, default=False)
    fingerprint: Mapped[str] = mapped_column(String, index=True)


class FlagDecision(Base):
    __tablename__ = "flag_decisions"
    id: Mapped[int] = _pk()
    flag_id: Mapped[int] = mapped_column(ForeignKey("flags.id"))
    officer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String)  # ACCEPT|DISMISS
    reason: Mapped[str] = mapped_column(Text)
    at: Mapped[datetime] = _now()


class AuditLog(Base):
    __tablename__ = "audit_log"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = _now()
    actor: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    entity: Mapped[str] = mapped_column(String)
    payload: Mapped[dict | None] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String)
    prev_hash: Mapped[str] = mapped_column(String)
    hash: Mapped[str] = mapped_column(String)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = _pk()
    kind: Mapped[str] = mapped_column(String)
    audience: Mapped[str] = mapped_column(String)  # institution|officer
    institution_id: Mapped[int | None] = mapped_column(ForeignKey("institutions.id"))
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id"))
    message: Mapped[str] = mapped_column(Text)
    dedupe_key: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = _now()


class AlertRead(Base):
    __tablename__ = "alert_reads"
    id: Mapped[int] = _pk()
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = _pk()
    kind: Mapped[str] = mapped_column(String)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id"))
    status: Mapped[str] = mapped_column(String, default="PENDING")
    created_at: Mapped[datetime] = _now()
