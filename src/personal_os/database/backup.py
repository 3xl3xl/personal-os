"""Consistent SQLite backup and restore primitives.

Explicit paths only: there is no fallback to the private runtime database.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
import uuid
from pathlib import Path

UTC = dt.timezone.utc


class BackupError(RuntimeError):
    """Raised when backup or restore validation fails."""


def _existing_file(path: Path, *, label: str) -> Path:
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise BackupError(f"{label} does not exist or is not a file: {path}")
    return path


def _integrity_check(path: Path) -> None:
    try:
        with sqlite3.connect(path) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.DatabaseError as exc:
        raise BackupError(f"SQLite integrity check failed for {path}") from exc
    if result != ("ok",):
        raise BackupError(f"SQLite integrity check did not return ok for {path}: {result!r}")


def _version_name(now: dt.datetime | None = None) -> str:
    instant = now or dt.datetime.now(UTC)
    if instant.tzinfo is None:
        raise BackupError("backup timestamp must be timezone-aware")
    instant = instant.astimezone(UTC)
    return f"personal_os_{instant:%Y%m%dT%H%M%S%fZ}_{uuid.uuid4().hex[:8]}.db"


def create_backup(source_db: Path, backup_directory: Path, *, now: dt.datetime | None = None) -> Path:
    """Create and verify one versioned, consistent SQLite snapshot."""
    source = _existing_file(source_db, label="source database")
    destination_dir = Path(backup_directory).expanduser().resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / _version_name(now)
    try:
        with sqlite3.connect(source) as source_connection:
            with sqlite3.connect(destination) as destination_connection:
                source_connection.backup(destination_connection)
        _integrity_check(destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


def restore_backup(backup_db: Path, destination_db: Path) -> Path:
    """Restore a verified snapshot to an explicit destination path."""
    backup = _existing_file(backup_db, label="backup database")
    _integrity_check(backup)
    destination = Path(destination_db).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(backup) as source_connection:
            with sqlite3.connect(destination) as destination_connection:
                source_connection.backup(destination_connection)
        _integrity_check(destination)
    except sqlite3.DatabaseError as exc:
        raise BackupError("SQLite restore failed") from exc
    return destination
