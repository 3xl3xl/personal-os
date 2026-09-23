"""Vendor-neutral inputs/results for registering one FinancialMetric.

Mirrors domain/account_write_contracts.py's shape. WriteContext and
ApprovalStatus are reused as-is from domain/write_contracts.py.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from personal_os.domain.datetime import to_utc
from personal_os.domain.records import FinancialMetricRecord
from personal_os.domain.write_contracts import ApprovalStatus


class AddMetricInput(BaseModel):
    """One new tracked KPI definition. Never a revenue source or accounting
    category -- FinancialMetric exists only to support Target-vs-Actual
    tracking (Finance v0.1 Schema Design, Decision 3)."""
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    id: uuid.UUID
    key: Annotated[str, Field(min_length=1)]
    display_name: Annotated[str, Field(min_length=1)]

    @field_validator("key", "display_name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


@dataclass(frozen=True, slots=True)
class AddMetricResult:
    metric: FinancialMetricRecord
    audit_id: uuid.UUID
    approval_status: ApprovalStatus = ApprovalStatus.EXPLICITLY_APPROVED


def canonical_metric(record: FinancialMetricRecord) -> str:
    """Complete written fact, deterministic UTF-8 JSON with UTC microseconds."""
    return json.dumps({
        "id": str(record.id),
        "key": record.key,
        "display_name": record.display_name,
        "created_at": to_utc(record.created_at).isoformat(timespec="microseconds").replace("+00:00", "Z"),
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
