"""Explicit local-private runtime composition for Personal OS.

Importing this module has no filesystem side effects. The runtime database is
created/migrated only by an explicit initialize_runtime() call.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from personal_os.repository.engine import create_session_factory, create_sqlite_engine

DEFAULT_DATA_DIR = Path.home() / "PersonalOS-data"
DEFAULT_DATABASE_PATH = DEFAULT_DATA_DIR / "personal_os.db"
_PRIVATE_DIR_MODE = 0o700
_PRIVATE_FILE_MODE = 0o600


@dataclass(frozen=True, slots=True)
class Runtime:
    database_path: Path
    engine: Engine
    session_factory: sessionmaker[Session]


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{Path(path).expanduser().resolve()}"


def initialize_runtime(database_path: Path = DEFAULT_DATABASE_PATH) -> Runtime:
    """Create a private runtime DB, migrate it to head, and return dependencies."""
    path = Path(database_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, _PRIVATE_DIR_MODE)

    url = sqlite_url(path)
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")

    # SQLite creates files according to the process umask; enforce the runtime
    # privacy contract explicitly for both newly-created and existing DB files.
    os.chmod(path, _PRIVATE_FILE_MODE)

    engine = create_sqlite_engine(url)
    return Runtime(path, engine, create_session_factory(engine))
