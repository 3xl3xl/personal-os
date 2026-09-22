"""Finance read composition over a Unit-of-Work abstraction.

This remains in the Service Layer without importing SQLAlchemy, SQLite, ORM
models, or concrete repositories. The caller supplies a Unit-of-Work factory;
production/test composition decides which persistence implementation backs it.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any, Protocol, TypeVar
from zoneinfo import ZoneInfo

from personal_os.domain.read_contracts import FinanceReadValue, MonthlyRevenueReadValue
from personal_os.services.read_contract import FinanceReadContract, FinanceReadDependencies

T = TypeVar("T")


class ReadUnitOfWork(Protocol):
    accounts: Any
    transactions: Any
    capital_buckets: Any
    bucket_allocations: Any
    financial_targets: Any
    monthly_targets: Any

    def __enter__(self) -> "ReadUnitOfWork": ...
    def __exit__(self, exc_type, exc, tb) -> None: ...


UnitOfWorkFactory = Callable[[], ReadUnitOfWork]


def _read(uow_factory: UnitOfWorkFactory, operation: Callable[[FinanceReadContract], T]) -> T:
    with uow_factory() as uow:
        contract = FinanceReadContract(
            FinanceReadDependencies(
                accounts=uow.accounts,
                transactions=uow.transactions,
                buckets=uow.capital_buckets,
                allocations=uow.bucket_allocations,
                financial_targets=uow.financial_targets,
                monthly_targets=uow.monthly_targets,
            )
        )
        return operation(contract)


def get_net_worth(uow_factory: UnitOfWorkFactory, *, evaluation_time: dt.datetime) -> FinanceReadValue:
    return _read(uow_factory, lambda c: c.get_net_worth(evaluation_time=evaluation_time))


def get_available_capital(uow_factory: UnitOfWorkFactory, *, evaluation_time: dt.datetime) -> FinanceReadValue:
    return _read(uow_factory, lambda c: c.get_available_capital(evaluation_time=evaluation_time))


def get_tax_reserve(uow_factory: UnitOfWorkFactory, *, evaluation_time: dt.datetime) -> FinanceReadValue:
    return _read(uow_factory, lambda c: c.get_tax_reserve(evaluation_time=evaluation_time))


def get_goal_gap(uow_factory: UnitOfWorkFactory, *, metric_key: str, evaluation_time: dt.datetime) -> FinanceReadValue:
    return _read(uow_factory, lambda c: c.get_goal_gap(metric_key=metric_key, evaluation_time=evaluation_time))


def get_required_revenue(
    uow_factory: UnitOfWorkFactory,
    *,
    metric_key: str,
    evaluation_time: dt.datetime,
    business_timezone: ZoneInfo,
) -> MonthlyRevenueReadValue:
    return _read(
        uow_factory,
        lambda c: c.get_required_revenue(
            metric_key=metric_key,
            evaluation_time=evaluation_time,
            business_timezone=business_timezone,
        ),
    )
