"""
CapitalBucket persistence model — Finance v0.1 Schema Design §5.3.

Represents the "purpose" of allocated cash within a CASH account.
Bucket balance is never a stored column: it is derived as the sum of
this bucket's ACTIVE bucket_allocations (Schema Design §7, Balance
Strategy).

`name`, `bucket_role`, and `is_protected` are three independent
responsibilities (Schema Design v0.3, "Final correction — semantic
bucket role"):
- name: user-defined display label. Renaming never changes any
  financial calculation.
- bucket_role: system semantic role (GENERAL, TAX_RESERVE in v0.1).
  Q3 (Tax Reserved) is computed from bucket_role == TAX_RESERVE, never
  from name.
- is_protected: Available Capital exclusion policy.

Both bucket_role and is_protected are required (NOT NULL) with no
column default at all — not even a role-independent one — so that
every bucket creation must state both explicitly. This is a stricter
reading than "no bucket_role-conditional default"; it guarantees there
is no code path, now or later, that could let one imply the other.
Multiple TAX_RESERVE-role buckets are permitted: there is no unique
constraint on bucket_role or on name.

CASH-only allocation scope (a bucket's account should be a CASH
account) is a Service-Layer / domain invariant per the Schema Design,
not a DB-enforced constraint — this table has a plain FK to accounts,
with no CHECK tying it to accounts.account_type.

`status` (ACTIVE, ARCHIVED) uses the
personal_os.domain.enums.CapitalBucketStatus enum (added in Step 4 to
complete the confirmed Schema Design semantics as a domain type,
alongside BucketRole).
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from personal_os.database.schema.base import Base
from personal_os.domain.enums import BucketRole, CapitalBucketStatus


class CapitalBucket(Base):
    __tablename__ = "capital_buckets"
    __table_args__ = (
        Index("ix_capital_buckets_account_id", "account_id"),
        Index("ix_capital_buckets_bucket_role", "bucket_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    bucket_role: Mapped[BucketRole] = mapped_column(
        Enum(BucketRole, native_enum=False, create_constraint=True, validate_strings=True),
        nullable=False,
    )
    is_protected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[CapitalBucketStatus] = mapped_column(
        Enum(CapitalBucketStatus, native_enum=False, create_constraint=True, validate_strings=True),
        nullable=False,
        default=CapitalBucketStatus.ACTIVE,
    )
    created_at: Mapped[dt.datetime] = mapped_column(nullable=False)
