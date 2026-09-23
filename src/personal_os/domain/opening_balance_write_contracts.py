"""Vendor-neutral inputs/results for the single OPENING_BALANCE transaction write.

Deliberately its own small module rather than a change to
personal_os.domain.write_contracts (the NORMAL transaction write's shapes):
ADR-012 explicitly scoped "opening-balance bootstrap" out of that contract,
and this project's established pattern (see domain/account_write_contracts.py's
own docstring) is additive parallel modules for new write shapes, never edits
to an already-tested one. WriteContext and ApprovalStatus are shared as-is
from write_contracts since neither carries any transaction-specific field,
and canonical_transaction is reused as-is (imported, not duplicated) since it
already serializes transaction_type generically for any TransactionKind.

See ADR-018 for the accepted design, including the one-per-account invariant
enforced by the Service layer (not expressible here without a repository read).
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, field_validator

from personal_os.domain.datetime import to_utc
from personal_os.domain.money import Money
from personal_os.domain.records import TransactionRecord
from personal_os.domain.write_contracts import ApprovalStatus

__all__ = ["AddOpeningBalanceInput", "AddOpeningBalanceResult"]


class AddOpeningBalanceInput(BaseModel):
    """One new ACTIVE OPENING_BALANCE transaction.

    No metric_key -- an opening balance is a bootstrap fact about the
    account, not an observation tied to a tracked metric. No
    transaction_type or status field -- always OPENING_BALANCE/ACTIVE,
    same rationale as AddTransactionInput fixing NORMAL/ACTIVE.
    """
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    id: uuid.UUID
    account_id: uuid.UUID
    amount: Money
    occurred_at: dt.datetime
    memo: str | None = None

    @field_validator("amount")
    @classmethod
    def exact_money(cls, value: Money) -> Money:
        return Money(value.amount_minor, value.currency_code)

    @field_validator("occurred_at")
    @classmethod
    def aware_utc(cls, value: dt.datetime) -> dt.datetime:
        return to_utc(value)


@dataclass(frozen=True, slots=True)
class AddOpeningBalanceResult:
    transaction: TransactionRecord
    audit_id: uuid.UUID
    approval_status: ApprovalStatus = ApprovalStatus.EXPLICITLY_APPROVED
