"""Real atomic writes using the canonical temporary SQLite + Alembic fixture,
plus the real DB-level constraints (FK to accounts, unique transaction ID)
that the service-layer checks are meant to pre-empt (defense-in-depth)."""
import json
import uuid
from dataclasses import replace

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError

from personal_os.database.schema import AuditLog, Transaction
from personal_os.domain.enums import AccountStatus, AccountType
from personal_os.domain.records import AccountRecord
from personal_os.repository.audit_logs import AuditLogRepository
from personal_os.repository.transactions import TransactionRepository
from personal_os.repository.unit_of_work import UnitOfWork
from personal_os.services.opening_balance_write_contract import OpeningBalanceWriteContract, WriteReferenceError
from personal_os.services.permissions import PermissionDeniedError
from tests.services.test_opening_balance_write_contract import NOW, AUDIT_ID, ACCOUNT_ID, request, context


def service(factory):
    return OpeningBalanceWriteContract(factory, clock=lambda: NOW, audit_id_factory=lambda: AUDIT_ID)


def counts(session_factory):
    with session_factory() as session:
        return (len(session.scalars(select(Transaction)).all()), len(session.scalars(select(AuditLog)).all()))


def seed_account(session_factory, account_id=ACCOUNT_ID, currency_code="JPY"):
    with UnitOfWork(session_factory) as uow:
        uow.accounts.add(AccountRecord(
            id=account_id, name="synthetic account", account_type=AccountType.CASH,
            currency_code=currency_code, opened_at=NOW, status=AccountStatus.ACTIVE,
        ))
        uow.commit()


def test_success_roundtrip_one_transaction_one_audit(session_factory):
    seed_account(session_factory)
    result = service(lambda: UnitOfWork(session_factory)).add_opening_balance(request(), context=context())
    with UnitOfWork(session_factory) as uow:
        stored = uow.transactions.get(result.transaction.id)
        assert stored == result.transaction
        audit = uow.audit_logs.list_all()[0]
        assert audit.affected_entity_id == stored.id
        assert audit.action == "add_opening_balance"
        assert audit.approval_status == "EXPLICITLY_APPROVED"
        assert audit.old_value is None
        assert audit.occurred_at == NOW
        assert json.loads(audit.new_value)["transaction_type"] == "OPENING_BALANCE"
    assert counts(session_factory) == (1, 1)


def test_unapproved_no_uow_or_db_mutation(session_factory):
    seed_account(session_factory)
    def forbidden():
        pytest.fail("opened database before approval")
    with pytest.raises(PermissionDeniedError):
        service(forbidden).add_opening_balance(request(), context=context(approved=False))
    assert counts(session_factory) == (0, 0)


@pytest.mark.parametrize("stage", ["transaction", "audit", "commit"])
def test_real_rollback_after_flushed_writes(session_factory, monkeypatch, stage):
    seed_account(session_factory)
    if stage in {"transaction", "audit"}:
        repo = TransactionRepository if stage == "transaction" else AuditLogRepository
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
        service(factory).add_opening_balance(request(), context=context())
    assert counts(session_factory) == (0, 0)


def test_actual_audit_constraint_failure_rolls_back_transaction(session_factory, monkeypatch):
    seed_account(session_factory)
    original = AuditLogRepository.add
    def invalid(self, record):
        original(self, replace(record, actor=None))  # NOT NULL constraint
    monkeypatch.setattr(AuditLogRepository, "add", invalid)
    with pytest.raises(IntegrityError):
        service(lambda: UnitOfWork(session_factory)).add_opening_balance(request(), context=context())
    assert counts(session_factory) == (0, 0)


def test_duplicate_transaction_id_creates_no_additional_row(session_factory):
    seed_account(session_factory)
    write = service(lambda: UnitOfWork(session_factory))
    write.add_opening_balance(request(), context=context())
    with pytest.raises(WriteReferenceError):
        write.add_opening_balance(request(), context=context())
    assert counts(session_factory) == (1, 1)


def test_second_opening_balance_same_account_creates_no_additional_row(session_factory):
    seed_account(session_factory)
    write = service(lambda: UnitOfWork(session_factory))
    write.add_opening_balance(request(), context=context())
    with pytest.raises(WriteReferenceError, match="already has an opening balance"):
        write.add_opening_balance(request(id=uuid.uuid4()), context=context())
    assert counts(session_factory) == (1, 1)


def test_existing_audit_id_collision_rolls_back_new_transaction(session_factory):
    # A second, distinct account -- the one-opening-balance-per-account check
    # must not be what blocks this write; only the AuditLog.id collision should.
    second_account_id = uuid.uuid4()
    seed_account(session_factory)
    seed_account(session_factory, account_id=second_account_id)
    write = service(lambda: UnitOfWork(session_factory))
    write.add_opening_balance(request(), context=context())
    with pytest.raises(IntegrityError):
        write.add_opening_balance(request(id=uuid.uuid4(), account_id=second_account_id), context=context())
    assert counts(session_factory) == (1, 1)


def test_db_level_fk_defends_even_if_app_check_were_bypassed(session_factory, monkeypatch):
    """Defense-in-depth: even with the service-layer existence check disabled,
    the real transactions.account_id -> accounts.id ForeignKey still refuses a
    write against an account that does not exist in the DB. No account is
    seeded; the fake stands in only far enough to pass the currency check."""
    from types import SimpleNamespace
    from personal_os.repository.accounts import AccountRepository
    monkeypatch.setattr(AccountRepository, "get", lambda self, account_id: SimpleNamespace(currency_code="JPY"))
    with pytest.raises(IntegrityError):
        service(lambda: UnitOfWork(session_factory)).add_opening_balance(request(), context=context())
    assert counts(session_factory) == (0, 0)


def test_db_level_unique_transaction_id_defends_even_if_app_check_were_bypassed(session_factory, monkeypatch):
    """Defense-in-depth: even with both the service-layer duplicate-transaction-ID
    check AND the one-opening-balance-per-account check disabled, the real
    transactions.id primary key still refuses a second row with the same ID."""
    seed_account(session_factory)
    write = service(lambda: UnitOfWork(session_factory))
    write.add_opening_balance(request(), context=context())
    monkeypatch.setattr(TransactionRepository, "get", lambda self, transaction_id: None)
    monkeypatch.setattr(TransactionRepository, "list_by_account", lambda self, account_id: [])
    with pytest.raises(IntegrityError):
        write.add_opening_balance(request(), context=context())
    assert counts(session_factory) == (1, 1)


def test_single_real_commit(session_factory):
    seed_account(session_factory)
    commits = []
    class CountingUow(UnitOfWork):
        def __enter__(self):
            super().__enter__()
            event.listen(self.session, "after_commit", lambda session: commits.append(True))
            return self
    service(lambda: CountingUow(session_factory)).add_opening_balance(request(), context=context())
    assert commits == [True]
    assert counts(session_factory) == (1, 1)
