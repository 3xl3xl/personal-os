"""Real atomic writes using the canonical temporary SQLite + Alembic fixture."""
import json
import uuid
from dataclasses import replace

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from personal_os.database.schema import Account, AuditLog
from personal_os.repository.unit_of_work import UnitOfWork
from personal_os.repository.accounts import AccountRepository
from personal_os.repository.audit_logs import AuditLogRepository
from personal_os.services.account_write_contract import AccountWriteContract, WriteReferenceError
from personal_os.services.permissions import PermissionDeniedError
from tests.services.test_account_write_contract import NOW, AUDIT_ID, request, context


def service(factory):
    return AccountWriteContract(factory, clock=lambda: NOW, audit_id_factory=lambda: AUDIT_ID)


def counts(session_factory):
    with session_factory() as session:
        return (len(session.scalars(select(Account)).all()), len(session.scalars(select(AuditLog)).all()))


def test_success_roundtrip_one_account_one_audit(session_factory):
    result = service(lambda: UnitOfWork(session_factory)).add_account(request(), context=context())
    with UnitOfWork(session_factory) as uow:
        stored = uow.accounts.get(result.account.id)
        assert stored == result.account
        audit = uow.audit_logs.list_all()[0]
        assert audit.affected_entity_id == stored.id
        assert audit.approval_status == "EXPLICITLY_APPROVED"
        assert audit.old_value is None
        assert audit.occurred_at == NOW
        assert json.loads(audit.new_value)["currency_code"] == "JPY"
    assert counts(session_factory) == (1, 1)


def test_unapproved_no_uow_or_db_mutation(session_factory):
    def forbidden():
        pytest.fail("opened database before approval")
    with pytest.raises(PermissionDeniedError):
        service(forbidden).add_account(request(), context=context(approved=False))
    assert counts(session_factory) == (0, 0)


@pytest.mark.parametrize("stage", ["account", "audit", "commit"])
def test_real_rollback_after_flushed_writes(session_factory, monkeypatch, stage):
    if stage in {"account", "audit"}:
        repo = AccountRepository if stage == "account" else AuditLogRepository
        original = repo.add
        def fail(self, record):
            original(self, record)  # actual INSERT + flush has already happened
            raise RuntimeError("synthetic failure")
        monkeypatch.setattr(repo, "add", fail)
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
        service(factory).add_account(request(), context=context())
    assert counts(session_factory) == (0, 0)


def test_actual_audit_constraint_failure_rolls_back_account(session_factory, monkeypatch):
    original = AuditLogRepository.add
    def invalid(self, record):
        original(self, replace(record, actor=None))  # NOT NULL constraint
    monkeypatch.setattr(AuditLogRepository, "add", invalid)
    with pytest.raises(IntegrityError):
        service(lambda: UnitOfWork(session_factory)).add_account(request(), context=context())
    assert counts(session_factory) == (0, 0)


def test_duplicate_account_id_creates_no_additional_account_or_audit(session_factory):
    write = service(lambda: UnitOfWork(session_factory))
    write.add_account(request(), context=context())
    with pytest.raises(WriteReferenceError):
        write.add_account(request(), context=context())
    assert counts(session_factory) == (1, 1)


def test_existing_audit_id_collision_rolls_back_new_account(session_factory):
    write = service(lambda: UnitOfWork(session_factory))
    write.add_account(request(), context=context())
    with pytest.raises(IntegrityError):
        write.add_account(request(id=uuid.uuid4()), context=context())
    assert counts(session_factory) == (1, 1)


def test_single_real_commit(session_factory):
    commits = []
    class CountingUow(UnitOfWork):
        def __enter__(self):
            super().__enter__()
            event.listen(self.session, "after_commit", lambda session: commits.append(True))
            return self
    service(lambda: CountingUow(session_factory)).add_account(request(), context=context())
    assert commits == [True]
    assert counts(session_factory) == (1, 1)
