"""Add nullable provenance for historical audit compatibility.

Revision ID: audit_provenance_v1
Revises: 34f4e80340ee
"""
from alembic import op
import sqlalchemy as sa

revision = "audit_provenance_v1"
down_revision = "34f4e80340ee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("model_or_agent", "tool", "source"):
        op.add_column("audit_logs", sa.Column(name, sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("audit_logs") as batch:
        for name in ("source", "tool", "model_or_agent"):
            batch.drop_column(name)
