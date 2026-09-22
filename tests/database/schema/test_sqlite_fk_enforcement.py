"""
Distinguishes "FK definition exists in the schema" from "SQLite
enforces that FK at runtime" -- these are NOT the same thing.

SQLite requires `PRAGMA foreign_keys = ON` to be issued on every
connection for declared FOREIGN KEY constraints to actually be
enforced; without it, SQLite silently accepts rows that reference a
nonexistent parent row, even though the FK is present in the schema's
DDL. Step 4 only defines the schema (personal_os.database.schema); it
does not configure engine/connection behavior -- that is a Repository
Layer concern (Step 6, Repository interfaces/implementations), which
is where a SQLAlchemy `connect` event listener issuing
`PRAGMA foreign_keys = ON` belongs, together with a corresponding
enforcement test (attempting an insert with a dangling FK reference
and expecting IntegrityError) using that configured engine.

This test documents the CURRENT (Step 4) state: FK enforcement is NOT
active, because no engine-level configuration exists yet.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from personal_os.database.schema import Base, Transaction
from personal_os.domain.enums import TransactionKind


def test_sqlite_does_not_enforce_declared_foreign_keys_without_pragma() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        orphan_transaction = Transaction(
            account_id=uuid.uuid4(),  # references an account that does not exist
            transaction_type=TransactionKind.NORMAL,
            amount_minor=100,
            currency_code="USD",
            occurred_at=dt.datetime.now(dt.timezone.utc),
        )
        session.add(orphan_transaction)
        # This commit does NOT raise, even though transactions.account_id
        # has a declared FK to accounts.id. If this assertion ever starts
        # failing (i.e. an IntegrityError is raised here), it means some
        # engine-level configuration (e.g. PRAGMA foreign_keys=ON on
        # connect) has been introduced -- update this test's expectation
        # and its docstring accordingly at that point, rather than
        # deleting it, since it exists specifically to catch that change.
        session.commit()

        fetched = session.get(Transaction, orphan_transaction.id)
        assert fetched is not None, (
            "expected the orphan row to persist -- FK is declared but not "
            "runtime-enforced without PRAGMA foreign_keys=ON"
        )
    engine.dispose()
