from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import text

from personal_os.database.backup import BackupError, create_backup, restore_backup
from personal_os.repository.engine import create_sqlite_engine
from tests.conftest import make_alembic_config

UTC = dt.timezone.utc


def _row_count(path: Path, table: str) -> int:
    with sqlite3.connect(path) as connection:
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_backup_uses_versioned_unique_files(tmp_path):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO sample VALUES (1)")
    backup_dir = tmp_path / "backups"
    now = dt.datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    first = create_backup(source, backup_dir, now=now)
    second = create_backup(source, backup_dir, now=now)
    assert first != second
    assert first.exists() and second.exists()
    assert first.parent == backup_dir.resolve()


def test_backup_is_consistent_readable_snapshot_of_migrated_database(tmp_path):
    source = tmp_path / "source.db"
    url = f"sqlite:///{source}"
    command.upgrade(make_alembic_config(url), "head")
    engine = create_sqlite_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO financial_metrics (id, key, display_name, created_at) VALUES (:id, :key, :name, :created_at)"),
                {"id": "00000000000040008000000000000001", "key": "synthetic_metric", "name": "Synthetic", "created_at": "2026-09-22 12:00:00"},
            )
    finally:
        engine.dispose()
    backup = create_backup(source, tmp_path / "backups")
    assert _row_count(backup, "financial_metrics") == 1
    with sqlite3.connect(backup) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_snapshot_does_not_change_after_source_changes(tmp_path):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE sample (value INTEGER)")
        connection.execute("INSERT INTO sample VALUES (1)")
    backup = create_backup(source, tmp_path / "backups")
    with sqlite3.connect(source) as connection:
        connection.execute("INSERT INTO sample VALUES (2)")
    assert _row_count(source, "sample") == 2
    assert _row_count(backup, "sample") == 1


def test_restore_recreates_schema_and_data(tmp_path):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE sample (value TEXT)")
        connection.execute("INSERT INTO sample VALUES ('synthetic')")
    backup = create_backup(source, tmp_path / "backups")
    restored = restore_backup(backup, tmp_path / "restored.db")
    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT value FROM sample").fetchall() == [("synthetic",)]
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_restore_replaces_existing_destination_contents(tmp_path):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE wanted (value INTEGER)")
        connection.execute("INSERT INTO wanted VALUES (7)")
    backup = create_backup(source, tmp_path / "backups")
    destination = tmp_path / "destination.db"
    with sqlite3.connect(destination) as connection:
        connection.execute("CREATE TABLE obsolete (value INTEGER)")
    restore_backup(backup, destination)
    with sqlite3.connect(destination) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "wanted" in tables
        assert "obsolete" not in tables
        assert connection.execute("SELECT value FROM wanted").fetchone() == (7,)


def test_missing_source_and_backup_fail_closed(tmp_path):
    with pytest.raises(BackupError):
        create_backup(tmp_path / "missing.db", tmp_path / "backups")
    with pytest.raises(BackupError):
        restore_backup(tmp_path / "missing-backup.db", tmp_path / "restored.db")


def test_corrupt_backup_is_rejected_before_restore(tmp_path):
    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"not a sqlite database")
    destination = tmp_path / "destination.db"
    with pytest.raises(BackupError):
        restore_backup(corrupt, destination)
    assert not destination.exists()


def test_no_private_runtime_path_or_git_fallback_is_encoded():
    import inspect
    import personal_os.database.backup as module
    source = inspect.getsource(module)
    assert "PersonalOS-data" not in source
    assert "~/PersonalOS" not in source
    assert ".git" not in source
