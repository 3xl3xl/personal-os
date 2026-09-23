"""Real atomic writes using the canonical temporary SQLite + Alembic fixture."""
from dataclasses import replace
import json
import uuid

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from personal_os.database.schema import Transaction, AuditLog
from personal_os.domain.money import Money
from personal_os.repository.unit_of_work import UnitOfWork
from personal_os.repository.transactions import TransactionRepository
from personal_os.repository.audit_logs import AuditLogRepository
from personal_os.services.write_contract import FinanceWriteContract, WriteReferenceError
from personal_os.services.permissions import PermissionDeniedError
from tests.services.test_write_contract import ACCOUNT, NOW, AUDIT_ID, request, context


@pytest.fixture
def seeded(session_factory):
    with UnitOfWork(session_factory) as uow:
        uow.accounts.add(ACCOUNT)
        uow.commit()
    return session_factory


def service(factory):
    return FinanceWriteContract(factory, clock=lambda: NOW, audit_id_factory=lambda: AUDIT_ID)


def counts(session_factory):
    with session_factory() as session:
        return (len(session.scalars(select(Transaction)).all()), len(session.scalars(select(AuditLog)).all()))


def test_success_roundtrip_one_transaction_one_audit(seeded):
    result = service(lambda: UnitOfWork(seeded)).add_transaction(request(), context=context())
    with UnitOfWork(seeded) as uow:
        stored = uow.transactions.get(result.transaction.id)
        assert stored == result.transaction
        audit = uow.audit_logs.list_all()[0]
        assert audit.affected_entity_id == stored.id
        assert audit.approval_status == "EXPLICITLY_APPROVED"
        assert audit.old_value is None
        assert audit.occurred_at == NOW
        assert json.loads(audit.new_value)["amount"]["amount_minor"] == -123
        assert uow.accounts.get(ACCOUNT.id) == ACCOUNT
    assert counts(seeded) == (1, 1)


def test_unapproved_no_uow_or_db_mutation(seeded):
    def forbidden():
        pytest.fail("opened database before approval")
    with pytest.raises(PermissionDeniedError):
        service(forbidden).add_transaction(request(), context=context(approved=False))
    assert counts(seeded) == (0, 0)


@pytest.mark.parametrize("stage", ["transaction", "audit", "commit"])
def test_real_rollback_after_flushed_writes(seeded, monkeypatch, stage):
    if stage in {"transaction", "audit"}:
        repo = TransactionRepository if stage == "transaction" else AuditLogRepository
        original = repo.add
        def fail(self, record):
            original(self, record)  # actual INSERT + flush has already happened
            raise RuntimeError("synthetic failure")
        monkeypatch.setattr(repo, "add", fail)
        factory = lambda: UnitOfWork(seeded)
    else:
        class FailingCommitUow(UnitOfWork):
            def __enter__(self):
                super().__enter__()
                def fail(session):
                    raise RuntimeError("synthetic failure")
                event.listen(self.session, "before_commit", fail)
                return self
        factory = lambda: FailingCommitUow(seeded)
    with pytest.raises(RuntimeError, match="synthetic failure"):
        service(factory).add_transaction(request(), context=context())
    assert counts(seeded) == (0, 0)


def test_actual_audit_constraint_failure_rolls_back_transaction(seeded, monkeypatch):
    original = AuditLogRepository.add
    def invalid(self, record):
        original(self, replace(record, actor=None))  # NOT NULL constraint
    monkeypatch.setattr(AuditLogRepository, "add", invalid)
    with pytest.raises(IntegrityError):
        service(lambda: UnitOfWork(seeded)).add_transaction(request(), context=context())
    assert counts(seeded) == (0, 0)


def test_actual_fk_constraint_failure_rolls_back(seeded, monkeypatch):
    original = TransactionRepository.add
    def invalid(self, record):
        original(self, replace(record, account_id=uuid.uuid4()))
    monkeypatch.setattr(TransactionRepository, "add", invalid)
    with pytest.raises(IntegrityError):
        service(lambda: UnitOfWork(seeded)).add_transaction(request(), context=context())
    assert counts(seeded) == (0, 0)


def test_duplicate_request_creates_no_additional_transaction_or_audit(seeded):
    write = service(lambda: UnitOfWork(seeded))
    write.add_transaction(request(), context=context())
    with pytest.raises(WriteReferenceError):
        write.add_transaction(request(), context=context())
    assert counts(seeded) == (1, 1)


def test_existing_audit_id_collision_rolls_back_new_transaction(seeded):
    write = service(lambda: UnitOfWork(seeded))
    write.add_transaction(request(), context=context())
    with pytest.raises(IntegrityError):
        write.add_transaction(request(id=uuid.uuid4()), context=context())
    assert counts(seeded) == (1, 1)


def test_exact_large_integer_roundtrip(seeded):
    value = 2**60 + 1
    result = service(lambda: UnitOfWork(seeded)).add_transaction(request(amount=Money(value, "JPY")), context=context())
    with UnitOfWork(seeded) as uow:
        assert uow.transactions.get(result.transaction.id).amount.amount_minor == value
        assert json.loads(uow.audit_logs.list_all()[0].new_value)["amount"]["amount_minor"] == value


def test_integer_overflow_fails_without_rounding_or_rows(seeded):
    with pytest.raises(OverflowError):
        service(lambda: UnitOfWork(seeded)).add_transaction(request(amount=Money(2**80, "JPY")), context=context())
    assert counts(seeded) == (0, 0)


def test_single_real_commit(seeded):
    commits = []
    class CountingUow(UnitOfWork):
        def __enter__(self):
            super().__enter__()
            event.listen(self.session, "after_commit", lambda session: commits.append(True))
            return self
    service(lambda: CountingUow(seeded)).add_transaction(request(), context=context())
    assert commits == [True]
    assert counts(seeded) == (1, 1)
