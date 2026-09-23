"""Vendor-neutral inputs/results for the single Account-creation write.

Mirrors personal_os.domain.write_contracts (the transaction write's shapes);
WriteContext and ApprovalStatus are shared as-is since neither carries any
transaction-specific field. This module is additive only -- it never edits
write_contracts.py, which stays exactly as Step 19/20 left it.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from personal_os.domain.datetime import to_utc
from personal_os.domain.enums import AccountType
from personal_os.domain.records import AccountRecord
from personal_os.domain.write_contracts import ApprovalStatus


class AddAccountInput(BaseModel):
    """One new ACTIVE Account. No status transition, close, or rename here."""
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    id: uuid.UUID
    name: Annotated[str, Field(min_length=1)]
    account_type: AccountType
    currency_code: Annotated[str, Field(min_length=1)]
    opened_at: dt.datetime

    @field_validator("name", "currency_code")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("opened_at")
    @classmethod
    def aware_utc(cls, value: dt.datetime) -> dt.datetime:
        return to_utc(value)


@dataclass(frozen=True, slots=True)
class AddAccountResult:
    account: AccountRecord
    audit_id: uuid.UUID
    approval_status: ApprovalStatus = ApprovalStatus.EXPLICITLY_APPROVED


def canonical_account(record: AccountRecord) -> str:
    """Complete written fact, deterministic UTF-8 JSON with UTC microseconds."""
    return json.dumps({
        "id": str(record.id),
        "name": record.name,
        "account_type": record.account_type.value,
        "currency_code": record.currency_code,
        "opened_at": to_utc(record.opened_at).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "status": record.status.value,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
