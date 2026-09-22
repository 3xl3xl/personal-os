"""Immutable result DTOs for Finance v0.1 read-time calculations.

These values are derived at runtime from stored facts/planning records.
They are never persistence entities and must not become a replacement
source of truth.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from personal_os.domain.money import Money


@dataclass(frozen=True, slots=True)
class FinanceValueResult:
    metric_key: str
    value: Money
    as_of: dt.datetime


@dataclass(frozen=True, slots=True)
class MonthlyRevenueResult:
    metric_key: str
    year: int
    month: int
    target: Money
    actual: Money
    variance: Money
    required: Money
    as_of: dt.datetime
