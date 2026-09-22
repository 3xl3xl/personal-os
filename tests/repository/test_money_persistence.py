"""
Step 6, item 9 -- Money persistence at the Repository boundary.

Verifies, through the Repository (not by inspecting raw SQL), that:
- amount_minor round-trips exactly, including large magnitudes that
  would silently lose precision if the storage were ever a float, and
  including negative amounts (Schema Design: a signed integer, not an
  unsigned one).
- currency_code round-trips exactly and independently of amount_minor
  (two different currencies are never confused with each other).
"""

from __future__ import annotations

from personal_os.domain.datetime import utc_now
from personal_os.domain.enums import AccountStatus, AccountType, TransactionKind, TransactionStatus
from personal_os.domain.ids import new_id
from personal_os.domain.money import Money
from personal_os.domain.records import AccountRecord, TransactionRecord
from personal_os.repository.accounts import AccountRepository
from personal_os.repository.transactions import TransactionRepository


def _make_account(session, currency_code: str) -> AccountRecord:
    record = AccountRecord(
        id=new_id(), name="Test", account_type=AccountType.CASH,
        currency_code=currency_code, opened_at=utc_now(), status=AccountStatus.ACTIVE,
    )
    AccountRepository(session).add(record)
    return record


def test_large_amount_minor_round_trips_exactly_not_as_a_float(session_factory):
    """9,007,199,254,740,993 exceeds 2**53 -- a value an IEEE-754
    double cannot represent exactly. If amount_minor were ever stored
    as a float, this value would silently round to a different
    integer on read.
    """
    session = session_factory()
    try:
        account = _make_account(session, "JPY")
        repo = TransactionRepository(session)
        huge_amount = 9_007_199_254_740_993
        record = TransactionRecord(
            id=new_id(), account_id=account.id, transaction_type=TransactionKind.NORMAL,
            amount=Money(huge_amount, "JPY"), occurred_at=utc_now(), status=TransactionStatus.ACTIVE,
        )
        repo.add(record)
        session.commit()

        got = repo.get(record.id)
        assert got.amount.amount_minor == huge_amount
        assert isinstance(got.amount.amount_minor, int)
    finally:
        session.close()


def test_negative_amount_minor_round_trips_exactly(session_factory):
    session = session_factory()
    try:
        account = _make_account(session, "JPY")
        repo = TransactionRepository(session)
        record = TransactionRecord(
            id=new_id(), account_id=account.id, transaction_type=TransactionKind.NORMAL,
            amount=Money(-42_500, "JPY"), occurred_at=utc_now(), status=TransactionStatus.ACTIVE,
        )
        repo.add(record)
        session.commit()

        got = repo.get(record.id)
        assert got.amount.amount_minor == -42_500
    finally:
        session.close()


def test_currency_code_is_preserved_and_not_confused_between_transactions(session_factory):
    session = session_factory()
    try:
        jpy_account = _make_account(session, "JPY")
        usd_account = _make_account(session, "USD")
        repo = TransactionRepository(session)

        jpy_tx = TransactionRecord(
            id=new_id(), account_id=jpy_account.id, transaction_type=TransactionKind.NORMAL,
            amount=Money(100_000, "JPY"), occurred_at=utc_now(), status=TransactionStatus.ACTIVE,
        )
        usd_tx = TransactionRecord(
            id=new_id(), account_id=usd_account.id, transaction_type=TransactionKind.NORMAL,
            amount=Money(100_000, "USD"), occurred_at=utc_now(), status=TransactionStatus.ACTIVE,
        )
        repo.add(jpy_tx)
        repo.add(usd_tx)
        session.commit()

        assert repo.get(jpy_tx.id).amount.currency_code == "JPY"
        assert repo.get(usd_tx.id).amount.currency_code == "USD"
        assert repo.get(jpy_tx.id).amount == Money(100_000, "JPY")
        assert repo.get(usd_tx.id).amount == Money(100_000, "USD")
    finally:
        session.close()
