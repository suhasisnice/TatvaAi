"""flags, flag_decisions; documents.proof_level / forensics

Revision ID: 0004
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade():
    op.add_column("documents", sa.Column("proof_level", sa.String(20)))
    op.add_column("documents", sa.Column("forensics", sa.Text))
    op.create_table("flags",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("application_id", sa.Integer, sa.ForeignKey("applications.id"), nullable=False, index=True),
        sa.Column("engine", sa.String(20), nullable=False),
        sa.Column("code", sa.String(50), nullable=False, index=True),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("explanation", sa.Text, nullable=False),
        sa.Column("evidence", sa.Text, nullable=False),
        sa.Column("rule_id", sa.String(80)), sa.Column("rule_pack_version", sa.String(50)), sa.Column("citation", sa.Text),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("documents.id")),
        sa.Column("forensic", sa.Boolean, nullable=False),
        sa.Column("fingerprint", sa.String(250), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime, nullable=False))
    op.create_table("flag_decisions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("flag_id", sa.Integer, sa.ForeignKey("flags.id"), nullable=False, index=True),
        sa.Column("officer_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decision", sa.String(10), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("decided_at", sa.DateTime, nullable=False))


def downgrade():
    op.drop_table("flag_decisions")
    op.drop_table("flags")
    op.drop_column("documents", "forensics")
    op.drop_column("documents", "proof_level")
