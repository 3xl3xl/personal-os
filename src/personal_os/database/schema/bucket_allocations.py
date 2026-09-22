"""
BucketAllocation persistence model — Finance v0.1 Schema Design §5.4
(Decision 2, Transfer/Reallocation atomicity).

Append-only ledger of how a CASH account's balance is split across its
CapitalBuckets — never updated or deleted. Two invariants depend on
this table (sum of a bucket's ACTIVE allocations == derived bucket
balance; sum of an account's bucket balances == derived account
balance); both are Service-Layer-verified, not DB constraints — see
this step's DB-vs-Service invariant list.

Two entry types:
- CASH_LINKED: created alongside a real cash-moving Transaction
  (originating_transaction_id required).
- REALLOCATION: pure relabeling between buckets, no cash movement; two
  legs share a reallocation_group_id and sum to zero
  (reallocation_group_id required here; the "two legs exist and sum to
  zero" invariant itself is Service-Layer, not DB-enforced, since it
  depends on sibling rows).

The CHECK constraint below only enforces that a row carries the
linkage field its own entry_type requires — a same-row, single-row
rule — it cannot and does not verify anything about sibling rows.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import BigInteger, CheckConstraint, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from personal_os.database.schema.base import Base
from personal_os.domain.enums import EntryType


class BucketAllocation(Base):
    __tablename__ = "bucket_allocations"
    __table_args__ = (
        CheckConstraint("length(currency_code) = 3", name="ck_bucket_allocations_currency_code_length"),
        CheckConstraint("currency_code = upper(currency_code)", name="ck_bucket_allocations_currency_code_upper"),
        CheckConstraint(
            "(entry_type = 'CASH_LINKED' AND originating_transaction_id IS NOT NULL) OR "
            "(entry_type = 'REALLOCATION' AND reallocation_group_id IS NOT NULL)",
            name="ck_bucket_allocations_entry_type_linkage",
        ),
        Index("ix_bucket_allocations_bucket_id", "bucket_id"),
        Index("ix_bucket_allocations_account_id", "account_id"),
        Index("ix_bucket_allocations_reallocation_group_id", "reallocation_group_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    bucket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("capital_buckets.id"), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    entry_type: Mapped[EntryType] = mapped_column(
        Enum(EntryType, native_enum=False, create_constraint=True, validate_strings=True),
        nullable=False,
    )
    originating_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id"), nullable=True
    )
    reallocation_group_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(nullable=False)
