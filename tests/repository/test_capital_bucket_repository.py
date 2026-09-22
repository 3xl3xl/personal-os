"""Step 6 -- CapitalBucket write/read roundtrip."""

from __future__ import annotations

from personal_os.domain.datetime import utc_now
from personal_os.domain.enums import AccountStatus, AccountType, BucketRole, CapitalBucketStatus
from personal_os.domain.ids import new_id
from personal_os.domain.records import AccountRecord, CapitalBucketRecord
from personal_os.repository.accounts import AccountRepository
from personal_os.repository.capital_buckets import CapitalBucketRepository


def _make_account(session) -> AccountRecord:
    repo = AccountRepository(session)
    record = AccountRecord(
        id=new_id(), name="Main", account_type=AccountType.CASH,
        currency_code="JPY", opened_at=utc_now(), status=AccountStatus.ACTIVE,
    )
    repo.add(record)
    return record


def test_capital_bucket_write_read_roundtrip(session_factory):
    session = session_factory()
    try:
        account = _make_account(session)
        repo = CapitalBucketRepository(session)
        record = CapitalBucketRecord(
            id=new_id(),
            account_id=account.id,
            name="Emergency Fund",
            bucket_role=BucketRole.GENERAL,
            is_protected=True,
            status=CapitalBucketStatus.ACTIVE,
            created_at=utc_now(),
        )

        repo.add(record)
        session.commit()

        got = repo.get(record.id)
        assert got == record
    finally:
        session.close()


def test_multiple_tax_reserve_buckets_are_writable_and_listable(session_factory):
    session = session_factory()
    try:
        account = _make_account(session)
        repo = CapitalBucketRepository(session)

        first = CapitalBucketRecord(
            id=new_id(), account_id=account.id, name="Income Tax Reserve",
            bucket_role=BucketRole.TAX_RESERVE, is_protected=True,
            status=CapitalBucketStatus.ACTIVE, created_at=utc_now(),
        )
        second = CapitalBucketRecord(
            id=new_id(), account_id=account.id, name="Resident Tax Reserve",
            bucket_role=BucketRole.TAX_RESERVE, is_protected=True,
            status=CapitalBucketStatus.ACTIVE, created_at=utc_now(),
        )
        repo.add(first)
        repo.add(second)
        session.commit()

        listed = repo.list_by_account(account.id)
        assert {r.id for r in listed} == {first.id, second.id}
        assert all(r.bucket_role == BucketRole.TAX_RESERVE for r in listed)
    finally:
        session.close()
