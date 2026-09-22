"""Explicit local-private runtime composition for Personal OS.

This is the one production/local runtime composition root. Importing this module
has no filesystem side effects. The runtime database is created/migrated only by
an explicit initialize_runtime() call.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from personal_os.repository.engine import create_session_factory, create_sqlite_engine

DEFAULT_DATA_DIR = Path.home() / "PersonalOS-data"
DEFAULT_DATABASE_PATH = DEFAULT_DATA_DIR / "personal_os.db"


@dataclass(frozen=True, slots=True)
class Runtime:
    database_path: Path
    engine: Engine
    session_factory: sessionmaker[Session]


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{Path(path).expanduser().resolve()}"


def initialize_runtime(database_path: Path = DEFAULT_DATABASE_PATH) -> Runtime:
    """Create parent directory, migrate to head, and return runtime dependencies."""
    path=Path(database_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    url=sqlite_url(path)
    config=Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")

    engine=create_sqlite_engine(url)
    return Runtime(path, engine, create_session_factory(engine))
