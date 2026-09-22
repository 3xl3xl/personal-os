"""Step 6 -- MonthlyTarget append/read."""

from __future__ import annotations

from personal_os.domain.datetime import utc_now
from personal_os.domain.ids import new_id
from personal_os.domain.money import Money
from personal_os.domain.records import FinancialMetricRecord, MonthlyTargetRecord
from personal_os.repository.financial_metrics import FinancialMetricRepository
from personal_os.repository.monthly_targets import MonthlyTargetRepository


def _make_metric(session, key: str) -> FinancialMetricRecord:
    metric = FinancialMetricRecord(id=new_id(), key=key, display_name=key, created_at=utc_now())
    FinancialMetricRepository(session).add(metric)
    return metric


def test_monthly_target_append_and_read(session_factory):
    session = session_factory()
    try:
        metric = _make_metric(session, "self_generated_revenue")
        repo = MonthlyTargetRepository(session)
        record = MonthlyTargetRecord(
            id=new_id(),
            metric_key=metric.key,
            year=2026,
            month=10,
            target_amount=Money(500_000_00, "JPY"),
            effective_from=utc_now(),
            created_at=utc_now(),
        )

        repo.add(record)
        session.commit()

        listed = repo.list_by_metric_year_month(metric.key, 2026, 10)
        assert listed == [record]
    finally:
        session.close()


def test_list_by_metric_year_month_excludes_other_months(session_factory):
    session = session_factory()
    try:
        metric = _make_metric(session, "self_generated_revenue")
        repo = MonthlyTargetRepository(session)

        october = MonthlyTargetRecord(
            id=new_id(), metric_key=metric.key, year=2026, month=10,
            target_amount=Money(500_000_00, "JPY"), effective_from=utc_now(), created_at=utc_now(),
        )
        november = MonthlyTargetRecord(
            id=new_id(), metric_key=metric.key, year=2026, month=11,
            target_amount=Money(600_000_00, "JPY"), effective_from=utc_now(), created_at=utc_now(),
        )
        repo.add(october)
        repo.add(november)
        session.commit()

        listed = repo.list_by_metric_year_month(metric.key, 2026, 10)
        assert [r.id for r in listed] == [october.id]
    finally:
        session.close()
