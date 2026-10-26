"""audit_log, alerts, alert_reads, jobs; applications.risk_reasons / scored_at

Revision ID: 0005
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"


def upgrade():
    op.add_column("applications", sa.Column("risk_reasons", sa.Text))
    op.add_column("applications", sa.Column("scored_at", sa.DateTime))
    op.create_table("audit_log",
        sa.Column("seq", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ts", sa.String(40), nullable=False), sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("action", sa.String(60), nullable=False, index=True), sa.Column("entity", sa.String(120), nullable=False, index=True),
        sa.Column("payload_json", sa.Text, nullable=False), sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False), sa.Column("hash", sa.String(64), nullable=False))
    op.create_table("alerts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("application_id", sa.Integer, sa.ForeignKey("applications.id"), nullable=False, index=True),
        sa.Column("audience", sa.String(12), nullable=False), sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False), sa.Column("message", sa.Text, nullable=False),
        sa.Column("dedupe_key", sa.String(300), nullable=False), sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("application_id", "dedupe_key"))
    op.create_table("alert_reads",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("alert_id", sa.Integer, sa.ForeignKey("alerts.id"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("alert_id", "user_id"))
    op.create_table("jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("application_id", sa.Integer, sa.ForeignKey("applications.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(20), nullable=False), sa.Column("status", sa.String(10), nullable=False),
        sa.Column("result_json", sa.Text), sa.Column("created_at", sa.DateTime, nullable=False), sa.Column("finished_at", sa.DateTime))


def downgrade():
    for t in ("jobs", "alert_reads", "alerts", "audit_log"):
        op.drop_table(t)
    op.drop_column("applications", "scored_at")
    op.drop_column("applications", "risk_reasons")
