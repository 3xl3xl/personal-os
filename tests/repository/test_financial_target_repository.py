"""Step 6 -- FinancialTarget append/read."""

from __future__ import annotations

import datetime as dt

from personal_os.domain.datetime import utc_now
from personal_os.domain.ids import new_id
from personal_os.domain.money import Money
from personal_os.domain.records import FinancialMetricRecord, FinancialTargetRecord
from personal_os.repository.financial_metrics import FinancialMetricRepository
from personal_os.repository.financial_targets import FinancialTargetRepository


def _make_metric(session, key: str) -> FinancialMetricRecord:
    metric = FinancialMetricRecord(id=new_id(), key=key, display_name=key, created_at=utc_now())
    FinancialMetricRepository(session).add(metric)
    return metric


def test_financial_target_append_and_read(session_factory):
    session = session_factory()
    try:
        metric = _make_metric(session, "net_worth")
        repo = FinancialTargetRepository(session)
        record = FinancialTargetRecord(
            id=new_id(),
            metric_key=metric.key,
            target_amount=Money(10_000_000_00, "JPY"),
            effective_from=utc_now(),
            created_at=utc_now(),
        )

        repo.add(record)
        session.commit()

        listed = repo.list_by_metric(metric.key)
        assert listed == [record]
    finally:
        session.close()


def test_multiple_versions_are_appended_not_overwritten(session_factory):
    session = session_factory()
    try:
        metric = _make_metric(session, "net_worth")
        repo = FinancialTargetRepository(session)

        earlier = FinancialTargetRecord(
            id=new_id(), metric_key=metric.key, target_amount=Money(5_000_000_00, "JPY"),
            effective_from=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc), created_at=utc_now(),
        )
        later = FinancialTargetRecord(
            id=new_id(), metric_key=metric.key, target_amount=Money(6_000_000_00, "JPY"),
            effective_from=dt.datetime(2026, 6, 1, tzinfo=dt.timezone.utc), created_at=utc_now(),
        )
        repo.add(earlier)
        repo.add(later)
        session.commit()

        listed = repo.list_by_metric(metric.key)
        assert [r.id for r in listed] == [earlier.id, later.id]
    finally:
        session.close()
