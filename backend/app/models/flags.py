from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Flag(Base):
    """An evidence-linked finding from one of the five engines. Never an approval/rejection: officers decide."""

    __tablename__ = "flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    engine: Mapped[str] = mapped_column(String(20))  # completeness|consistency|authenticity|issuer|compliance
    code: Mapped[str] = mapped_column(String(50), index=True)
    severity: Mapped[str] = mapped_column(String(10))  # CRITICAL|MAJOR|MINOR|INFO
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    message: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[str] = mapped_column(Text)  # JSON list of {document_id,page,bbox,...} | {system_source,record_id,...}
    rule_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    rule_pack_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    citation: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="OPEN")  # OPEN|ACCEPTED|DISMISSED
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    forensic: Mapped[bool] = mapped_column(Boolean, default=False)
    fingerprint: Mapped[str] = mapped_column(String(250), index=True)  # stable identity so decisions survive re-runs
    created_at: Mapped[datetime] = mapped_column(DateTime)
    # The inspection committee's own on-site verdict, separate from the officer's ACCEPT/DISMISS screening above.
    inspection_status: Mapped[str] = mapped_column(String(10), default="PENDING", server_default="PENDING")  # PENDING|CONFIRMED|CLEARED
    inspection_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    inspection_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    inspected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class FlagDecision(Base):
    __tablename__ = "flag_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    flag_id: Mapped[int] = mapped_column(ForeignKey("flags.id"), index=True)
    officer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(10))  # ACCEPT|DISMISS
    reason: Mapped[str] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime)
