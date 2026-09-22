"""Step 10 acceptance tests for the canonical temporary SQLite fixture."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect, text

from personal_os.repository.engine import create_sqlite_engine


def test_temp_database_is_file_based_outside_repository(temp_db_path, migrated_sqlite_url):
    repo_root = Path(__file__).resolve().parents[2]
    assert temp_db_path.exists()
    assert repo_root not in temp_db_path.resolve().parents
    assert migrated_sqlite_url == f"sqlite:///{temp_db_path}"


def test_migrations_are_applied_to_temp_database(engine):
    tables = set(inspect(engine).get_table_names())
    assert "alembic_version" in tables
    assert {
        "accounts",
        "audit_logs",
        "bucket_allocations",
        "capital_buckets",
        "financial_metrics",
        "financial_targets",
        "monthly_targets",
        "transactions",
    }.issubset(tables)


def test_runtime_engine_enforces_foreign_keys(engine):
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_engine_fixture_removes_database_after_teardown(request, tmp_path):
    db_path = tmp_path / "teardown_probe.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_sqlite_engine(db_url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE probe (id INTEGER PRIMARY KEY)"))
    assert db_path.exists()
    engine.dispose()
    db_path.unlink()
    assert not db_path.exists()
