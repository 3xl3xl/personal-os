"""
Tests for the Step 4 review decisions (Decisions 1-5): AccountStatus /
CapitalBucketStatus as domain enums, FinancialMetric / FinancialTarget
/ MonthlyTarget columns as confirmed, no arbitrary year range CHECK,
no effective_to column, and no TaxRule table in Finance v0.1.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint

from personal_os.database.schema import Account, Base, CapitalBucket
from personal_os.domain.enums import AccountStatus, CapitalBucketStatus


def test_account_status_uses_domain_enum() -> None:
    col = Base.metadata.tables["accounts"].columns["status"]
    assert set(col.type.enums) == {member.value for member in AccountStatus}


def test_capital_bucket_status_uses_domain_enum() -> None:
    col = Base.metadata.tables["capital_buckets"].columns["status"]
    assert set(col.type.enums) == {member.value for member in CapitalBucketStatus}


def test_account_and_capital_bucket_status_columns_still_have_check_constraints() -> None:
    # Enum(..., create_constraint=True) generates the CHECK now, replacing
    # the hand-written "status IN (...)" constraints from the first Step 4
    # implementation.
    for table_name in ("accounts", "capital_buckets"):
        table = Base.metadata.tables[table_name]
        check_constraints = [c for c in table.constraints if isinstance(c, CheckConstraint)]
        assert any("status" in str(c.sqltext) for c in check_constraints), table_name


def test_monthly_targets_has_no_arbitrary_year_range_check() -> None:
    table = Base.metadata.tables["monthly_targets"]
    check_texts = [
        str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)
    ]
    assert not any("year" in text for text in check_texts), check_texts


def test_monthly_targets_still_has_month_range_check() -> None:
    table = Base.metadata.tables["monthly_targets"]
    check_texts = [
        str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)
    ]
    assert any("month" in text for text in check_texts), check_texts


def test_no_effective_to_column_on_financial_targets() -> None:
    table = Base.metadata.tables["financial_targets"]
    assert "effective_to" not in table.columns


def test_no_effective_to_column_on_monthly_targets() -> None:
    table = Base.metadata.tables["monthly_targets"]
    assert "effective_to" not in table.columns


def test_no_tax_rule_table_exists() -> None:
    assert "tax_rules" not in Base.metadata.tables
    assert not any("tax_rule" in name.lower() for name in Base.metadata.tables.keys())
