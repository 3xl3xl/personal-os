"""
Step 5 -- Alembic migration lifecycle:

    empty DB
      -> alembic upgrade head
      -> 8 Finance tables + alembic_version
      -> alembic downgrade base
      -> Finance tables removed
      -> alembic upgrade head
      -> schema recreated successfully

No persistent database file survives these tests -- see the autouse
_no_stray_db_files_left_in_repo fixture in conftest.py; every URL used
here points into pytest's own tmp_path.
"""

from __future__ import annotations

from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

EXPECTED_FINANCE_TABLES = {
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


def _table_names(db_url: str) -> set[str]:
    engine = create_engine(db_url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_database_starts_empty(temp_sqlite_url):
    assert _table_names(temp_sqlite_url) == set()


def test_upgrade_head_creates_exactly_the_expected_finance_tables(alembic_config, temp_sqlite_url):
    command.upgrade(alembic_config, "head")

    after = _table_names(temp_sqlite_url)
    assert EXPECTED_FINANCE_TABLES <= after, (
        f"Missing expected table(s): {EXPECTED_FINANCE_TABLES - after}"
    )
    unexpected = after - EXPECTED_FINANCE_TABLES - {"alembic_version"}
    assert not unexpected, (
        f"Unexpected extra table(s) created by migration (e.g. a TaxRule "
        f"table must not appear in Step 5): {unexpected}"
    )


def test_alembic_version_table_records_current_head(alembic_config, temp_sqlite_url):
    command.upgrade(alembic_config, "head")

    engine = create_engine(temp_sqlite_url)
    try:
        with engine.connect() as conn:
            rows = conn.exec_driver_sql("SELECT version_num FROM alembic_version").fetchall()
    finally:
        engine.dispose()

    script_dir = ScriptDirectory.from_config(alembic_config)
    (expected_head,) = script_dir.get_heads()

    assert len(rows) == 1
    assert rows[0][0] == expected_head


def test_downgrade_to_base_removes_all_finance_tables(alembic_config, temp_sqlite_url):
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")

    after = _table_names(temp_sqlite_url)
    surviving = EXPECTED_FINANCE_TABLES & after
    assert not surviving, f"Finance table(s) survived downgrade to base: {surviving}"


def test_re_upgrade_after_downgrade_recreates_full_schema(alembic_config, temp_sqlite_url):
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")

    after = _table_names(temp_sqlite_url)
    assert EXPECTED_FINANCE_TABLES <= after
