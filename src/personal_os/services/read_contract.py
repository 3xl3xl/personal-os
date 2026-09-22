"""Vendor-neutral Finance read contract for future MCP/REST adapters."""
from __future__ import annotations
import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo
from personal_os.domain.read_contracts import FinanceReadValue, MonthlyRevenueReadValue
from personal_os.repository.protocols import AccountRepositoryProtocol, BucketAllocationRepositoryProtocol, CapitalBucketRepositoryProtocol, FinancialTargetRepositoryProtocol, MonthlyTargetRepositoryProtocol, TransactionRepositoryProtocol
from personal_os.services import finance
from personal_os.services.permissions import OperationClass, require_permission

@dataclass(frozen=True, slots=True)
class FinanceReadDependencies:
    accounts: AccountRepositoryProtocol
    transactions: TransactionRepositoryProtocol
    buckets: CapitalBucketRepositoryProtocol
    allocations: BucketAllocationRepositoryProtocol
    financial_targets: FinancialTargetRepositoryProtocol
    monthly_targets: MonthlyTargetRepositoryProtocol

class FinanceReadContract:
    def __init__(self, dependencies: FinanceReadDependencies) -> None:
        self._deps = dependencies

    @staticmethod
    def _authorize_read() -> None:
        require_permission(OperationClass.READ)

    @staticmethod
    def _value(result) -> FinanceReadValue:
        return FinanceReadValue(metric_key=result.metric_key, value=result.value, as_of=result.as_of)

    def get_net_worth(self, *, evaluation_time: dt.datetime) -> FinanceReadValue:
        self._authorize_read()
        return self._value(finance.net_worth(self._deps.accounts, self._deps.transactions, evaluation_time=evaluation_time))

    def get_available_capital(self, *, evaluation_time: dt.datetime) -> FinanceReadValue:
        self._authorize_read()
        return self._value(finance.available_capital(self._deps.accounts, self._deps.buckets, self._deps.allocations, evaluation_time=evaluation_time))

    def get_tax_reserve(self, *, evaluation_time: dt.datetime) -> FinanceReadValue:
        self._authorize_read()
        return self._value(finance.tax_reserved(self._deps.accounts, self._deps.buckets, self._deps.allocations, evaluation_time=evaluation_time))

    def get_goal_gap(self, *, metric_key: str, evaluation_time: dt.datetime) -> FinanceReadValue:
        self._authorize_read()
        return self._value(finance.goal_gap(self._deps.accounts, self._deps.transactions, self._deps.financial_targets, metric_key=metric_key, evaluation_time=evaluation_time))

    def get_required_revenue(self, *, metric_key: str, evaluation_time: dt.datetime, business_timezone: ZoneInfo) -> MonthlyRevenueReadValue:
        self._authorize_read()
        r = finance.required_monthly_revenue(self._deps.accounts, self._deps.transactions, self._deps.monthly_targets, metric_key=metric_key, evaluation_time=evaluation_time, business_timezone=business_timezone)
        return MonthlyRevenueReadValue(metric_key=r.metric_key, year=r.year, month=r.month, target=r.target, actual=r.actual, variance=r.variance, required=r.required, as_of=r.as_of)
