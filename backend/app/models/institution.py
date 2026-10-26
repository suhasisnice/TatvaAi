from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    state: Mapped[str] = mapped_column(String(100))
    aicte_id: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)


class Campus(Base):
    # ponytail: plain lat/lon + haversine instead of PostGIS types, keeps tests DB-agnostic.
    __tablename__ = "campuses"

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    address: Mapped[str] = mapped_column(String(500))
    state: Mapped[str] = mapped_column(String(100))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"), index=True)
    category: Mapped[str] = mapped_column(String(50))
    academic_year: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    reopen_count: Mapped[int] = mapped_column(Integer, default=0)
    rule_pack_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    risk_tier: Mapped[str | None] = mapped_column(String(10), nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_reasons: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: top reasons sorted by contribution
    scored_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    form_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # online application form (JSON)
