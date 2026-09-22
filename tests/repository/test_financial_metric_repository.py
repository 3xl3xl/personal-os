"""Step 6 -- FinancialMetric write/read."""

from __future__ import annotations

from personal_os.domain.datetime import utc_now
from personal_os.domain.ids import new_id
from personal_os.domain.records import FinancialMetricRecord
from personal_os.repository.financial_metrics import FinancialMetricRepository


def test_financial_metric_write_read(session_factory):
    session = session_factory()
    try:
        repo = FinancialMetricRepository(session)
        record = FinancialMetricRecord(
            id=new_id(),
            key="net_worth",
            display_name="Net Worth",
            created_at=utc_now(),
        )

        repo.add(record)
        session.commit()

        got = repo.get_by_key("net_worth")
        assert got == record
    finally:
        session.close()


def test_get_by_key_returns_none_for_unknown_key(session_factory):
    session = session_factory()
    try:
        repo = FinancialMetricRepository(session)
        assert repo.get_by_key("does_not_exist") is None
    finally:
        session.close()
