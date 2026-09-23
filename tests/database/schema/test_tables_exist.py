"""Schema-level tests: verifies all Finance v0.1 tables are registered."""

from __future__ import annotations

from personal_os.database.schema import Base

EXPECTED_TABLES = {
    "accounts",
    "transactions",
    "capital_buckets",
    "bucket_allocations",
    "financial_metrics",
    "financial_targets",
    "monthly_targets",
    "audit_logs",
    "external_transaction_links",
}


def test_all_expected_tables_exist_in_metadata() -> None:
    assert set(Base.metadata.tables.keys()) == EXPECTED_TABLES
