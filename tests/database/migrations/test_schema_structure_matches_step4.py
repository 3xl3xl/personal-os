"""
Step 5 -- Verify the migrated schema's structure (PK / FK / UNIQUE /
CHECK / indexes / nullable semantics) matches Step 4's SQLAlchemy
metadata, using the migration's own output rather than
Base.metadata.create_all(). Complements test_schema_drift.py, which
covers what Alembic's compare_metadata checks; this module covers
CHECK constraints and a few Step-4-specific semantic points that
compare_metadata does not check (see that module's docstring).
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect

ALL_TABLES = (
    "accounts",
    "transactions",
    "capital_buckets",
    "bucket_allocations",
    "financial_metrics",
    "financial_targets",
    "monthly_targets",
    "audit_logs",
)


def _inspector(db_url):
    engine = create_engine(db_url)
    return engine, inspect(engine)


def test_every_table_has_a_primary_key_column_named_id(alembic_config, temp_sqlite_url):
    command.upgrade(alembic_config, "head")
    engine, inspector = _inspector(temp_sqlite_url)
    try:
        for table in ALL_TABLES:
            pk = inspector.get_pk_constraint(table)
            assert pk["constrained_columns"] == ["id"], f"{table}: {pk}"
    finally:
        engine.dispose()


def test_foreign_keys_match_step4_metadata(alembic_config, temp_sqlite_url):
    command.upgrade(alembic_config, "head")
    engine, inspector = _inspector(temp_sqlite_url)
    try:

        def fk_targets(table):
            return {
                (
                    tuple(fk["constrained_columns"]),
                    fk["referred_table"],
                    tuple(fk["referred_columns"]),
                )
                for fk in inspector.get_foreign_keys(table)
            }

        assert fk_targets("transactions") == {
            (("account_id",), "accounts", ("id",)),
            (("correction_of",), "transactions", ("id",)),
            (("metric_key",), "financial_metrics", ("key",)),
        }
        assert fk_targets("capital_buckets") == {
            (("account_id",), "accounts", ("id",)),
        }
        assert fk_targets("bucket_allocations") == {
            (("bucket_id",), "capital_buckets", ("id",)),
            (("account_id",), "accounts", ("id",)),
            (("originating_transaction_id",), "transactions", ("id",)),
        }
        assert fk_targets("financial_targets") == {
            (("metric_key",), "financial_metrics", ("key",)),
        }
        assert fk_targets("monthly_targets") == {
            (("metric_key",), "financial_metrics", ("key",)),
        }
        assert fk_targets("accounts") == set()
        assert fk_targets("financial_metrics") == set()
        assert fk_targets("audit_logs") == set()
    finally:
        engine.dispose()


def test_unique_constraints_match_step4_metadata(alembic_config, temp_sqlite_url):
    command.upgrade(alembic_config, "head")
    engine, inspector = _inspector(temp_sqlite_url)
    try:
        fm_unique_columns = {
            tuple(uc["column_names"]) for uc in inspector.get_unique_constraints("financial_metrics")
        }
        fm_unique_indexes = {
            tuple(ix["column_names"])
            for ix in inspector.get_indexes("financial_metrics")
            if ix["unique"]
        }
        assert ("key",) in fm_unique_columns or ("key",) in fm_unique_indexes, (
            "financial_metrics.key must be unique (table-level UNIQUE or "
            "unique index -- SQLite may reflect either)"
        )

        ft_unique = {
            tuple(uc["column_names"]) for uc in inspector.get_unique_constraints("financial_targets")
        }
        assert ("metric_key", "effective_from") in ft_unique

        mt_unique = {
            tuple(uc["column_names"]) for uc in inspector.get_unique_constraints("monthly_targets")
        }
        assert ("metric_key", "year", "month", "effective_from") in mt_unique

        for table in ("capital_buckets",):
            uniques = inspector.get_unique_constraints(table)
            assert not any("bucket_role" in uc["column_names"] for uc in uniques), (
                "bucket_role must not be uniquely constrained -- multiple "
                "TAX_RESERVE buckets are permitted (Schema Design v0.3)"
            )
            assert not any(uc["column_names"] == ["name"] for uc in uniques), (
                "capital_buckets.name must not be uniquely constrained"
            )
    finally:
        engine.dispose()


def test_check_constraints_present_for_currency_code(alembic_config, temp_sqlite_url):
    command.upgrade(alembic_config, "head")
    engine, inspector = _inspector(temp_sqlite_url)
    try:
        for table in (
            "accounts",
            "transactions",
            "bucket_allocations",
            "financial_targets",
            "monthly_targets",
        ):
            checks = inspector.get_check_constraints(table)
            combined_text = " ".join(c["sqltext"] for c in checks).lower()
            assert "currency_code" in combined_text, (
                f"{table}: expected a currency_code CHECK constraint, found {checks}"
            )
    finally:
        engine.dispose()


def test_month_range_check_present_and_no_arbitrary_year_range_check(alembic_config, temp_sqlite_url):
    command.upgrade(alembic_config, "head")
    engine, inspector = _inspector(temp_sqlite_url)
    try:
        checks = inspector.get_check_constraints("monthly_targets")
        texts = [c["sqltext"].lower() for c in checks]
        assert any("month" in t for t in texts), "monthly_targets must keep its month 1-12 CHECK"
        assert not any("year" in t and ("2000" in t or "2100" in t) for t in texts), (
            "monthly_targets must not have an arbitrary year-range CHECK "
            "(Step 4 Decision 4)"
        )
    finally:
        engine.dispose()


def test_bucket_allocations_entry_type_linkage_check_present(alembic_config, temp_sqlite_url):
    command.upgrade(alembic_config, "head")
    engine, inspector = _inspector(temp_sqlite_url)
    try:
        checks = inspector.get_check_constraints("bucket_allocations")
        combined_text = " ".join(c["sqltext"] for c in checks).upper()
        assert "CASH_LINKED" in combined_text
        assert "REALLOCATION" in combined_text
    finally:
        engine.dispose()


def test_bucket_role_and_is_protected_are_not_null_with_no_server_default(alembic_config, temp_sqlite_url):
    command.upgrade(alembic_config, "head")
    engine, inspector = _inspector(temp_sqlite_url)
    try:
        columns = {c["name"]: c for c in inspector.get_columns("capital_buckets")}
        assert columns["bucket_role"]["nullable"] is False
        assert not columns["bucket_role"].get("default")
        assert columns["is_protected"]["nullable"] is False
        assert not columns["is_protected"].get("default")
    finally:
        engine.dispose()


def test_no_effective_to_column_on_target_tables(alembic_config, temp_sqlite_url):
    command.upgrade(alembic_config, "head")
    engine, inspector = _inspector(temp_sqlite_url)
    try:
        for table in ("financial_targets", "monthly_targets"):
            column_names = {c["name"] for c in inspector.get_columns(table)}
            assert "effective_to" not in column_names
    finally:
        engine.dispose()


def test_money_columns_are_integer_never_float(alembic_config, temp_sqlite_url):
    command.upgrade(alembic_config, "head")
    engine, inspector = _inspector(temp_sqlite_url)
    try:
        money_columns = {
            "transactions": "amount_minor",
            "bucket_allocations": "amount_minor",
            "financial_targets": "target_amount_minor",
            "monthly_targets": "target_amount_minor",
        }
        for table, column_name in money_columns.items():
            columns = {c["name"]: c for c in inspector.get_columns(table)}
            type_name = str(columns[column_name]["type"]).upper()
            assert "FLOAT" not in type_name and "REAL" not in type_name and "NUMERIC" not in type_name, (
                f"{table}.{column_name} must be an integer type, found {type_name}"
            )
    finally:
        engine.dispose()
