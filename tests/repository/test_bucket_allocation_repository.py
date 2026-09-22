"""Step 6 -- BucketAllocation write/read roundtrip."""

from __future__ import annotations

from personal_os.domain.datetime import utc_now
from personal_os.domain.enums import (
    AccountStatus,
    AccountType,
    BucketRole,
    CapitalBucketStatus,
    EntryType,
    TransactionKind,
    TransactionStatus,
)
from personal_os.domain.ids import new_id
from personal_os.domain.money import Money
from personal_os.domain.records import (
    AccountRecord,
    BucketAllocationRecord,
    CapitalBucketRecord,
    TransactionRecord,
)
from personal_os.repository.accounts import AccountRepository
from personal_os.repository.bucket_allocations import BucketAllocationRepository
from personal_os.repository.capital_buckets import CapitalBucketRepository
from personal_os.repository.transactions import TransactionRepository


def test_bucket_allocation_write_read_roundtrip(session_factory):
    session = session_factory()
    try:
        account = AccountRecord(
            id=new_id(), name="Main", account_type=AccountType.CASH,
            currency_code="JPY", opened_at=utc_now(), status=AccountStatus.ACTIVE,
        )
        AccountRepository(session).add(account)

        bucket = CapitalBucketRecord(
            id=new_id(), account_id=account.id, name="Operating Cash",
            bucket_role=BucketRole.GENERAL, is_protected=False,
            status=CapitalBucketStatus.ACTIVE, created_at=utc_now(),
        )
        CapitalBucketRepository(session).add(bucket)

        transaction = TransactionRecord(
            id=new_id(), account_id=account.id, transaction_type=TransactionKind.NORMAL,
            amount=Money(50_000, "JPY"), occurred_at=utc_now(), status=TransactionStatus.ACTIVE,
        )
        TransactionRepository(session).add(transaction)

        repo = BucketAllocationRepository(session)
        allocation = BucketAllocationRecord(
            id=new_id(),
            bucket_id=bucket.id,
            account_id=account.id,
            amount=Money(50_000, "JPY"),
            entry_type=EntryType.CASH_LINKED,
            created_at=utc_now(),
            originating_transaction_id=transaction.id,
        )
        repo.add(allocation)
        session.commit()

        listed = repo.list_by_bucket(bucket.id)
        assert listed == [allocation]
    finally:
        session.close()
