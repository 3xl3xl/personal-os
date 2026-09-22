"""
Account repository -- Repository Layer access to the `accounts` table.

Public methods accept/return only personal_os.domain.records.AccountRecord
-- never the SQLAlchemy Account ORM model (Step 6, item 6) -- so nothing
above the Repository Layer ever holds a Session-bound object.

No update/delete method exists here for Step 6: Finance v0.1's Schema
Design derives an account's balance from its transactions (never a
stored column), and this Step's test list does not call for an account
status transition (e.g. closing an account). Unlike a meaningless
update on an append-only entity, a status transition would be a real,
meaningful future write -- deferred to whichever future Step first
needs it rather than speculatively added now.

add() calls session.flush() (not commit()) so that a constraint
violation (e.g. a future FK from another table onto accounts.id)
surfaces at the point of the write itself; the surrounding transaction
boundary (commit/rollback) belongs entirely to UnitOfWork, never to
this repository (Step 6, item 7).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from personal_os.database.schema import Account
from personal_os.domain.records import AccountRecord
from personal_os.repository._datetime_adapter import from_storage, to_storage


class AccountRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: AccountRecord) -> None:
        row = Account(
            id=record.id,
            name=record.name,
            account_type=record.account_type,
            currency_code=record.currency_code,
            opened_at=to_storage(record.opened_at),
            status=record.status,
        )
        self._session.add(row)
        self._session.flush()

    def get(self, account_id: uuid.UUID) -> AccountRecord | None:
        row = self._session.get(Account, account_id)
        return None if row is None else _to_record(row)

    def list_all(self) -> list[AccountRecord]:
        stmt = select(Account).order_by(Account.opened_at)
        rows = self._session.execute(stmt).scalars().all()
        return [_to_record(row) for row in rows]


def _to_record(row: Account) -> AccountRecord:
    return AccountRecord(
        id=row.id,
        name=row.name,
        account_type=row.account_type,
        currency_code=row.currency_code,
        opened_at=from_storage(row.opened_at),
        status=row.status,
    )
