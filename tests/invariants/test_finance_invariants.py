from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import replace
from zoneinfo import ZoneInfo

import pytest

from personal_os.domain.enums import (
    AccountStatus,
    AccountType,
    BucketRole,
    CapitalBucketStatus,
    EntryType,
    TransactionKind,
    TransactionStatus,
)
from personal_os.domain.money import CurrencyMismatchError, Money
from personal_os.domain.records import (
    AccountRecord,
    BucketAllocationRecord,
    CapitalBucketRecord,
    FinancialTargetRecord,
    MonthlyTargetRecord,
    TransactionRecord,
)
from personal_os.services.finance import (
    available_capital,
    goal_gap,
    net_worth,
    required_monthly_revenue,
    tax_reserved,
)

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 22, 12, 0, tzinfo=UTC)


class Accounts:
    def __init__(self, rows): self.rows = rows
    def list_all(self): return list(self.rows)


class Transactions:
    def __init__(self, rows): self.rows = rows
    def list_by_account(self, account_id):
        return [row for row in self.rows if row.account_id == account_id]


class Buckets:
    def __init__(self, rows): self.rows = rows
    def list_by_account(self, account_id):
        return [row for row in self.rows if row.account_id == account_id]


class Allocations:
    def __init__(self, rows): self.rows = rows
    def list_by_bucket(self, bucket_id):
        return [row for row in self.rows if row.bucket_id == bucket_id]


class FinancialTargets:
    def __init__(self, rows): self.rows = rows
    def list_by_metric(self, metric_key):
        return [row for row in self.rows if row.metric_key == metric_key]


class MonthlyTargets:
    def __init__(self, rows): self.rows = rows
    def list_by_metric_year_month(self, metric_key, year, month):
        return [
            row for row in self.rows
            if row.metric_key == metric_key and row.year == year and row.month == month
        ]


def account(*, kind=AccountType.CASH, currency="JPY"):
    return AccountRecord(
        id=uuid.uuid4(),
        name="synthetic",
        account_type=kind,
        currency_code=currency,
        opened_at=NOW - dt.timedelta(days=30),
        status=AccountStatus.ACTIVE,
    )


def tx(a, amount, *, currency=None, status=TransactionStatus.ACTIVE,
       occurred=NOW - dt.timedelta(hours=1), metric=None,
       kind=TransactionKind.NORMAL, transfer_group_id=None):
    return TransactionRecord(
        id=uuid.uuid4(),
        account_id=a.id,
        transaction_type=kind,
        amount=Money(amount, currency or a.currency_code),
        occurred_at=occurred,
        status=status,
        metric_key=metric,
        transfer_group_id=transfer_group_id,
    )


def bucket(a, *, role=BucketRole.GENERAL, protected=False, name="synthetic"):
    return CapitalBucketRecord(
        id=uuid.uuid4(),
        account_id=a.id,
        name=name,
        bucket_role=role,
        is_protected=protected,
        status=CapitalBucketStatus.ACTIVE,
        created_at=NOW - dt.timedelta(days=20),
    )


def allocation(a, b, amount, *, currency=None, entry_type=EntryType.CASH_LINKED,
               reallocation_group_id=None):
    return BucketAllocationRecord(
        id=uuid.uuid4(),
        bucket_id=b.id,
        account_id=a.id,
        amount=Money(amount, currency or a.currency_code),
        entry_type=entry_type,
        created_at=NOW - dt.timedelta(minutes=10),
        reallocation_group_id=reallocation_group_id,
        originating_transaction_id=uuid.uuid4() if entry_type is EntryType.CASH_LINKED else None,
    )


def ftarget(amount, effective, *, currency="JPY", metric="net_worth"):
    return FinancialTargetRecord(
        id=uuid.uuid4(),
        metric_key=metric,
        target_amount=Money(amount, currency),
        effective_from=effective,
        created_at=effective,
    )


def mtarget(amount, effective, *, currency="JPY", metric="self_revenue",
            year=2026, month=9):
    return MonthlyTargetRecord(
        id=uuid.uuid4(),
        metric_key=metric,
        year=year,
        month=month,
        target_amount=Money(amount, currency),
        effective_from=effective,
        created_at=effective,
    )


def test_net_worth_is_ledger_derived_and_never_adds_bucket_allocations():
    a = account()
    b = bucket(a)
    result = net_worth(
        Accounts([a]),
        Transactions([tx(a, 10_000), tx(a, -2_500)]),
        evaluation_time=NOW,
    )
    # A bucket allocation is an allocation of the same cash, not another asset.
    assert result.value == Money(7_500, "JPY")
    assert allocation(a, b, 6_000).amount == Money(6_000, "JPY")


def test_net_worth_uses_only_active_nonfuture_ledger_facts():
    a = account()
    rows = [
        tx(a, 1_000),
        tx(a, 9_000, status=TransactionStatus.VOIDED),
        tx(a, 8_000, occurred=NOW + dt.timedelta(seconds=1)),
    ]
    assert net_worth(Accounts([a]), Transactions(rows), evaluation_time=NOW).value == Money(1_000, "JPY")


def test_finance_never_implicitly_aggregates_currencies():
    jpy = account(currency="JPY")
    usd = account(currency="USD")
    with pytest.raises(CurrencyMismatchError):
        net_worth(
            Accounts([jpy, usd]),
            Transactions([tx(jpy, 100), tx(usd, 100)]),
            evaluation_time=NOW,
        )


def test_available_capital_is_only_unprotected_cash_allocation():
    cash = account()
    investment = account(kind=AccountType.INVESTMENT)
    free = bucket(cash, protected=False)
    protected = bucket(cash, protected=True)
    investment_bucket = bucket(investment, protected=False)
    result = available_capital(
        Accounts([cash, investment]),
        Buckets([free, protected, investment_bucket]),
        Allocations([
            allocation(cash, free, 500),
            allocation(cash, protected, 700),
            allocation(investment, investment_bucket, 900),
        ]),
        evaluation_time=NOW,
    )
    assert result.value == Money(500, "JPY")


def test_tax_reserved_is_role_based_not_name_based_and_allows_multiple_buckets():
    a = account()
    first = bucket(a, role=BucketRole.TAX_RESERVE, name="renamed freely")
    second = bucket(a, role=BucketRole.TAX_RESERVE, name="anything")
    misleading = bucket(a, role=BucketRole.GENERAL, name="TAX RESERVE")
    result = tax_reserved(
        Accounts([a]),
        Buckets([first, second, misleading]),
        Allocations([
            allocation(a, first, 100),
            allocation(a, second, 200),
            allocation(a, misleading, 999),
        ]),
        evaluation_time=NOW,
    )
    assert result.value == Money(300, "JPY")


def test_bucket_role_and_protection_are_independent_semantics():
    a = account()
    tax = bucket(a, role=BucketRole.TAX_RESERVE, protected=False)
    general = bucket(a, role=BucketRole.GENERAL, protected=True)
    assert tax.bucket_role is BucketRole.TAX_RESERVE and tax.is_protected is False
    assert general.bucket_role is BucketRole.GENERAL and general.is_protected is True


def test_reallocation_is_zero_sum_and_does_not_create_account_cash():
    a = account()
    left, right = bucket(a), bucket(a)
    group = uuid.uuid4()
    legs = [
        allocation(a, left, -400, entry_type=EntryType.REALLOCATION, reallocation_group_id=group),
        allocation(a, right, 400, entry_type=EntryType.REALLOCATION, reallocation_group_id=group),
    ]
    assert sum(leg.amount.amount_minor for leg in legs) == 0
    assert all(leg.originating_transaction_id is None for leg in legs)
    assert net_worth(Accounts([a]), Transactions([]), evaluation_time=NOW).value == Money(0, "JPY")


def test_transfer_two_legs_are_zero_sum_and_do_not_change_net_worth():
    source, destination = account(), account()
    group = uuid.uuid4()
    legs = [
        tx(source, -1_000, kind=TransactionKind.TRANSFER, transfer_group_id=group),
        tx(destination, 1_000, kind=TransactionKind.TRANSFER, transfer_group_id=group),
    ]
    assert sum(leg.amount.amount_minor for leg in legs) == 0
    assert net_worth(Accounts([source, destination]), Transactions(legs), evaluation_time=NOW).value == Money(0, "JPY")


def test_goal_gap_is_signed_and_active_target_is_latest_effective_version():
    a = account()
    targets = FinancialTargets([
        ftarget(1_000, NOW - dt.timedelta(days=10)),
        ftarget(1_500, NOW - dt.timedelta(days=1)),
        ftarget(9_999, NOW + dt.timedelta(days=1)),
    ])
    result = goal_gap(
        Accounts([a]), Transactions([tx(a, 2_000)]), targets,
        metric_key="net_worth", evaluation_time=NOW,
    )
    assert result.value == Money(-500, "JPY")


def test_required_monthly_revenue_is_target_minus_actual_clamped_at_zero():
    a = account()
    targets = MonthlyTargets([mtarget(1_000, NOW - dt.timedelta(days=1))])
    result = required_monthly_revenue(
        Accounts([a]),
        Transactions([tx(a, 1_200, metric="self_revenue")]),
        targets,
        metric_key="self_revenue",
        evaluation_time=NOW,
        business_timezone=ZoneInfo("UTC"),
    )
    assert result.variance == Money(-200, "JPY")
    assert result.required == Money(0, "JPY")


def test_required_monthly_revenue_keeps_revenue_distinct_by_metric():
    a = account()
    targets = MonthlyTargets([mtarget(1_000, NOW - dt.timedelta(days=1))])
    result = required_monthly_revenue(
        Accounts([a]),
        Transactions([
            tx(a, 250, metric="self_revenue"),
            tx(a, 900, metric="profit"),
        ]),
        targets,
        metric_key="self_revenue",
        evaluation_time=NOW,
        business_timezone=ZoneInfo("UTC"),
    )
    assert result.actual == Money(250, "JPY")
    assert result.required == Money(750, "JPY")


def test_target_versions_are_append_only_facts_selected_by_evaluation_time():
    old = mtarget(1_000, NOW - dt.timedelta(days=10))
    new = mtarget(2_000, NOW - dt.timedelta(days=1))
    future = mtarget(3_000, NOW + dt.timedelta(days=1))
    a = account()
    result = required_monthly_revenue(
        Accounts([a]), Transactions([]), MonthlyTargets([old, new, future]),
        metric_key="self_revenue", evaluation_time=NOW,
        business_timezone=ZoneInfo("UTC"),
    )
    assert result.target == Money(2_000, "JPY")
    assert old != replace(old, target_amount=Money(9_999, "JPY"))
