"""
Step 6, items 7-8 -- Unit of Work transaction boundary: commit,
rollback, and multiple repository operations sharing one transaction.
"""

from __future__ import annotations

import pytest

from sqlalchemy import select

from personal_os.database.schema import Account
from personal_os.domain.datetime import utc_now
from personal_os.domain.enums import (
    AccountStatus,
    AccountType,
    TransactionKind,
    TransactionStatus,
)
from personal_os.domain.ids import new_id
from personal_os.domain.money import Money
from personal_os.domain.records import AccountRecord, TransactionRecord
from personal_os.repository.unit_of_work import UnitOfWork


class _DeliberateTestError(Exception):
    """Raised mid-transaction to prove rollback discards partial writes."""


def _account_count(session_factory) -> int:
    session = session_factory()
    try:
        return len(session.execute(select(Account)).scalars().all())
    finally:
        session.close()


def test_multiple_repository_operations_share_one_commit(session_factory):
    account = AccountRecord(
        id=new_id(), name="UoW Account", account_type=AccountType.CASH,
        currency_code="JPY", opened_at=utc_now(), status=AccountStatus.ACTIVE,
    )
    transaction = TransactionRecord(
        id=new_id(), account_id=account.id, transaction_type=TransactionKind.NORMAL,
        amount=Money(1000, "JPY"), occurred_at=utc_now(), status=TransactionStatus.ACTIVE,
    )

    with UnitOfWork(session_factory) as uow:
        uow.accounts.add(account)
        uow.transactions.add(transaction)
        uow.commit()

    with UnitOfWork(session_factory) as uow:
        assert uow.accounts.get(account.id) == account
        assert uow.transactions.get(transaction.id) == transaction


def test_no_commit_call_results_in_rollback_on_clean_exit(session_factory):
    """Even without an exception, forgetting to call commit() must not
    silently persist the write -- there is no implicit commit."""
    account = AccountRecord(
        id=new_id(), name="Never Committed", account_type=AccountType.CASH,
        currency_code="JPY", opened_at=utc_now(), status=AccountStatus.ACTIVE,
    )

    with UnitOfWork(session_factory) as uow:
        uow.accounts.add(account)
        # deliberately no uow.commit()

    assert _account_count(session_factory) == 0


def test_exception_mid_transaction_rolls_back_all_writes_no_partial_write(session_factory):
    before_count = _account_count(session_factory)

    account = AccountRecord(
        id=new_id(), name="Rolled Back Account", account_type=AccountType.CASH,
        currency_code="JPY", opened_at=utc_now(), status=AccountStatus.ACTIVE,
    )
    transaction = TransactionRecord(
        id=new_id(), account_id=account.id, transaction_type=TransactionKind.NORMAL,
        amount=Money(1000, "JPY"), occurred_at=utc_now(), status=TransactionStatus.ACTIVE,
    )

    try:
        with UnitOfWork(session_factory) as uow:
            uow.accounts.add(account)
            uow.transactions.add(transaction)
            raise _DeliberateTestError("simulated failure after two writes")
    except _DeliberateTestError:
        pass

    with UnitOfWork(session_factory) as uow:
        assert uow.accounts.get(account.id) is None
        assert uow.transactions.get(transaction.id) is None

    assert _account_count(session_factory) == before_count


def test_explicit_rollback_call_also_discards_writes(session_factory):
    account = AccountRecord(
        id=new_id(), name="Explicitly Rolled Back", account_type=AccountType.CASH,
        currency_code="JPY", opened_at=utc_now(), status=AccountStatus.ACTIVE,
    )

    with UnitOfWork(session_factory) as uow:
        uow.accounts.add(account)
        uow.rollback()

    with UnitOfWork(session_factory) as uow:
        assert uow.accounts.get(account.id) is None


class _SimulatedCommitError(Exception):
    """Stands in for a real DBAPI/constraint error raised by session.commit()."""


def test_commit_failure_rolls_back_leaves_no_partial_write_and_propagates(
    session_factory, monkeypatch
):
    """UnitOfWork.commit() itself -- not just __exit__ -- must roll back
    when session.commit() raises, and must never swallow the error.
    """
    account = AccountRecord(
        id=new_id(), name="Commit Failure Test", account_type=AccountType.CASH,
        currency_code="JPY", opened_at=utc_now(), status=AccountStatus.ACTIVE,
    )

    with UnitOfWork(session_factory) as uow:
        uow.accounts.add(account)

        real_rollback = uow.session.rollback
        rollback_calls: list[bool] = []

        def _spy_rollback():
            rollback_calls.append(True)
            real_rollback()

        def _failing_commit():
            raise _SimulatedCommitError("simulated commit-time failure")

        monkeypatch.setattr(uow.session, "commit", _failing_commit)
        monkeypatch.setattr(uow.session, "rollback", _spy_rollback)

        with pytest.raises(_SimulatedCommitError):
            uow.commit()

        assert rollback_calls, "commit() failure must trigger session.rollback()"

    # From a completely fresh UnitOfWork/session: nothing from the
    # failed transaction survived -- no partial/half-committed write.
    with UnitOfWork(session_factory) as fresh_uow:
        assert fresh_uow.accounts.get(account.id) is None
