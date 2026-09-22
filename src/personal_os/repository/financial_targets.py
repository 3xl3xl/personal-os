"""
FinancialTarget repository -- Repository Layer access to the
`financial_targets` table (append/version-only; Finance v0.1 Schema
Design, Q4).

No update/delete method: rows are append/version-only (Step 4
docstring). No "effective version at time T" query here either: Step
4's own schema module docstring assigns that selection rule
(MAX(effective_from) <= evaluation_time) to the Service Layer, not to
this schema/repository layer -- computing it here would be exactly the
kind of business decision Step 6, item 1 tells the Repository Layer
not to make. list_by_metric() returns every version, ordered by
effective_from, and leaves version selection to whichever future
Service Layer step implements it.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from personal_os.database.schema import FinancialTarget
from personal_os.domain.money import Money
from personal_os.domain.records import FinancialTargetRecord
from personal_os.repository._datetime_adapter import from_storage, to_storage


class FinancialTargetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: FinancialTargetRecord) -> None:
        row = FinancialTarget(
            id=record.id,
            metric_key=record.metric_key,
            target_amount_minor=record.target_amount.amount_minor,
            currency_code=record.target_amount.currency_code,
            effective_from=to_storage(record.effective_from),
            created_at=to_storage(record.created_at),
        )
        self._session.add(row)
        self._session.flush()

    def list_by_metric(self, metric_key: str) -> list[FinancialTargetRecord]:
        stmt = (
            select(FinancialTarget)
            .where(FinancialTarget.metric_key == metric_key)
            .order_by(FinancialTarget.effective_from)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [_to_record(row) for row in rows]


def _to_record(row: FinancialTarget) -> FinancialTargetRecord:
    return FinancialTargetRecord(
        id=row.id,
        metric_key=row.metric_key,
        target_amount=Money(row.target_amount_minor, row.currency_code),
        effective_from=from_storage(row.effective_from),
        created_at=from_storage(row.created_at),
    )
