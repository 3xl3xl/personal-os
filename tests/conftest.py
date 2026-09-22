"""Canonical temporary SQLite fixture for Personal OS tests.

Step 10 centralizes the integration-test database lifecycle:

    pytest tmp_path
      -> file-based SQLite database outside the repository
      -> Alembic upgrade head
      -> runtime engine with SQLite FK enforcement
      -> test
      -> engine dispose
      -> explicit database-file removal

No fixture in this module has a fallback to the private runtime database.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from personal_os.repository.engine import create_session_factory, create_sqlite_engine

REPO_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"
MIGRATIONS_DIR = REPO_ROOT / "src" / "personal_os" / "database" / "migrations"


def make_alembic_config(database_url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "personal_os_test.db"


@pytest.fixture
def temp_sqlite_url(temp_db_path: Path) -> str:
    return f"sqlite:///{temp_db_path}"


@pytest.fixture
def migrated_sqlite_url(temp_sqlite_url: str) -> str:
    command.upgrade(make_alembic_config(temp_sqlite_url), "head")
    return temp_sqlite_url


@pytest.fixture
def engine(migrated_sqlite_url: str, temp_db_path: Path):
    engine = create_sqlite_engine(migrated_sqlite_url)
    try:
        yield engine
    finally:
        engine.dispose()
        # Explicit cleanup is part of the fixture contract rather than relying
        # only on pytest's eventual tmp_path cleanup.
        for path in (
            temp_db_path,
            Path(str(temp_db_path) + "-wal"),
            Path(str(temp_db_path) + "-shm"),
            Path(str(temp_db_path) + "-journal"),
        ):
            path.unlink(missing_ok=True)


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return create_session_factory(engine)
