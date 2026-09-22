"""
MonthlyTarget repository -- Repository Layer access to the
`monthly_targets` table (append/version-only; Finance v0.1 Schema
Design, Q5).

Same reasoning as FinancialTargetRepository: no update/delete, and no
"effective version at time T" query here -- that selection rule is a
Service-Layer responsibility per Step 4's schema module docstring.
list_by_metric_year_month() returns every version for a given
(metric_key, year, month), ordered by effective_from.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from personal_os.database.schema import MonthlyTarget
from personal_os.domain.money import Money
from personal_os.domain.records import MonthlyTargetRecord
from personal_os.repository._datetime_adapter import from_storage, to_storage


class MonthlyTargetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: MonthlyTargetRecord) -> None:
        row = MonthlyTarget(
            id=record.id,
            metric_key=record.metric_key,
            year=record.year,
            month=record.month,
            target_amount_minor=record.target_amount.amount_minor,
            currency_code=record.target_amount.currency_code,
            effective_from=to_storage(record.effective_from),
            created_at=to_storage(record.created_at),
        )
        self._session.add(row)
        self._session.flush()

    def list_by_metric_year_month(
        self, metric_key: str, year: int, month: int
    ) -> list[MonthlyTargetRecord]:
        stmt = (
            select(MonthlyTarget)
            .where(
                MonthlyTarget.metric_key == metric_key,
                MonthlyTarget.year == year,
                MonthlyTarget.month == month,
            )
            .order_by(MonthlyTarget.effective_from)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [_to_record(row) for row in rows]


def _to_record(row: MonthlyTarget) -> MonthlyTargetRecord:
    return MonthlyTargetRecord(
        id=row.id,
        metric_key=row.metric_key,
        year=row.year,
        month=row.month,
        target_amount=Money(row.target_amount_minor, row.currency_code),
        effective_from=from_storage(row.effective_from),
        created_at=from_storage(row.created_at),
    )
