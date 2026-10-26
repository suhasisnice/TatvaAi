"""facts, verifications, rule_packs, rule_results

Revision ID: 0003
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"


def fk(t, **kw):
    return sa.Column(kw.pop("name"), sa.Integer, sa.ForeignKey(t), **kw)


def upgrade():
    op.create_table("facts",
        sa.Column("id", sa.Integer, primary_key=True),
        fk("applications.id", name="application_id", nullable=False, index=True),
        sa.Column("subject", sa.String(120), nullable=False, index=True),
        sa.Column("attribute", sa.String(80), nullable=False),
        sa.Column("value", sa.Text), sa.Column("unit", sa.String(20)),
        sa.Column("source_type", sa.String(20), nullable=False),
        fk("documents.id", name="document_id"),
        sa.Column("page", sa.Integer), sa.Column("bbox", sa.String(100)),
        sa.Column("system_source", sa.String(80)), sa.Column("record_id", sa.String(120)))
    op.create_table("verifications",
        sa.Column("id", sa.Integer, primary_key=True),
        fk("applications.id", name="application_id", nullable=False, index=True),
        fk("documents.id", name="document_id"),
        sa.Column("adapter", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("request_hash", sa.String(64)), sa.Column("response_hash", sa.String(64)),
        sa.Column("response_summary", sa.Text),
        sa.Column("checked_at", sa.DateTime, nullable=False),
        sa.Column("carried_forward_from", sa.String(10)),
        sa.Column("manual_note", sa.Text),
        fk("users.id", name="manual_by"))
    op.create_table("rule_packs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("version", sa.String(50), nullable=False, unique=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("effective_from", sa.String(10)),
        sa.Column("yaml_blob", sa.Text, nullable=False),
        fk("users.id", name="created_by"), fk("users.id", name="approved_by"),
        sa.Column("created_at", sa.DateTime, nullable=False))
    op.create_table("rule_results",
        sa.Column("id", sa.Integer, primary_key=True),
        fk("applications.id", name="application_id", nullable=False, index=True),
        sa.Column("rule_id", sa.String(80), nullable=False),
        sa.Column("rule_pack_version", sa.String(50), nullable=False),
        sa.Column("scope", sa.String(120)),
        sa.Column("status", sa.String(25), nullable=False),
        sa.Column("result_json", sa.Text, nullable=False),
        sa.Column("evaluated_at", sa.DateTime, nullable=False))


def downgrade():
    for t in ("rule_results", "rule_packs", "verifications", "facts"):
        op.drop_table(t)
