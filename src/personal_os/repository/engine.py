"""
SQLAlchemy Engine / Session factory for Personal OS's Repository Layer.

Source of truth: ADR-002 (Persistence & ORM Strategy) and this Step's
"Runtime Engine / Session Infrastructure" requirement. This module is
Repository Layer runtime configuration -- it never hardcodes a real
database path (the URL is always supplied by the caller) and never
references ~/PersonalOS-data/personal_os.db.

## SQLite Foreign Key enforcement -- Stage C

Step 4 proved FK *declaration* exists in the schema metadata. Step 5
proved a freshly migrated database enforces FKs once
PRAGMA foreign_keys=ON is explicitly set on a connection. Neither
stage makes enforcement happen automatically for ordinary application
traffic: SQLite defaults every new connection to
foreign_keys=OFF, regardless of what a migration or the schema
declares.

This module is Stage C: every connection opened through an engine
created by create_sqlite_engine() has PRAGMA foreign_keys=ON applied
automatically via a SQLAlchemy "connect" event listener, so no
individual call site has to remember to do it.
"""

from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def create_sqlite_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy Engine with SQLite FK enforcement always on.

    `database_url` is supplied entirely by the caller (a future
    startup/runtime configuration layer, or a test) -- this function
    never hardcodes or defaults to a real database path. The
    PRAGMA foreign_keys=ON listener is only attached when the engine's
    dialect is actually sqlite, so this function stays safe to call
    against a future PostgreSQL URL without erroring on an
    unsupported pragma.
    """
    engine = create_engine(database_url)

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):  # noqa: ANN001, ARG001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build a sessionmaker bound to `engine`.

    expire_on_commit=False: the Repository Layer always converts an
    ORM row to a domain record (see personal_os.domain.records) before
    returning control to its caller, so nothing above this layer ever
    touches an ORM instance after commit -- this setting simply avoids
    a surprising extra SELECT being issued while a repository method
    is still building that record from a row it just wrote.
    """
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
