"""
Step 5 -- Stage B of the 3-stage SQLite foreign-key verification
policy adopted at the end of Step 4:

    A. FK declaration        -> verified in Step 4 (schema metadata;
                                 see tests/database/schema/
                                 test_sqlite_fk_enforcement.py)
    B. migration-result FK   -> verified here
    C. runtime Repository FK -> to be verified in Step 6

SQLite never enforces declared foreign keys by default -- Step 4
proved this empirically for Base.metadata.create_all(). This module
proves the same is true (and separately, fixable per-connection) for
a database built via the Alembic migration instead: an INSERT
referencing a nonexistent parent ID is rejected only once
PRAGMA foreign_keys=ON is explicitly enabled on the verification
connection. Both states are asserted, not just the "rejected" one, so
this test cannot silently pass for the wrong reason (e.g. a typo that
makes the FK-off case also fail).
"""

from __future__ import annotations

import uuid

import pytest
from alembic import command
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError


def _engine_with_fk_pragma(db_url: str, *, enabled: bool):
    engine = create_engine(db_url)

    if enabled:

        @event.listens_for(engine, "connect")
        def _set_sqlite_fk_pragma(dbapi_connection, connection_record):  # noqa: ANN001, ARG001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def _insert_transaction_with_nonexistent_account(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO transactions "
                "(id, account_id, transaction_type, amount_minor, "
                " currency_code, occurred_at, status) "
                "VALUES (:id, :account_id, 'NORMAL', 1000, 'JPY', "
                " '2026-01-01T00:00:00+00:00', 'ACTIVE')"
            ),
            {"id": str(uuid.uuid4()), "account_id": str(uuid.uuid4())},
        )


def test_invalid_fk_insert_is_rejected_when_pragma_is_on(alembic_config, temp_sqlite_url):
    command.upgrade(alembic_config, "head")

    engine = _engine_with_fk_pragma(temp_sqlite_url, enabled=True)
    try:
        with pytest.raises(IntegrityError):
            _insert_transaction_with_nonexistent_account(engine)
    finally:
        engine.dispose()


def test_invalid_fk_insert_is_not_rejected_when_pragma_is_off(alembic_config, temp_sqlite_url):
    """Documents today's SQLite default -- not a desired end state.

    A future Step 6 fix (always-on PRAGMA foreign_keys=ON in the
    Repository Layer's connection setup) must change this test
    deliberately, not leave it silently passing for a stale reason.
    """
    command.upgrade(alembic_config, "head")

    engine = _engine_with_fk_pragma(temp_sqlite_url, enabled=False)
    try:
        _insert_transaction_with_nonexistent_account(engine)  # must NOT raise
    finally:
        engine.dispose()
