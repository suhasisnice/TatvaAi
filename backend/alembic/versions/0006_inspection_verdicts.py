"""flags.inspection_status / inspection_note / inspection_by_id / inspected_at (EVC on-site verdict per flag)

Revision ID: 0006
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"


def upgrade():
    with op.batch_alter_table("flags") as b:  # batch mode: SQLite cannot ALTER in a foreign key
        b.add_column(sa.Column("inspection_status", sa.String(10), nullable=False, server_default="PENDING"))
        b.add_column(sa.Column("inspection_note", sa.Text, nullable=True))
        b.add_column(sa.Column("inspection_by_id", sa.Integer, sa.ForeignKey("users.id", name="fk_flags_inspection_by"), nullable=True))
        b.add_column(sa.Column("inspected_at", sa.DateTime, nullable=True))
