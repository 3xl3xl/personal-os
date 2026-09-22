"""
Step 6 -- SQLite Foreign Key Stage C: runtime Repository FK enforcement.

    A. FK declaration        -> Step 4
    B. migration-result FK   -> Step 5
    C. runtime Repository FK -> here

Unlike Step 5's test (which manually flips PRAGMA foreign_keys on a
raw verification connection), this module proves that the *ordinary*
engine every Repository call goes through --
personal_os.repository.engine.create_sqlite_engine() -- enables FK
enforcement automatically, on every connection, with no call site
having to remember to do it.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from personal_os.domain.datetime import utc_now
from personal_os.domain.enums import TransactionKind, TransactionStatus
from personal_os.domain.ids import new_id
from personal_os.domain.money import Money
from personal_os.domain.records import TransactionRecord
from personal_os.repository.transactions import TransactionRepository


def test_pragma_foreign_keys_is_on_for_every_connection_from_the_runtime_engine(engine):
    with engine.connect() as conn:
        value = conn.execute(text("PRAGMA foreign_keys")).scalar_one()
    assert value == 1


def test_invalid_fk_insert_through_the_repository_raises_integrity_error(session_factory):
    session = session_factory()
    try:
        repo = TransactionRepository(session)
        record = TransactionRecord(
            id=new_id(),
            account_id=uuid.uuid4(),  # deliberately nonexistent account
            transaction_type=TransactionKind.NORMAL,
            amount=Money(1000, "JPY"),
            occurred_at=utc_now(),
            status=TransactionStatus.ACTIVE,
        )
        with pytest.raises(IntegrityError):
            repo.add(record)
    finally:
        session.rollback()
        session.close()
