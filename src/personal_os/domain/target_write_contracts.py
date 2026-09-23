"""Vendor-neutral inputs/results for registering one FinancialTarget or
MonthlyTarget version (Finance v0.1 Schema Design Q4/Q5). Both write shapes
live together here since they are the same append/version-only family and
share every field except MonthlyTarget's (year, month). WriteContext and
ApprovalStatus are reused as-is from domain/write_contracts.py.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from personal_os.domain.datetime import to_utc
from personal_os.domain.money import Money
from personal_os.domain.records import FinancialTargetRecord, MonthlyTargetRecord
from personal_os.domain.write_contracts import ApprovalStatus


class AddFinancialTargetInput(BaseModel):
    """One new version of a metric's overall target (Q4). Append/version-
    only -- there is no update or delete; a changed target is a new row
    with a later effective_from."""
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    id: uuid.UUID
    metric_key: Annotated[str, Field(min_length=1)]
    target_amount: Money
    effective_from: dt.datetime

    @field_validator("metric_key")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("target_amount")
    @classmethod
    def exact_money(cls, value: Money) -> Money:
        return Money(value.amount_minor, value.currency_code)

    @field_validator("effective_from")
    @classmethod
    def aware_utc(cls, value: dt.datetime) -> dt.datetime:
        return to_utc(value)


class AddMonthlyTargetInput(BaseModel):
    """One new version of a metric's target for a specific (year, month) (Q5).
    Append/version-only, same as AddFinancialTargetInput."""
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    id: uuid.UUID
    metric_key: Annotated[str, Field(min_length=1)]
    year: int
    month: Annotated[int, Field(ge=1, le=12)]
    target_amount: Money
    effective_from: dt.datetime

    @field_validator("metric_key")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("target_amount")
    @classmethod
    def exact_money(cls, value: Money) -> Money:
        return Money(value.amount_minor, value.currency_code)

    @field_validator("effective_from")
    @classmethod
    def aware_utc(cls, value: dt.datetime) -> dt.datetime:
        return to_utc(value)


@dataclass(frozen=True, slots=True)
class AddFinancialTargetResult:
    target: FinancialTargetRecord
    audit_id: uuid.UUID
    approval_status: ApprovalStatus = ApprovalStatus.EXPLICITLY_APPROVED


@dataclass(frozen=True, slots=True)
class AddMonthlyTargetResult:
    target: MonthlyTargetRecord
    audit_id: uuid.UUID
    approval_status: ApprovalStatus = ApprovalStatus.EXPLICITLY_APPROVED


def canonical_financial_target(record: FinancialTargetRecord) -> str:
    return json.dumps({
        "id": str(record.id),
        "metric_key": record.metric_key,
        "target_amount": {"amount_minor": record.target_amount.amount_minor,
                           "currency_code": record.target_amount.currency_code},
        "effective_from": to_utc(record.effective_from).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "created_at": to_utc(record.created_at).isoformat(timespec="microseconds").replace("+00:00", "Z"),
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def canonical_monthly_target(record: MonthlyTargetRecord) -> str:
    return json.dumps({
        "id": str(record.id),
        "metric_key": record.metric_key,
        "year": record.year,
        "month": record.month,
        "target_amount": {"amount_minor": record.target_amount.amount_minor,
                           "currency_code": record.target_amount.currency_code},
        "effective_from": to_utc(record.effective_from).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "created_at": to_utc(record.created_at).isoformat(timespec="microseconds").replace("+00:00", "Z"),
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
