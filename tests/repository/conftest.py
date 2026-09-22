"""
Shared fixtures for Step 6 Repository Layer tests.

Per this Step's "Schema creation in tests" requirement, these tests do
NOT use Base.metadata.create_all() as a schema creation mechanism.
Every test goes through the same path production code will use:

    temporary SQLite file (pytest tmp_path)
      -> alembic upgrade head
      -> runtime engine (personal_os.repository.engine.create_sqlite_engine)
      -> Repository / UnitOfWork

This intentionally duplicates the small `make_alembic_config` /
`temp_sqlite_url` helpers already defined in
tests/database/migrations/conftest.py, rather than importing across
test packages or refactoring that Step 5 file -- Step 6 stays fully
additive to previously committed/approved test files.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session, sessionmaker

from personal_os.repository.engine import create_session_factory, create_sqlite_engine

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"
MIGRATIONS_DIR = REPO_ROOT / "src" / "personal_os" / "database" / "migrations"


def make_alembic_config(db_url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture
def temp_sqlite_url(tmp_path) -> str:
    db_path = tmp_path / "personal_os_repository_test.db"
    return f"sqlite:///{db_path}"


@pytest.fixture
def migrated_sqlite_url(temp_sqlite_url: str) -> str:
    """A temp SQLite URL that has already been migrated to head."""
    cfg = make_alembic_config(temp_sqlite_url)
    command.upgrade(cfg, "head")
    return temp_sqlite_url


@pytest.fixture
def engine(migrated_sqlite_url: str):
    eng = create_sqlite_engine(migrated_sqlite_url)
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine) -> sessionmaker[Session]:
    return create_session_factory(engine)
