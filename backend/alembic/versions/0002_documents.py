"""documents, pages, extracted fields, faculty records, access log; institution.aicte_id, application.form_data

Revision ID: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
    op.add_column("institutions", sa.Column("aicte_id", sa.String(50)))
    op.create_index("uq_institutions_aicte_id", "institutions", ["aicte_id"], unique=True)  # portable: SQLite cannot ALTER ADD UNIQUE
    op.add_column("applications", sa.Column("form_data", sa.Text))
    op.create_table("documents",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("application_id", sa.Integer, sa.ForeignKey("applications.id"), nullable=False, index=True),
        sa.Column("doc_type", sa.String(50), nullable=False),
        sa.Column("classification_confidence", sa.Float, nullable=False),
        sa.Column("filename", sa.String(300), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("storage_key", sa.String(300), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False, index=True),
        sa.Column("size", sa.Integer, nullable=False),
        sa.Column("page_count", sa.Integer, nullable=False),
        sa.Column("uploaded_at", sa.DateTime, nullable=False),
        sa.Column("uploaded_by", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("dsc_status", sa.String(30)),
        sa.Column("dsc_info", sa.Text),
        sa.Column("qr_payload", sa.Text),
        sa.Column("carried_forward_from", sa.String(10)))
    op.create_table("document_pages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("page_no", sa.Integer, nullable=False),
        sa.Column("width", sa.Float, nullable=False),
        sa.Column("height", sa.Float, nullable=False),
        sa.Column("image_key", sa.String(300), nullable=False),
        sa.Column("has_text", sa.Boolean, nullable=False))
    op.create_table("extracted_fields",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("value", sa.Text),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("page", sa.Integer),
        *[sa.Column(c, sa.Float) for c in ("x0", "y0", "x1", "y1")])
    op.create_table("faculty_records",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("application_id", sa.Integer, sa.ForeignKey("applications.id"), nullable=False, index=True),
        sa.Column("institution_id", sa.Integer, sa.ForeignKey("institutions.id"), nullable=False, index=True),
        sa.Column("faculty_id", sa.String(50), nullable=False, index=True),
        sa.Column("national_id_hash", sa.String(64), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("designation", sa.String(50), nullable=False),
        sa.Column("qualification", sa.String(100), nullable=False),
        sa.Column("full_time", sa.Boolean, nullable=False),
        sa.Column("joined_date", sa.String(10), nullable=False),
        sa.Column("department", sa.String(200), nullable=False))
    op.create_table("document_access",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("documents.id"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("at", sa.DateTime, nullable=False),
        sa.Column("what", sa.String(30), nullable=False))


def downgrade():
    for t in ("document_access", "faculty_records", "extracted_fields", "document_pages", "documents"):
        op.drop_table(t)
    op.drop_column("applications", "form_data")
    op.drop_index("uq_institutions_aicte_id", "institutions")
    op.drop_column("institutions", "aicte_id")
