"""Finance v0.1 read calculations.

Architecture boundary: this module depends only on domain types and
repository Protocols. It deliberately knows nothing about SQLAlchemy,
SQLite, ORM models, Alembic, or persistence configuration.

Normative definitions: PERSONAL_OS_SPEC.md §32.1.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from personal_os.domain.datetime import require_aware, to_timezone, to_utc
from personal_os.domain.enums import AccountType, BucketRole, TransactionStatus
from personal_os.domain.finance_results import FinanceValueResult, MonthlyRevenueResult
from personal_os.domain.money import Money
from personal_os.domain.records import FinancialTargetRecord, MonthlyTargetRecord
from personal_os.repository.protocols import (
    AccountRepositoryProtocol,
    BucketAllocationRepositoryProtocol,
    CapitalBucketRepositoryProtocol,
    FinancialTargetRepositoryProtocol,
    MonthlyTargetRepositoryProtocol,
    TransactionRepositoryProtocol,
)


class TargetNotFoundError(LookupError):
    """No target version is effective at the requested evaluation time."""


class NoFinancialDataError(LookupError):
    """A currency-bearing result cannot be derived because no facts exist."""


def _sum_money(values: list[Money], *, empty_currency: str | None = None) -> Money:
    if not values:
        if empty_currency is None:
            raise NoFinancialDataError("cannot derive a currency from an empty fact set")
        return Money(0, empty_currency)
    total = Money(0, values[0].currency_code)
    for value in values:
        total = total + value
    return total


def _active_financial_target(
    versions: list[FinancialTargetRecord], evaluation_time: dt.datetime
) -> FinancialTargetRecord:
    evaluation_utc = to_utc(evaluation_time)
    eligible = [v for v in versions if to_utc(v.effective_from) <= evaluation_utc]
    if not eligible:
        raise TargetNotFoundError("no FinancialTarget is effective at evaluation_time")
    return max(eligible, key=lambda v: to_utc(v.effective_from))


def _active_monthly_target(
    versions: list[MonthlyTargetRecord], evaluation_time: dt.datetime
) -> MonthlyTargetRecord:
    evaluation_utc = to_utc(evaluation_time)
    eligible = [v for v in versions if to_utc(v.effective_from) <= evaluation_utc]
    if not eligible:
        raise TargetNotFoundError("no MonthlyTarget is effective at evaluation_time")
    return max(eligible, key=lambda v: to_utc(v.effective_from))


def net_worth(
    accounts: AccountRepositoryProtocol,
    transactions: TransactionRepositoryProtocol,
    *,
    evaluation_time: dt.datetime,
) -> FinanceValueResult:
    """Q1: sum account balances derived from ACTIVE ledger transactions."""
    as_of = to_utc(evaluation_time)
    account_balances: list[Money] = []
    for account in accounts.list_all():
        active = [
            tx.amount
            for tx in transactions.list_by_account(account.id)
            if tx.status == TransactionStatus.ACTIVE and to_utc(tx.occurred_at) <= as_of
        ]
        # The account currency is an actual stored fact and gives an empty
        # ledger a well-defined zero without assuming JPY or another currency.
        account_balances.append(_sum_money(active, empty_currency=account.currency_code))
    value = _sum_money(account_balances)
    return FinanceValueResult(metric_key="net_worth", value=value, as_of=as_of)


def available_capital(
    accounts: AccountRepositoryProtocol,
    buckets: CapitalBucketRepositoryProtocol,
    allocations: BucketAllocationRepositoryProtocol,
    *,
    evaluation_time: dt.datetime,
) -> FinanceValueResult:
    """Q2: unprotected allocations belonging to CASH accounts."""
    as_of = to_utc(evaluation_time)
    values: list[Money] = []
    cash_currencies: list[str] = []
    for account in accounts.list_all():
        if account.account_type != AccountType.CASH:
            continue
        cash_currencies.append(account.currency_code)
        for bucket in buckets.list_by_account(account.id):
            if bucket.is_protected:
                continue
            values.extend(
                allocation.amount
                for allocation in allocations.list_by_bucket(bucket.id)
                if to_utc(allocation.created_at) <= as_of
            )
    empty_currency = cash_currencies[0] if len(set(cash_currencies)) == 1 else None
    value = _sum_money(values, empty_currency=empty_currency)
    return FinanceValueResult(metric_key="available_capital", value=value, as_of=as_of)


def tax_reserved(
    accounts: AccountRepositoryProtocol,
    buckets: CapitalBucketRepositoryProtocol,
    allocations: BucketAllocationRepositoryProtocol,
    *,
    evaluation_time: dt.datetime,
) -> FinanceValueResult:
    """Q3: allocations in every TAX_RESERVE-role bucket; names are irrelevant."""
    as_of = to_utc(evaluation_time)
    values: list[Money] = []
    candidate_currencies: list[str] = []
    for account in accounts.list_all():
        for bucket in buckets.list_by_account(account.id):
            if bucket.bucket_role != BucketRole.TAX_RESERVE:
                continue
            candidate_currencies.append(account.currency_code)
            values.extend(
                allocation.amount
                for allocation in allocations.list_by_bucket(bucket.id)
                if to_utc(allocation.created_at) <= as_of
            )
    empty_currency = (
        candidate_currencies[0] if len(set(candidate_currencies)) == 1 else None
    )
    value = _sum_money(values, empty_currency=empty_currency)
    return FinanceValueResult(metric_key="tax_reserved", value=value, as_of=as_of)


def goal_gap(
    accounts: AccountRepositoryProtocol,
    transactions: TransactionRepositoryProtocol,
    targets: FinancialTargetRepositoryProtocol,
    *,
    metric_key: str,
    evaluation_time: dt.datetime,
) -> FinanceValueResult:
    """Q4 Finance v0.1 net-worth goal: active target minus derived Net Worth."""
    as_of = to_utc(evaluation_time)
    target = _active_financial_target(targets.list_by_metric(metric_key), as_of)
    actual = net_worth(accounts, transactions, evaluation_time=as_of).value
    return FinanceValueResult(
        metric_key=metric_key,
        value=target.target_amount - actual,
        as_of=as_of,
    )


def required_monthly_revenue(
    accounts: AccountRepositoryProtocol,
    transactions: TransactionRepositoryProtocol,
    targets: MonthlyTargetRepositoryProtocol,
    *,
    metric_key: str,
    evaluation_time: dt.datetime,
    business_timezone: ZoneInfo,
) -> MonthlyRevenueResult:
    """Q5: remaining self-generated revenue required in the target local month."""
    require_aware(evaluation_time)
    if not isinstance(business_timezone, ZoneInfo):
        raise TypeError("business_timezone must be zoneinfo.ZoneInfo")
    as_of = to_utc(evaluation_time)
    local_evaluation = to_timezone(as_of, business_timezone)
    year, month = local_evaluation.year, local_evaluation.month

    target = _active_monthly_target(
        targets.list_by_metric_year_month(metric_key, year, month), as_of
    )

    actual_values: list[Money] = []
    for account in accounts.list_all():
        for tx in transactions.list_by_account(account.id):
            if tx.status != TransactionStatus.ACTIVE or tx.metric_key != metric_key:
                continue
            if to_utc(tx.occurred_at) > as_of:
                continue
            local_occurred = to_timezone(tx.occurred_at, business_timezone)
            if (local_occurred.year, local_occurred.month) == (year, month):
                actual_values.append(tx.amount)

    actual = _sum_money(
        actual_values, empty_currency=target.target_amount.currency_code
    )
    variance = target.target_amount - actual
    required = Money(
        max(0, variance.amount_minor),
        variance.currency_code,
    )
    return MonthlyRevenueResult(
        metric_key=metric_key,
        year=year,
        month=month,
        target=target.target_amount,
        actual=actual,
        variance=variance,
        required=required,
        as_of=as_of,
    )
