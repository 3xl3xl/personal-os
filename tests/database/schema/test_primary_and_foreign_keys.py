"""Verifies primary keys and required foreign keys per Finance v0.1 Schema Design."""

from __future__ import annotations

from personal_os.database.schema import Base


def _table(name: str):
    return Base.metadata.tables[name]


def test_every_table_has_a_single_uuid_primary_key() -> None:
    # ADR-007: every table uses a UUID primary key column.
    for table_name, table in Base.metadata.tables.items():
        pk_columns = list(table.primary_key.columns)
        assert len(pk_columns) == 1, f"{table_name} should have exactly one PK column"
        assert pk_columns[0].name == "id", f"{table_name}'s PK column should be named 'id'"


def test_transactions_account_id_is_required_foreign_key() -> None:
    col = _table("transactions").columns["account_id"]
    assert col.nullable is False
    assert any(fk.column.table.name == "accounts" for fk in col.foreign_keys)


def test_transactions_correction_of_is_nullable_self_referential_fk() -> None:
    col = _table("transactions").columns["correction_of"]
    assert col.nullable is True
    assert any(fk.column.table.name == "transactions" for fk in col.foreign_keys)


def test_transactions_metric_key_is_nullable_fk_to_financial_metrics() -> None:
    col = _table("transactions").columns["metric_key"]
    assert col.nullable is True
    assert any(
        fk.column.table.name == "financial_metrics" and fk.column.name == "key"
        for fk in col.foreign_keys
    )


def test_capital_buckets_account_id_is_required_foreign_key() -> None:
    col = _table("capital_buckets").columns["account_id"]
    assert col.nullable is False
    assert any(fk.column.table.name == "accounts" for fk in col.foreign_keys)


def test_bucket_allocations_required_foreign_keys() -> None:
    table = _table("bucket_allocations")
    bucket_id = table.columns["bucket_id"]
    account_id = table.columns["account_id"]
    assert bucket_id.nullable is False
    assert account_id.nullable is False
    assert any(fk.column.table.name == "capital_buckets" for fk in bucket_id.foreign_keys)
    assert any(fk.column.table.name == "accounts" for fk in account_id.foreign_keys)


def test_bucket_allocations_originating_transaction_id_is_nullable_fk() -> None:
    col = _table("bucket_allocations").columns["originating_transaction_id"]
    assert col.nullable is True
    assert any(fk.column.table.name == "transactions" for fk in col.foreign_keys)


def test_financial_targets_and_monthly_targets_reference_financial_metrics_key() -> None:
    for table_name in ("financial_targets", "monthly_targets"):
        col = _table(table_name).columns["metric_key"]
        assert col.nullable is False
        assert any(
            fk.column.table.name == "financial_metrics" and fk.column.name == "key"
            for fk in col.foreign_keys
        )
