from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Fact(Base):
    """One fact with provenance: an extracted field (document/page/bbox), the online form, or a system record."""

    __tablename__ = "facts"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    subject: Mapped[str] = mapped_column(String(120), index=True)
    attribute: Mapped[str] = mapped_column(String(80))
    value: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_type: Mapped[str] = mapped_column(String(20))  # document | form | system | derived
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox: Mapped[str | None] = mapped_column(String(100), nullable=True)  # JSON [x0,y0,x1,y1]
    system_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    record_id: Mapped[str | None] = mapped_column(String(120), nullable=True)


class Verification(Base):
    __tablename__ = "verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    adapter: Mapped[str] = mapped_column(String(50))
    # VERIFIED | MISMATCH_DETECTED | EXPIRED | VERIFICATION_PENDING | SOURCE_UNAVAILABLE | MANUAL_REVIEW_REQUIRED
    status: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(120))
    request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    response_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    response_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime)
    carried_forward_from: Mapped[str | None] = mapped_column(String(10), nullable=True)
    manual_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class RulePack(Base):
    __tablename__ = "rule_packs"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(50), unique=True)
    status: Mapped[str] = mapped_column(String(10), default="draft")  # draft | active | retired
    effective_from: Mapped[str | None] = mapped_column(String(10), nullable=True)
    yaml_blob: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class RuleResult(Base):
    __tablename__ = "rule_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    rule_id: Mapped[str] = mapped_column(String(80))
    rule_pack_version: Mapped[str] = mapped_column(String(50))
    scope: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(25))  # PASS | FAIL | INSUFFICIENT_EVIDENCE
    result_json: Mapped[str] = mapped_column(Text)  # inputs, computed values, message, citation
    evaluated_at: Mapped[datetime] = mapped_column(DateTime)
