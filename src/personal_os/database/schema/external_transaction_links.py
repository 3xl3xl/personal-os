"""
ExternalTransactionLink persistence model -- ADR-014 (freee read-only
integration), dedup tracking for approved external-source writes.

Records exactly which (source, external_office_id, external_account_id,
external_transaction_id) tuple produced which Transaction, so a later sync
of the same statement line is recognized and never creates a second
Transaction. The UNIQUE constraint below makes duplicate import a DB-
enforced impossibility, not just an application-level check (see ADR-014's
Rationale). Append-only: relinking or reclassifying an already-imported
line is a future step, not this one -- no update/delete method exists at
the Repository layer.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from personal_os.database.schema.base import Base


class ExternalTransactionLink(Base):
    __tablename__ = "external_transaction_links"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "external_office_id",
            "external_account_id",
            "external_transaction_id",
            name="uq_external_transaction_links_identity",
        ),
        Index("ix_external_transaction_links_transaction_id", "transaction_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String, nullable=False)
    external_office_id: Mapped[str] = mapped_column(String, nullable=False)
    external_account_id: Mapped[str] = mapped_column(String, nullable=False)
    external_transaction_id: Mapped[str] = mapped_column(String, nullable=False)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("transactions.id"), nullable=False
    )
    imported_at: Mapped[dt.datetime] = mapped_column(nullable=False)
