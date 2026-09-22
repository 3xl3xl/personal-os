"""
CapitalBucket repository -- Repository Layer access to the
`capital_buckets` table (Finance v0.1 Schema Design Sec.5.3).

No update/delete method for Step 6: bucket balance is derived from
bucket_allocations, never stored. A future ARCHIVED-status transition
is a real future write (like Account's status), deferred rather than
speculatively added -- Step 6's test list does not call for it.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from personal_os.database.schema import CapitalBucket
from personal_os.domain.records import CapitalBucketRecord
from personal_os.repository._datetime_adapter import from_storage, to_storage


class CapitalBucketRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: CapitalBucketRecord) -> None:
        row = CapitalBucket(
            id=record.id,
            account_id=record.account_id,
            name=record.name,
            bucket_role=record.bucket_role,
            is_protected=record.is_protected,
            status=record.status,
            created_at=to_storage(record.created_at),
        )
        self._session.add(row)
        self._session.flush()

    def get(self, bucket_id: uuid.UUID) -> CapitalBucketRecord | None:
        row = self._session.get(CapitalBucket, bucket_id)
        return None if row is None else _to_record(row)

    def list_by_account(self, account_id: uuid.UUID) -> list[CapitalBucketRecord]:
        stmt = (
            select(CapitalBucket)
            .where(CapitalBucket.account_id == account_id)
            .order_by(CapitalBucket.created_at)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [_to_record(row) for row in rows]


def _to_record(row: CapitalBucket) -> CapitalBucketRecord:
    return CapitalBucketRecord(
        id=row.id,
        account_id=row.account_id,
        name=row.name,
        bucket_role=row.bucket_role,
        is_protected=row.is_protected,
        status=row.status,
        created_at=from_storage(row.created_at),
    )
