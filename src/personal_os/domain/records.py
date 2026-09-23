"""
Repository-facing domain records (DTOs) for Personal OS v0.1.

Source of truth: ARCHITECTURE.md Sec.1 ("the Service Layer works
exclusively with plain domain objects") and Step 6's "Domain /
Persistence Boundary" requirement.

Why this module exists (Step 6 justification, as requested):
- Why needed: the Repository Layer's public API must never return a
  SQLAlchemy ORM model instance to a caller above it (Step 6, item 6;
  ADR-002's layering). Without a plain return type, a Repository
  method would have no choice but to hand back a
  personal_os.database.schema.* instance directly.
- Why this specifically avoids leaking an ORM object: an ORM instance
  is bound to the Session/transaction that loaded it -- accessing an
  unloaded attribute after that Session closes raises
  DetachedInstanceError, and mutating it looks like (but is not
  necessarily) a tracked, persisted change. A frozen dataclass built
  *before* the Repository method returns has none of that lifecycle
  coupling: it is safe to hold, compare, and pass around after the
  UnitOfWork/Session that produced it has closed.
- How the future Service Layer will use these: they are exactly the
  shape Q1-Q5 (Net Worth, Available Capital, Tax Reserved, Distance
  from Target, Monthly Target vs Actual) need to compute from -- e.g.
  summing TransactionRecord.amount (a Money) across an account's
  ACTIVE transactions to derive a balance, filtering
  CapitalBucketRecord.bucket_role == BucketRole.TAX_RESERVE for Q3, or
  reading FinancialTargetRecord.effective_from to apply the version-
  selection rule documented in
  personal_os.database.schema.financial_targets. None of that logic
  is implemented here or anywhere in Step 6 -- these are plain data
  carriers only.

These are intentionally *not* a general-purpose Domain Entity
framework: one frozen dataclass per Finance v0.1 table, each a direct,
boring mirror of that table's columns (with amount_minor +
currency_code pairs collapsed into the existing Money value object,
per ADR-005). No behavior, no validation beyond what the underlying
value objects (Money, the enums) already enforce, no ORM-style
relationships or lazy loading. This module imports nothing from
personal_os.database or sqlalchemy -- only existing domain primitives
(Money, the enums) plus the standard library.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from personal_os.domain.enums import (
    AccountStatus,
    AccountType,
    BucketRole,
    CapitalBucketStatus,
    EntryType,
    TransactionKind,
    TransactionStatus,
)
from personal_os.domain.money import Money


@dataclass(frozen=True, slots=True)
class AccountRecord:
    id: uuid.UUID
    name: str
    account_type: AccountType
    currency_code: str
    opened_at: dt.datetime
    status: AccountStatus


@dataclass(frozen=True, slots=True)
class TransactionRecord:
    id: uuid.UUID
    account_id: uuid.UUID
    transaction_type: TransactionKind
    amount: Money
    occurred_at: dt.datetime
    status: TransactionStatus
    correction_of: uuid.UUID | None = None
    metric_key: str | None = None
    transfer_group_id: uuid.UUID | None = None
    memo: str | None = None


@dataclass(frozen=True, slots=True)
class CapitalBucketRecord:
    id: uuid.UUID
    account_id: uuid.UUID
    name: str
    bucket_role: BucketRole
    is_protected: bool
    status: CapitalBucketStatus
    created_at: dt.datetime


@dataclass(frozen=True, slots=True)
class BucketAllocationRecord:
    id: uuid.UUID
    bucket_id: uuid.UUID
    account_id: uuid.UUID
    amount: Money
    entry_type: EntryType
    created_at: dt.datetime
    originating_transaction_id: uuid.UUID | None = None
    reallocation_group_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class FinancialMetricRecord:
    id: uuid.UUID
    key: str
    display_name: str
    created_at: dt.datetime


@dataclass(frozen=True, slots=True)
class FinancialTargetRecord:
    id: uuid.UUID
    metric_key: str
    target_amount: Money
    effective_from: dt.datetime
    created_at: dt.datetime


@dataclass(frozen=True, slots=True)
class MonthlyTargetRecord:
    id: uuid.UUID
    metric_key: str
    year: int
    month: int
    target_amount: Money
    effective_from: dt.datetime
    created_at: dt.datetime


@dataclass(frozen=True, slots=True)
class AuditLogRecord:
    id: uuid.UUID
    actor: str
    action: str
    affected_entity_type: str
    approval_status: str
    occurred_at: dt.datetime
    affected_entity_id: uuid.UUID | None = None
    old_value: str | None = None
    new_value: str | None = None
    reason: str | None = None

    model_or_agent: str | None = None
    tool: str | None = None
    source: str | None = None
