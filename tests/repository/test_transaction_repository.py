"""Step 6 -- Transaction write/read roundtrip."""

from __future__ import annotations

from personal_os.domain.datetime import utc_now
from personal_os.domain.enums import AccountStatus, AccountType, TransactionKind, TransactionStatus
from personal_os.domain.ids import new_id
from personal_os.domain.money import Money
from personal_os.domain.records import AccountRecord, TransactionRecord
from personal_os.repository.accounts import AccountRepository
from personal_os.repository.transactions import TransactionRepository


def _make_account(session) -> AccountRecord:
    repo = AccountRepository(session)
    record = AccountRecord(
        id=new_id(), name="Main", account_type=AccountType.CASH,
        currency_code="JPY", opened_at=utc_now(), status=AccountStatus.ACTIVE,
    )
    repo.add(record)
    return record


def test_transaction_write_read_roundtrip(session_factory):
    session = session_factory()
    try:
        account = _make_account(session)
        repo = TransactionRepository(session)
        record = TransactionRecord(
            id=new_id(),
            account_id=account.id,
            transaction_type=TransactionKind.NORMAL,
            amount=Money(150_000, "JPY"),
            occurred_at=utc_now(),
            status=TransactionStatus.ACTIVE,
            memo="test transaction",
        )

        repo.add(record)
        session.commit()

        got = repo.get(record.id)
        assert got == record
    finally:
        session.close()


def test_list_by_account_returns_only_that_accounts_transactions(session_factory):
    session = session_factory()
    try:
        account_a = _make_account(session)
        account_b = _make_account(session)
        repo = TransactionRepository(session)

        tx_a = TransactionRecord(
            id=new_id(), account_id=account_a.id, transaction_type=TransactionKind.NORMAL,
            amount=Money(1000, "JPY"), occurred_at=utc_now(), status=TransactionStatus.ACTIVE,
        )
        tx_b = TransactionRecord(
            id=new_id(), account_id=account_b.id, transaction_type=TransactionKind.NORMAL,
            amount=Money(2000, "JPY"), occurred_at=utc_now(), status=TransactionStatus.ACTIVE,
        )
        repo.add(tx_a)
        repo.add(tx_b)
        session.commit()

        listed = repo.list_by_account(account_a.id)
        assert [r.id for r in listed] == [tx_a.id]
    finally:
        session.close()
