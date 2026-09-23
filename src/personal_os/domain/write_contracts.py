"""Vendor-neutral inputs/results for the single NORMAL transaction write."""
from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from personal_os.domain.datetime import to_utc
from personal_os.domain.money import Money
from personal_os.domain.records import TransactionRecord


class ApprovalStatus(StrEnum):
    EXPLICITLY_APPROVED = "EXPLICITLY_APPROVED"


class AddTransactionInput(BaseModel):
    """NORMAL/ACTIVE only; no correction, transfer, balance or derived fields."""
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    id: uuid.UUID
    account_id: uuid.UUID
    amount: Money
    occurred_at: dt.datetime
    metric_key: Annotated[str, Field(min_length=1)] | None = None
    memo: str | None = None

    @field_validator("amount")
    @classmethod
    def exact_money(cls, value: Money) -> Money:
        return Money(value.amount_minor, value.currency_code)

    @field_validator("occurred_at")
    @classmethod
    def aware_utc(cls, value: dt.datetime) -> dt.datetime:
        return to_utc(value)

    @field_validator("metric_key")
    @classmethod
    def nonblank_metric(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("metric_key must not be blank")
        return value


class WriteContext(BaseModel):
    """Explicit approval supplied by trusted caller, not inferred by the service.

    A future adapter must obtain approval for these exact arguments externally;
    an AI-generated boolean is not evidence of human approval.
    """
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    actor: Annotated[str, Field(min_length=1)]
    reason: Annotated[str, Field(min_length=1)]
    approved: bool = False

    @field_validator("actor", "reason")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("audit metadata must not be blank")
        return value


@dataclass(frozen=True, slots=True)
class AddTransactionResult:
    transaction: TransactionRecord
    audit_id: uuid.UUID
    approval_status: ApprovalStatus = ApprovalStatus.EXPLICITLY_APPROVED


def canonical_transaction(record: TransactionRecord) -> str:
    """Complete written fact, deterministic UTF-8 JSON with UTC microseconds.

    UUIDs are lowercase hyphenated strings; null fields are retained. No float,
    inferred provenance, approval metadata, or derived financial value is added.
    """
    return json.dumps({
        "id": str(record.id),
        "account_id": str(record.account_id),
        "transaction_type": record.transaction_type.value,
        "amount": {"amount_minor": record.amount.amount_minor,
                   "currency_code": record.amount.currency_code},
        "occurred_at": to_utc(record.occurred_at).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "status": record.status.value,
        "correction_of": None if record.correction_of is None else str(record.correction_of),
        "metric_key": record.metric_key,
        "transfer_group_id": None if record.transfer_group_id is None else str(record.transfer_group_id),
        "memo": record.memo,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
