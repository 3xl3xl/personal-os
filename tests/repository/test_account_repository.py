"""Step 6 -- Account write/read roundtrip."""

from __future__ import annotations

from personal_os.domain.datetime import utc_now
from personal_os.domain.enums import AccountStatus, AccountType
from personal_os.domain.ids import new_id
from personal_os.domain.records import AccountRecord
from personal_os.repository.accounts import AccountRepository


def test_account_write_read_roundtrip(session_factory):
    session = session_factory()
    try:
        repo = AccountRepository(session)
        record = AccountRecord(
            id=new_id(),
            name="Main Checking",
            account_type=AccountType.CASH,
            currency_code="JPY",
            opened_at=utc_now(),
            status=AccountStatus.ACTIVE,
        )

        repo.add(record)
        session.commit()

        got = repo.get(record.id)
        assert got == record
    finally:
        session.close()


def test_get_returns_none_for_unknown_account(session_factory):
    session = session_factory()
    try:
        repo = AccountRepository(session)
        assert repo.get(new_id()) is None
    finally:
        session.close()


def test_list_all_returns_every_written_account(session_factory):
    session = session_factory()
    try:
        repo = AccountRepository(session)
        first = AccountRecord(
            id=new_id(), name="A", account_type=AccountType.CASH,
            currency_code="JPY", opened_at=utc_now(), status=AccountStatus.ACTIVE,
        )
        second = AccountRecord(
            id=new_id(), name="B", account_type=AccountType.INVESTMENT,
            currency_code="USD", opened_at=utc_now(), status=AccountStatus.ACTIVE,
        )
        repo.add(first)
        repo.add(second)
        session.commit()

        listed = repo.list_all()
        assert {r.id for r in listed} == {first.id, second.id}
    finally:
        session.close()
