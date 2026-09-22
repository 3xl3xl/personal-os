from __future__ import annotations

import ast
import datetime as dt
import uuid
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from personal_os.domain.enums import (
    AccountStatus, AccountType, BucketRole, CapitalBucketStatus,
    EntryType, TransactionKind, TransactionStatus,
)
from personal_os.domain.money import CurrencyMismatchError, Money
from personal_os.domain.records import (
    AccountRecord, BucketAllocationRecord, CapitalBucketRecord,
    FinancialTargetRecord, MonthlyTargetRecord, TransactionRecord,
)
from personal_os.services.finance import (
    TargetNotFoundError, available_capital, goal_gap, net_worth,
    required_monthly_revenue, tax_reserved,
)

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 22, 12, tzinfo=UTC)


class Accounts:
    def __init__(self, rows): self.rows = rows
    def list_all(self): return list(self.rows)


class Transactions:
    def __init__(self, rows): self.rows = rows
    def list_by_account(self, account_id):
        return [r for r in self.rows if r.account_id == account_id]


class Buckets:
    def __init__(self, rows): self.rows = rows
    def list_by_account(self, account_id):
        return [r for r in self.rows if r.account_id == account_id]


class Allocations:
    def __init__(self, rows): self.rows = rows
    def list_by_bucket(self, bucket_id):
        return [r for r in self.rows if r.bucket_id == bucket_id]


class FinancialTargets:
    def __init__(self, rows): self.rows = rows
    def list_by_metric(self, metric_key):
        return [r for r in self.rows if r.metric_key == metric_key]


class MonthlyTargets:
    def __init__(self, rows): self.rows = rows
    def list_by_metric_year_month(self, metric_key, year, month):
        return [r for r in self.rows if r.metric_key == metric_key and r.year == year and r.month == month]


def account(currency="JPY", kind=AccountType.CASH):
    return AccountRecord(uuid.uuid4(), "a", kind, currency, NOW, AccountStatus.ACTIVE)


def tx(a, amount, *, currency="JPY", status=TransactionStatus.ACTIVE,
       metric=None, occurred=NOW, kind=TransactionKind.NORMAL):
    return TransactionRecord(uuid.uuid4(), a.id, kind, Money(amount, currency),
                             occurred, status, metric_key=metric)


def bucket(a, *, protected=False, role=BucketRole.GENERAL, name="bucket"):
    return CapitalBucketRecord(uuid.uuid4(), a.id, name, role, protected,
                               CapitalBucketStatus.ACTIVE, NOW)


def allocation(a, b, amount, *, currency="JPY", created=NOW):
    return BucketAllocationRecord(uuid.uuid4(), b.id, a.id, Money(amount, currency),
                                  EntryType.REALLOCATION, created,
                                  reallocation_group_id=uuid.uuid4())


def ftarget(amount, effective, *, currency="JPY", metric="net_worth"):
    return FinancialTargetRecord(uuid.uuid4(), metric, Money(amount, currency), effective, effective)


def mtarget(amount, effective, *, currency="JPY", metric="self_revenue", year=2026, month=9):
    return MonthlyTargetRecord(uuid.uuid4(), metric, year, month, Money(amount, currency), effective, effective)


def test_net_worth_positive_negative_and_multiple_accounts():
    a1, a2 = account(), account(kind=AccountType.LIABILITY)
    rows = [tx(a1, 1000), tx(a1, 500), tx(a2, -400)]
    assert net_worth(Accounts([a1, a2]), Transactions(rows), evaluation_time=NOW).value == Money(1100, "JPY")


def test_net_worth_ignores_voided_and_future_transactions():
    a = account()
    rows = [tx(a, 100), tx(a, 999, status=TransactionStatus.VOIDED),
            tx(a, 777, occurred=NOW + dt.timedelta(seconds=1))]
    assert net_worth(Accounts([a]), Transactions(rows), evaluation_time=NOW).value == Money(100, "JPY")


def test_net_worth_is_ledger_derived_and_has_no_bucket_input():
    a = account()
    result = net_worth(Accounts([a]), Transactions([tx(a, 250)]), evaluation_time=NOW)
    assert result.value == Money(250, "JPY")


def test_net_worth_mixed_currency_rejected_even_for_empty_account():
    with pytest.raises(CurrencyMismatchError):
        net_worth(Accounts([account("JPY"), account("USD")]), Transactions([]), evaluation_time=NOW)


def test_available_capital_excludes_protected_and_non_cash_accounts():
    cash, inv = account(), account(kind=AccountType.INVESTMENT)
    free, protected, inv_bucket = bucket(cash), bucket(cash, protected=True), bucket(inv)
    rows = [allocation(cash, free, 700), allocation(cash, protected, 500), allocation(inv, inv_bucket, 900)]
    result = available_capital(Accounts([cash, inv]), Buckets([free, protected, inv_bucket]),
                               Allocations(rows), evaluation_time=NOW)
    assert result.value == Money(700, "JPY")


def test_available_capital_sums_all_allocation_ledger_entries():
    a = account(); b = bucket(a)
    rows = [allocation(a, b, 1000), allocation(a, b, -250)]
    assert available_capital(Accounts([a]), Buckets([b]), Allocations(rows), evaluation_time=NOW).value == Money(750, "JPY")


def test_available_capital_mixed_cash_currencies_rejected():
    with pytest.raises(CurrencyMismatchError):
        available_capital(Accounts([account("JPY"), account("USD")]), Buckets([]), Allocations([]), evaluation_time=NOW)


def test_tax_reserved_uses_role_not_name_and_supports_multiple_buckets():
    a = account()
    b1 = bucket(a, role=BucketRole.TAX_RESERVE, name="renamed")
    b2 = bucket(a, role=BucketRole.TAX_RESERVE, name="anything")
    general = bucket(a, role=BucketRole.GENERAL, name="tax reserve")
    rows = [allocation(a, b1, 300), allocation(a, b2, 200), allocation(a, general, 999)]
    assert tax_reserved(Accounts([a]), Buckets([b1, b2, general]), Allocations(rows), evaluation_time=NOW).value == Money(500, "JPY")


def test_tax_reserved_mixed_currency_rejected():
    j, u = account("JPY"), account("USD")
    bj, bu = bucket(j, role=BucketRole.TAX_RESERVE), bucket(u, role=BucketRole.TAX_RESERVE)
    with pytest.raises(CurrencyMismatchError):
        tax_reserved(Accounts([j, u]), Buckets([bj, bu]), Allocations([]), evaluation_time=NOW)


def test_goal_gap_selects_latest_effective_target_and_is_signed():
    a = account()
    targets = [ftarget(1000, NOW-dt.timedelta(days=10)), ftarget(800, NOW-dt.timedelta(days=1)),
               ftarget(9999, NOW+dt.timedelta(days=1))]
    result = goal_gap(Accounts([a]), Transactions([tx(a, 900)]), FinancialTargets(targets),
                      metric_key="net_worth", evaluation_time=NOW)
    assert result.value == Money(-100, "JPY")


def test_goal_gap_historical_evaluation_selects_historical_version():
    past = NOW-dt.timedelta(days=5)
    a = account()
    targets = [ftarget(1000, NOW-dt.timedelta(days=10)), ftarget(2000, NOW-dt.timedelta(days=1))]
    result = goal_gap(Accounts([a]), Transactions([tx(a, 400, occurred=past)]), FinancialTargets(targets),
                      metric_key="net_worth", evaluation_time=past)
    assert result.value == Money(600, "JPY")


def test_goal_gap_currency_mismatch_rejected():
    a = account("JPY")
    with pytest.raises(CurrencyMismatchError):
        goal_gap(Accounts([a]), Transactions([]), FinancialTargets([ftarget(1000, NOW, currency="USD")]),
                 metric_key="net_worth", evaluation_time=NOW)


def test_goal_gap_requires_effective_target():
    a = account()
    with pytest.raises(TargetNotFoundError):
        goal_gap(Accounts([a]), Transactions([]), FinancialTargets([ftarget(1000, NOW+dt.timedelta(days=1))]),
                 metric_key="net_worth", evaluation_time=NOW)


def test_required_monthly_revenue_exact_arithmetic_and_clamp():
    a = account()
    targets = MonthlyTargets([mtarget(1000, NOW-dt.timedelta(days=1))])
    result = required_monthly_revenue(Accounts([a]), Transactions([tx(a, 650, metric="self_revenue")]),
                                      targets, metric_key="self_revenue", evaluation_time=NOW,
                                      business_timezone=ZoneInfo("Asia/Tokyo"))
    assert result.actual == Money(650, "JPY")
    assert result.variance == Money(350, "JPY")
    assert result.required == Money(350, "JPY")


def test_required_monthly_revenue_preserves_negative_variance_but_required_is_zero():
    a = account()
    result = required_monthly_revenue(
        Accounts([a]), Transactions([tx(a, 1200, metric="self_revenue")]),
        MonthlyTargets([mtarget(1000, NOW-dt.timedelta(days=1))]),
        metric_key="self_revenue", evaluation_time=NOW, business_timezone=ZoneInfo("UTC"))
    assert result.variance == Money(-200, "JPY")
    assert result.required == Money(0, "JPY")


def test_monthly_target_versioning_ignores_future_and_uses_latest_effective():
    a = account()
    targets = MonthlyTargets([
        mtarget(1000, NOW-dt.timedelta(days=10)),
        mtarget(800, NOW-dt.timedelta(days=1)),
        mtarget(9000, NOW+dt.timedelta(days=1)),
    ])
    result = required_monthly_revenue(Accounts([a]), Transactions([]), targets,
                                      metric_key="self_revenue", evaluation_time=NOW,
                                      business_timezone=ZoneInfo("UTC"))
    assert result.target == Money(800, "JPY")


def test_month_boundary_uses_explicit_business_timezone():
    evaluation = dt.datetime(2026, 10, 1, 0, 30, tzinfo=UTC)
    a = account()
    # 2026-09-30 23:45 UTC is Oct 1 in Tokyo, so it belongs to Tokyo's October.
    revenue = tx(a, 300, metric="self_revenue",
                 occurred=dt.datetime(2026, 9, 30, 23, 45, tzinfo=UTC))
    target = mtarget(1000, dt.datetime(2026, 9, 1, tzinfo=UTC), year=2026, month=10)
    result = required_monthly_revenue(Accounts([a]), Transactions([revenue]), MonthlyTargets([target]),
                                      metric_key="self_revenue", evaluation_time=evaluation,
                                      business_timezone=ZoneInfo("Asia/Tokyo"))
    assert (result.year, result.month) == (2026, 10)
    assert result.actual == Money(300, "JPY")


def test_monthly_actual_excludes_other_metric_voided_future_and_other_month():
    a = account()
    rows = [
        tx(a, 100, metric="self_revenue"),
        tx(a, 200, metric="other"),
        tx(a, 300, metric="self_revenue", status=TransactionStatus.VOIDED),
        tx(a, 400, metric="self_revenue", occurred=NOW+dt.timedelta(seconds=1)),
        tx(a, 500, metric="self_revenue", occurred=dt.datetime(2026, 8, 31, 23, tzinfo=UTC)),
    ]
    result = required_monthly_revenue(
        Accounts([a]), Transactions(rows), MonthlyTargets([mtarget(1000, NOW-dt.timedelta(days=1))]),
        metric_key="self_revenue", evaluation_time=NOW, business_timezone=ZoneInfo("UTC"))
    assert result.actual == Money(100, "JPY")


def test_monthly_revenue_currency_mismatch_rejected():
    a = account()
    with pytest.raises(CurrencyMismatchError):
        required_monthly_revenue(
            Accounts([a]), Transactions([tx(a, 100, currency="USD", metric="self_revenue")]),
            MonthlyTargets([mtarget(1000, NOW-dt.timedelta(days=1), currency="JPY")]),
            metric_key="self_revenue", evaluation_time=NOW, business_timezone=ZoneInfo("UTC"))


def test_monthly_target_historical_evaluation_selects_past_version():
    evaluation = dt.datetime(2026, 9, 10, tzinfo=UTC)
    a = account()
    targets = MonthlyTargets([
        mtarget(1000, dt.datetime(2026, 9, 1, tzinfo=UTC)),
        mtarget(2000, dt.datetime(2026, 9, 20, tzinfo=UTC)),
    ])
    result = required_monthly_revenue(Accounts([a]), Transactions([]), targets,
                                      metric_key="self_revenue", evaluation_time=evaluation,
                                      business_timezone=ZoneInfo("UTC"))
    assert result.target == Money(1000, "JPY")


def test_service_package_has_no_persistence_imports():
    root = Path(__file__).parents[2] / "src" / "personal_os" / "services"
    forbidden = ("sqlalchemy", "sqlite3", "personal_os.database")
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not any(name.startswith(forbidden) for name in imports), (path, imports)
