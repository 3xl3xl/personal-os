"""Verifies required unique constraints, and absence of unwanted ones."""

from __future__ import annotations

from sqlalchemy import UniqueConstraint

from personal_os.database.schema import Base


def test_financial_metrics_key_is_unique() -> None:
    table = Base.metadata.tables["financial_metrics"]
    assert table.columns["key"].unique is True


def test_financial_targets_metric_and_effective_from_is_unique() -> None:
    table = Base.metadata.tables["financial_targets"]
    unique_constraints = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    column_sets = [{col.name for col in uc.columns} for uc in unique_constraints]
    assert {"metric_key", "effective_from"} in column_sets


def test_monthly_targets_metric_year_month_effective_from_is_unique() -> None:
    table = Base.metadata.tables["monthly_targets"]
    unique_constraints = [c for c in table.constraints if isinstance(c, UniqueConstraint)]
    column_sets = [{col.name for col in uc.columns} for uc in unique_constraints]
    assert {"metric_key", "year", "month", "effective_from"} in column_sets


def test_capital_buckets_name_is_not_unique() -> None:
    # Buckets must be freely creatable/renameable; no forced uniqueness on name.
    table = Base.metadata.tables["capital_buckets"]
    assert table.columns["name"].unique is not True


def test_capital_buckets_bucket_role_is_not_unique() -> None:
    # Multiple TAX_RESERVE (or GENERAL) buckets must be allowed.
    table = Base.metadata.tables["capital_buckets"]
    assert table.columns["bucket_role"].unique is not True
