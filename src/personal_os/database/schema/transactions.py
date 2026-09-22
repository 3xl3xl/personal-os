"""
Transaction persistence model — Finance v0.1 Schema Design §5.2.

The append-only transaction ledger. Corrections are made via a new
row referencing `correction_of`, or by marking a row VOIDED — never by
UPDATE or DELETE (Schema Design §11, Audit Strategy). That append-only
discipline is enforced by a future Repository/Service Layer, not by
this schema module.

`transfer_group_id` is a nullable column shared by the two legs of an
account-to-account transfer (Schema Design, Transfer atomicity,
Decision 2). A transfer itself never represents revenue or expense.
The requirement that both legs exist and sum to zero, and the 2-leg
atomicity of their creation, are Service-Layer invariants — not
something a single-row CHECK constraint can correctly express, since
they depend on a sibling row. See this step's DB-vs-Service invariant
list.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import BigInteger, CheckConstraint, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from personal_os.database.schema.base import Base
from personal_os.domain.enums import TransactionKind, TransactionStatus


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("length(currency_code) = 3", name="ck_transactions_currency_code_length"),
        CheckConstraint("currency_code = upper(currency_code)", name="ck_transactions_currency_code_upper"),
        Index("ix_transactions_account_id", "account_id"),
        Index("ix_transactions_occurred_at", "occurred_at"),
        Index("ix_transactions_transfer_group_id", "transfer_group_id"),
        Index("ix_transactions_metric_key", "metric_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    transaction_type: Mapped[TransactionKind] = mapped_column(
        Enum(TransactionKind, native_enum=False, create_constraint=True, validate_strings=True),
        nullable=False,
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    occurred_at: Mapped[dt.datetime] = mapped_column(nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, native_enum=False, create_constraint=True, validate_strings=True),
        nullable=False,
        default=TransactionStatus.ACTIVE,
    )
    correction_of: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.id"), nullable=True
    )
    metric_key: Mapped[str | None] = mapped_column(
        ForeignKey("financial_metrics.key"), nullable=True
    )
    transfer_group_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
