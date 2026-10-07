"""Minimal immutable requests for append-only bucket writes."""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from personal_os.domain.datetime import to_utc
from personal_os.domain.enums import BucketRole
from personal_os.domain.money import Money


class BucketWriteInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    id: uuid.UUID
    created_at: dt.datetime

    @field_validator("created_at")
    @classmethod
    def aware(cls, value: dt.datetime) -> dt.datetime:
        return to_utc(value)


class AddCapitalBucketInput(BucketWriteInput):
    account_id: uuid.UUID
    name: Annotated[str, Field(min_length=1)]
    bucket_role: BucketRole
    is_protected: bool

    @field_validator("name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("blank name")
        return value


class AllocationInput(BucketWriteInput):
    amount_minor: Annotated[int, Field(ge=-(2**63)+1, le=2**63-1)]
    currency_code: str

    @field_validator("currency_code")
    @classmethod
    def currency(cls, value: str) -> str:
        Money(0, value)
        return value


class AddCashLinkedAllocationInput(AllocationInput):
    """Creates a NEW NORMAL transaction and its entire allocation atomically."""
    bucket_id: uuid.UUID


class ReallocateCapitalInput(AllocationInput):
    from_bucket_id: uuid.UUID
    to_bucket_id: uuid.UUID
    amount_minor: Annotated[int, Field(gt=0, le=2**63-1)]
