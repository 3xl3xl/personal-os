"""Add external_transaction_links for read-only bank/card import dedup.

Revision ID: external_txn_links_v1
Revises: audit_provenance_v1
Create Date: 2026-09-23

ADR-014 (freee read-only integration, Phase A). The UNIQUE constraint on
(source, external_office_id, external_account_id, external_transaction_id)
is the DB-enforced half of the no-duplicate-import guarantee; the other
half is the Repository/Service dedup check in
personal_os.services.import_review before a write is ever attempted.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "external_txn_links_v1"
down_revision = "audit_provenance_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_transaction_links",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("external_office_id", sa.String(), nullable=False),
        sa.Column("external_account_id", sa.String(), nullable=False),
        sa.Column("external_transaction_id", sa.String(), nullable=False),
        sa.Column(
            "transaction_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("transactions.id"),
            nullable=False,
        ),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "source",
            "external_office_id",
            "external_account_id",
            "external_transaction_id",
            name="uq_external_transaction_links_identity",
        ),
    )
    op.create_index(
        "ix_external_transaction_links_transaction_id",
        "external_transaction_links",
        ["transaction_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_transaction_links_transaction_id",
        table_name="external_transaction_links",
    )
    op.drop_table("external_transaction_links")
