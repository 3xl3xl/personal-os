"""
Account persistence model — Finance v0.1 Schema Design §5.1.

Represents the "physical/financial location" of money. Account
balance is never a stored column: it is derived as the sum of the
account's ACTIVE transactions (Schema Design §7, Balance Strategy) by
a future Repository-layer query, not by anything in this module.

`status` (ACTIVE, CLOSED) uses the personal_os.domain.enums.AccountStatus
enum (added in Step 4 to complete the confirmed Schema Design
semantics as a domain type, alongside AccountType).
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import CheckConstraint, Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from personal_os.database.schema.base import Base
from personal_os.domain.enums import AccountStatus, AccountType


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint("length(currency_code) = 3", name="ck_accounts_currency_code_length"),
        CheckConstraint("currency_code = upper(currency_code)", name="ck_accounts_currency_code_upper"),
        Index("ix_accounts_currency_code", "currency_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    account_type: Mapped[AccountType] = mapped_column(
        Enum(AccountType, native_enum=False, create_constraint=True, validate_strings=True),
        nullable=False,
    )
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    opened_at: Mapped[dt.datetime] = mapped_column(nullable=False)
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, native_enum=False, create_constraint=True, validate_strings=True),
        nullable=False,
        default=AccountStatus.ACTIVE,
    )
