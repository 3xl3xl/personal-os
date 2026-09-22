"""
Transaction repository -- Repository Layer access to the `transactions`
table (the append-only ledger; Finance v0.1 Schema Design Sec.5.2).

No update/delete method: corrections are new rows referencing
`correction_of`, and voiding is a status flip written as a new
Service-Layer-owned append -- Step 6 implements only the plain
read/write path an append-only ledger needs, not that business rule.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from personal_os.database.schema import Transaction
from personal_os.domain.money import Money
from personal_os.domain.records import TransactionRecord
from personal_os.repository._datetime_adapter import from_storage, to_storage


class TransactionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: TransactionRecord) -> None:
        row = Transaction(
            id=record.id,
            account_id=record.account_id,
            transaction_type=record.transaction_type,
            amount_minor=record.amount.amount_minor,
            currency_code=record.amount.currency_code,
            occurred_at=to_storage(record.occurred_at),
            status=record.status,
            correction_of=record.correction_of,
            metric_key=record.metric_key,
            transfer_group_id=record.transfer_group_id,
            memo=record.memo,
        )
        self._session.add(row)
        self._session.flush()

    def get(self, transaction_id: uuid.UUID) -> TransactionRecord | None:
        row = self._session.get(Transaction, transaction_id)
        return None if row is None else _to_record(row)

    def list_by_account(self, account_id: uuid.UUID) -> list[TransactionRecord]:
        stmt = (
            select(Transaction)
            .where(Transaction.account_id == account_id)
            .order_by(Transaction.occurred_at)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [_to_record(row) for row in rows]


def _to_record(row: Transaction) -> TransactionRecord:
    return TransactionRecord(
        id=row.id,
        account_id=row.account_id,
        transaction_type=row.transaction_type,
        amount=Money(row.amount_minor, row.currency_code),
        occurred_at=from_storage(row.occurred_at),
        status=row.status,
        correction_of=row.correction_of,
        metric_key=row.metric_key,
        transfer_group_id=row.transfer_group_id,
        memo=row.memo,
    )
