"""Real atomic writes using the canonical temporary SQLite + Alembic fixture,
covering both AddFinancialTargetInput/Q4 and AddMonthlyTargetInput/Q5, plus
the real DB-level FK-to-financial_metrics and UniqueConstraint that the
service-layer checks are meant to pre-empt (defense-in-depth)."""
import uuid
from dataclasses import replace

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from personal_os.database.schema import AuditLog, FinancialTarget, MonthlyTarget
from personal_os.domain.records import FinancialMetricRecord
from personal_os.repository.unit_of_work import UnitOfWork
from personal_os.repository.financial_targets import FinancialTargetRepository
from personal_os.repository.monthly_targets import MonthlyTargetRepository
from personal_os.repository.audit_logs import AuditLogRepository
from personal_os.services.permissions import PermissionDeniedError
from personal_os.services.target_write_contract import TargetWriteContract, WriteReferenceError
from tests.services.test_target_write_contract import NOW, AUDIT_ID, METRIC_KEY, financial_request, monthly_request, context


def service(factory):
    return TargetWriteContract(factory, clock=lambda: NOW, audit_id_factory=lambda: AUDIT_ID)


def counts(session_factory):
    with session_factory() as session:
        return (len(session.scalars(select(FinancialTarget)).all()),
                len(session.scalars(select(MonthlyTarget)).all()),
                len(session.scalars(select(AuditLog)).all()))


def seed_metric(session_factory, key=METRIC_KEY):
    with UnitOfWork(session_factory) as uow:
        uow.financial_metrics.add(FinancialMetricRecord(id=uuid.uuid4(), key=key, display_name="synthetic KPI", created_at=NOW))
        uow.commit()


def test_financial_target_success_roundtrip(session_factory):
    seed_metric(session_factory)
    result = service(lambda: UnitOfWork(session_factory)).add_financial_target(financial_request(), context=context())
    with UnitOfWork(session_factory) as uow:
        [stored] = uow.financial_targets.list_by_metric(METRIC_KEY)
        assert stored == result.target
        audit = uow.audit_logs.list_all()[0]
        assert audit.affected_entity_id == stored.id
        assert audit.occurred_at == NOW
    assert counts(session_factory) == (1, 0, 1)


def test_monthly_target_success_roundtrip(session_factory):
    seed_metric(session_factory)
    result = service(lambda: UnitOfWork(session_factory)).add_monthly_target(monthly_request(), context=context())
    with UnitOfWork(session_factory) as uow:
        [stored] = uow.monthly_targets.list_by_metric_year_month(METRIC_KEY, 2026, 3)
        assert stored == result.target
    assert counts(session_factory) == (0, 1, 1)


@pytest.mark.parametrize("method,build", [("add_financial_target", financial_request), ("add_monthly_target", monthly_request)])
def test_unapproved_no_uow_or_db_mutation(session_factory, method, build):
    def forbidden():
        pytest.fail("opened database before approval")
    with pytest.raises(PermissionDeniedError):
        getattr(service(forbidden), method)(build(), context=context(approved=False))
    assert counts(session_factory) == (0, 0, 0)


@pytest.mark.parametrize("method,build,repo", [
    ("add_financial_target", financial_request, FinancialTargetRepository),
    ("add_monthly_target", monthly_request, MonthlyTargetRepository),
])
@pytest.mark.parametrize("stage", ["target", "audit", "commit"])
def test_real_rollback_after_flushed_writes(session_factory, monkeypatch, method, build, repo, stage):
    seed_metric(session_factory)
    if stage in {"target", "audit"}:
        active_repo = repo if stage == "target" else AuditLogRepository
        original = active_repo.add
        def fail(self, record):
            original(self, record)  # actual INSERT + flush has already happened
            raise RuntimeError("synthetic failure")
        monkeypatch.setattr(active_repo, "add", fail)
        factory = lambda: UnitOfWork(session_factory)
    else:
        class FailingCommitUow(UnitOfWork):
            def __enter__(self):
                super().__enter__()
                def fail(session):
                    raise RuntimeError("synthetic failure")
                event.listen(self.session, "before_commit", fail)
                return self
        factory = lambda: FailingCommitUow(session_factory)
    with pytest.raises(RuntimeError, match="synthetic failure"):
        getattr(service(factory), method)(build(), context=context())
    assert counts(session_factory) == (0, 0, 0)


@pytest.mark.parametrize("method,build", [("add_financial_target", financial_request), ("add_monthly_target", monthly_request)])
def test_actual_audit_constraint_failure_rolls_back_target(session_factory, monkeypatch, method, build):
    seed_metric(session_factory)
    original = AuditLogRepository.add
    def invalid(self, record):
        original(self, replace(record, actor=None))  # NOT NULL constraint
    monkeypatch.setattr(AuditLogRepository, "add", invalid)
    with pytest.raises(IntegrityError):
        getattr(service(lambda: UnitOfWork(session_factory)), method)(build(), context=context())
    assert counts(session_factory) == (0, 0, 0)


@pytest.mark.parametrize("method,build", [("add_financial_target", financial_request), ("add_monthly_target", monthly_request)])
def test_unknown_metric_key_creates_no_rows(session_factory, method, build):
    with pytest.raises(WriteReferenceError, match="financial metric not found"):
        getattr(service(lambda: UnitOfWork(session_factory)), method)(build(), context=context())
    assert counts(session_factory) == (0, 0, 0)


def test_app_level_duplicate_financial_effective_from_creates_no_additional_row(session_factory):
    seed_metric(session_factory)
    write = service(lambda: UnitOfWork(session_factory))
    write.add_financial_target(financial_request(), context=context())
    with pytest.raises(WriteReferenceError, match="already exists"):
        write.add_financial_target(financial_request(id=uuid.uuid4()), context=context())
    assert counts(session_factory) == (1, 0, 1)


def test_app_level_duplicate_monthly_effective_from_creates_no_additional_row(session_factory):
    seed_metric(session_factory)
    write = service(lambda: UnitOfWork(session_factory))
    write.add_monthly_target(monthly_request(), context=context())
    with pytest.raises(WriteReferenceError, match="already exists"):
        write.add_monthly_target(monthly_request(id=uuid.uuid4()), context=context())
    assert counts(session_factory) == (0, 1, 1)


def test_db_level_fk_defends_even_if_app_check_were_bypassed(session_factory, monkeypatch):
    """Defense-in-depth: even with the service-layer existence check disabled,
    the real financial_targets.metric_key -> financial_metrics.key ForeignKey
    still refuses a write against a metric that does not exist in the DB."""
    from personal_os.repository.financial_metrics import FinancialMetricRepository
    monkeypatch.setattr(FinancialMetricRepository, "get_by_key", lambda self, key: object())
    with pytest.raises(IntegrityError):
        service(lambda: UnitOfWork(session_factory)).add_financial_target(financial_request(), context=context())
    assert counts(session_factory) == (0, 0, 0)


def test_db_level_unique_constraint_defends_even_if_app_check_were_bypassed(session_factory, monkeypatch):
    """Defense-in-depth: even with the service-layer duplicate-effective_from
    check disabled, the real UniqueConstraint(metric_key, effective_from)
    still refuses a second version at the same effective_from."""
    seed_metric(session_factory)
    write = service(lambda: UnitOfWork(session_factory))
    write.add_financial_target(financial_request(), context=context())
    monkeypatch.setattr(FinancialTargetRepository, "list_by_metric", lambda self, key: [])
    with pytest.raises(IntegrityError):
        write.add_financial_target(financial_request(id=uuid.uuid4()), context=context())
    assert counts(session_factory) == (1, 0, 1)


def test_same_metric_different_year_month_both_persist(session_factory):
    seed_metric(session_factory)
    audit_ids = iter([AUDIT_ID, uuid.uuid4()])
    write = TargetWriteContract(lambda: UnitOfWork(session_factory), clock=lambda: NOW, audit_id_factory=lambda: next(audit_ids))
    write.add_monthly_target(monthly_request(), context=context())
    write.add_monthly_target(monthly_request(id=uuid.uuid4(), month=4), context=context())
    with UnitOfWork(session_factory) as uow:
        assert len(uow.monthly_targets.list_by_metric_year_month(METRIC_KEY, 2026, 3)) == 1
        assert len(uow.monthly_targets.list_by_metric_year_month(METRIC_KEY, 2026, 4)) == 1
    assert counts(session_factory) == (0, 2, 2)


def test_single_real_commit(session_factory):
    seed_metric(session_factory)
    commits = []
    class CountingUow(UnitOfWork):
        def __enter__(self):
            super().__enter__()
            event.listen(self.session, "after_commit", lambda session: commits.append(True))
            return self
    service(lambda: CountingUow(session_factory)).add_financial_target(financial_request(), context=context())
    assert commits == [True]
    assert counts(session_factory) == (1, 0, 1)
