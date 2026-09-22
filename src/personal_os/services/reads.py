"""Runtime composition for the Finance v0.1 read path.

This module is deliberately the composition root: it knows the concrete UnitOfWork
and wires its repositories into the vendor-neutral FinanceReadContract. Business
calculations remain in services.finance and permission checks remain in the
contract/service boundary.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import TypeVar
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, sessionmaker

from personal_os.domain.read_contracts import FinanceReadValue, MonthlyRevenueReadValue
from personal_os.repository.unit_of_work import UnitOfWork
from personal_os.services.read_contract import FinanceReadContract, FinanceReadDependencies

T = TypeVar("T")


def _read(session_factory: sessionmaker[Session], operation: Callable[[FinanceReadContract], T]) -> T:
    with UnitOfWork(session_factory) as uow:
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


def get_net_worth(session_factory: sessionmaker[Session], *, evaluation_time: dt.datetime) -> FinanceReadValue:
    return _read(session_factory, lambda c: c.get_net_worth(evaluation_time=evaluation_time))


def get_available_capital(session_factory: sessionmaker[Session], *, evaluation_time: dt.datetime) -> FinanceReadValue:
    return _read(session_factory, lambda c: c.get_available_capital(evaluation_time=evaluation_time))


def get_tax_reserve(session_factory: sessionmaker[Session], *, evaluation_time: dt.datetime) -> FinanceReadValue:
    return _read(session_factory, lambda c: c.get_tax_reserve(evaluation_time=evaluation_time))


def get_goal_gap(session_factory: sessionmaker[Session], *, metric_key: str, evaluation_time: dt.datetime) -> FinanceReadValue:
    return _read(session_factory, lambda c: c.get_goal_gap(metric_key=metric_key, evaluation_time=evaluation_time))


def get_required_revenue(
    session_factory: sessionmaker[Session],
    *,
    metric_key: str,
    evaluation_time: dt.datetime,
    business_timezone: ZoneInfo,
) -> MonthlyRevenueReadValue:
    return _read(
        session_factory,
        lambda c: c.get_required_revenue(
            metric_key=metric_key,
            evaluation_time=evaluation_time,
            business_timezone=business_timezone,
        ),
    )
