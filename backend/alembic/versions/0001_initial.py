"""initial schema: users, institutions, campuses, applications

Revision ID: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade():
    op.create_table("institutions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("state", sa.String(100), nullable=False))
    op.create_table("users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(200), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(100), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("institution_id", sa.Integer, sa.ForeignKey("institutions.id")),
        sa.Column("mfa_secret", sa.String(64)),
        sa.Column("mfa_enabled", sa.Boolean, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False))
    op.create_table("campuses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("institution_id", sa.Integer, sa.ForeignKey("institutions.id"), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lon", sa.Float, nullable=False))
    op.create_table("applications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("institution_id", sa.Integer, sa.ForeignKey("institutions.id"), nullable=False, index=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("academic_year", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("submitted_at", sa.DateTime),
        sa.Column("locked", sa.Boolean, nullable=False),
        sa.Column("reopen_count", sa.Integer, nullable=False),
        sa.Column("rule_pack_version", sa.String(50)),
        sa.Column("risk_tier", sa.String(10)),
        sa.Column("risk_score", sa.Float))


def downgrade():
    for t in ("applications", "campuses", "users", "institutions"):
        op.drop_table(t)
