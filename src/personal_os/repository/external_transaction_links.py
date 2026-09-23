"""
ExternalTransactionLink repository -- Repository Layer access to the
`external_transaction_links` table (ADR-014, freee read-only integration).

Append-only: no update/delete method. `find()` is the one read this
integration needs -- a single dedup lookup by the four-part external
identity -- not a generic query interface.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from personal_os.database.schema import ExternalTransactionLink
from personal_os.domain.enums import ExternalSource
from personal_os.domain.records import ExternalTransactionLinkRecord
from personal_os.repository._datetime_adapter import from_storage, to_storage


class ExternalTransactionLinkRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: ExternalTransactionLinkRecord) -> None:
        row = ExternalTransactionLink(
            id=record.id,
            source=record.source.value,
            external_office_id=record.external_office_id,
            external_account_id=record.external_account_id,
            external_transaction_id=record.external_transaction_id,
            transaction_id=record.transaction_id,
            imported_at=to_storage(record.imported_at),
        )
        self._session.add(row)
        self._session.flush()

    def find(
        self,
        *,
        source: ExternalSource,
        external_office_id: str,
        external_account_id: str,
        external_transaction_id: str,
    ) -> ExternalTransactionLinkRecord | None:
        stmt = select(ExternalTransactionLink).where(
            ExternalTransactionLink.source == source.value,
            ExternalTransactionLink.external_office_id == external_office_id,
            ExternalTransactionLink.external_account_id == external_account_id,
            ExternalTransactionLink.external_transaction_id == external_transaction_id,
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        return None if row is None else _to_record(row)


def _to_record(row: ExternalTransactionLink) -> ExternalTransactionLinkRecord:
    return ExternalTransactionLinkRecord(
        id=row.id,
        source=ExternalSource(row.source),
        external_office_id=row.external_office_id,
        external_account_id=row.external_account_id,
        external_transaction_id=row.external_transaction_id,
        transaction_id=row.transaction_id,
        imported_at=from_storage(row.imported_at),
    )
