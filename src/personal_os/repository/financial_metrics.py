"""
FinancialMetric repository -- Repository Layer access to the
`financial_metrics` lookup table.

No update method: Step 6's test list only calls for write/read; a
display_name rename is a real future write with no current caller,
deferred rather than speculatively added.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from personal_os.database.schema import FinancialMetric
from personal_os.domain.records import FinancialMetricRecord
from personal_os.repository._datetime_adapter import from_storage, to_storage


class FinancialMetricRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: FinancialMetricRecord) -> None:
        row = FinancialMetric(
            id=record.id,
            key=record.key,
            display_name=record.display_name,
            created_at=to_storage(record.created_at),
        )
        self._session.add(row)
        self._session.flush()

    def get_by_key(self, key: str) -> FinancialMetricRecord | None:
        stmt = select(FinancialMetric).where(FinancialMetric.key == key)
        row = self._session.execute(stmt).scalar_one_or_none()
        return None if row is None else _to_record(row)


def _to_record(row: FinancialMetric) -> FinancialMetricRecord:
    return FinancialMetricRecord(
        id=row.id,
        key=row.key,
        display_name=row.display_name,
        created_at=from_storage(row.created_at),
    )
