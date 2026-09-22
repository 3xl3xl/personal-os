"""Vendor-neutral adapter-facing Finance read result DTOs."""
from __future__ import annotations
import datetime as dt
from dataclasses import dataclass
from enum import StrEnum
from personal_os.domain.money import Money

class ValueKind(StrEnum):
    ACTUAL = "ACTUAL"
    TARGET = "TARGET"
    FORECAST = "FORECAST"
    ASSUMPTION = "ASSUMPTION"
    DERIVED = "DERIVED"

@dataclass(frozen=True, slots=True)
class FinanceReadValue:
    metric_key: str
    value: Money
    as_of: dt.datetime
    kind: ValueKind = ValueKind.DERIVED

@dataclass(frozen=True, slots=True)
class MonthlyRevenueReadValue:
    metric_key: str
    year: int
    month: int
    target: Money
    actual: Money
    variance: Money
    required: Money
    as_of: dt.datetime
    target_kind: ValueKind = ValueKind.TARGET
    actual_kind: ValueKind = ValueKind.ACTUAL
    variance_kind: ValueKind = ValueKind.DERIVED
    required_kind: ValueKind = ValueKind.DERIVED
