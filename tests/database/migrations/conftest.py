"""
Shared fixtures for Step 5 Alembic migration tests.

Every test in this package runs Alembic programmatically against a
throwaway, file-based SQLite database created under pytest's own
tmp_path -- never against ~/PersonalOS-data/personal_os.db (which
Step 5 must not create) and never against any database path baked
into alembic.ini or env.py. See ADR-002 and SECURITY.md.

The database URL is injected via the "programmatic Config" path
documented in env.py (Config.set_main_option("sqlalchemy.url", ...)),
not via the PERSONAL_OS_DATABASE_URL environment variable -- these
tests exercise exactly the injection path a future Repository/runtime
layer is expected to use.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"
MIGRATIONS_DIR = REPO_ROOT / "src" / "personal_os" / "database" / "migrations"

_EXCLUDED_DIR_NAMES = {".venv", ".git", "_to_delete", "__pycache__", ".pytest_cache"}
_DB_FILE_SUFFIXES = (".db", ".sqlite", ".sqlite3")


def make_alembic_config(db_url: str) -> Config:
    """Build an Alembic Config pointed at a specific database URL."""
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def alembic_ini_path() -> Path:
    return ALEMBIC_INI


@pytest.fixture
def migrations_dir() -> Path:
    return MIGRATIONS_DIR


@pytest.fixture
def temp_sqlite_url(tmp_path) -> str:
    """A file-based (not in-memory) SQLite URL under pytest's tmp_path.

    File-based so that Alembic's own connection and a test's separate
    verification connection see the same database -- in-memory SQLite
    is per-connection and would not work for multi-connection checks
    such as the FK-enforcement tests.
    """
    db_path = tmp_path / "personal_os_migration_test.db"
    return f"sqlite:///{db_path}"


@pytest.fixture
def alembic_config(temp_sqlite_url: str) -> Config:
    return make_alembic_config(temp_sqlite_url)


def _repo_db_files() -> set[str]:
    found: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDED_DIR_NAMES]
        for name in filenames:
            if name.endswith(_DB_FILE_SUFFIXES):
                found.add(str(Path(dirpath) / name))
    return found


@pytest.fixture(autouse=True)
def _no_stray_db_files_left_in_repo():
    """Safety net: fail loudly if a test leaves a DB file inside the repo.

    All test databases live under pytest's tmp_path (outside the repo,
    cleaned up by pytest itself); this fixture only guards against a
    test accidentally writing one inside the Git-tracked tree.
    """
    before = _repo_db_files()
    yield
    after = _repo_db_files()
    new_files = after - before
    assert not new_files, (
        "Migration test left persistent database file(s) inside the "
        f"repository tree: {sorted(new_files)}"
    )
