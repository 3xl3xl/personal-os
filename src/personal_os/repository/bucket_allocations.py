"""
BucketAllocation repository -- Repository Layer access to the
`bucket_allocations` table (append-only ledger; Finance v0.1 Schema
Design Sec.5.4).

No update/delete method: this table is append-only by design (Step 4
docstring). No get-by-id method either -- nothing in Step 6's scope
needs single-row lookup by allocation id; list_by_bucket() is what a
future bucket-balance derivation actually needs.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from personal_os.database.schema import BucketAllocation
from personal_os.domain.money import Money
from personal_os.domain.records import BucketAllocationRecord
from personal_os.repository._datetime_adapter import from_storage, to_storage


class BucketAllocationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: BucketAllocationRecord) -> None:
        row = BucketAllocation(
            id=record.id,
            bucket_id=record.bucket_id,
            account_id=record.account_id,
            amount_minor=record.amount.amount_minor,
            currency_code=record.amount.currency_code,
            entry_type=record.entry_type,
            originating_transaction_id=record.originating_transaction_id,
            reallocation_group_id=record.reallocation_group_id,
            created_at=to_storage(record.created_at),
        )
        self._session.add(row)
        self._session.flush()

    def list_by_bucket(self, bucket_id: uuid.UUID) -> list[BucketAllocationRecord]:
        stmt = (
            select(BucketAllocation)
            .where(BucketAllocation.bucket_id == bucket_id)
            .order_by(BucketAllocation.created_at)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [_to_record(row) for row in rows]


def _to_record(row: BucketAllocation) -> BucketAllocationRecord:
    return BucketAllocationRecord(
        id=row.id,
        bucket_id=row.bucket_id,
        account_id=row.account_id,
        amount=Money(row.amount_minor, row.currency_code),
        entry_type=row.entry_type,
        created_at=from_storage(row.created_at),
        originating_transaction_id=row.originating_transaction_id,
        reallocation_group_id=row.reallocation_group_id,
    )
