"""Verifies CapitalBucket role/protected independence and multiple TAX_RESERVE support."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from personal_os.database.schema import Account, Base, CapitalBucket
from personal_os.domain.enums import AccountType, BucketRole


def _engine_with_schema():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def _make_account(session: Session) -> Account:
    account = Account(
        name="Test Cash",
        account_type=AccountType.CASH,
        currency_code="USD",
        opened_at=dt.datetime.now(dt.timezone.utc),
        status="ACTIVE",
    )
    session.add(account)
    session.flush()
    return account


def test_bucket_role_and_is_protected_are_independent() -> None:
    engine = _engine_with_schema()
    with Session(engine) as session:
        account = _make_account(session)

        # TAX_RESERVE with is_protected explicitly False must be schema-valid:
        # bucket_role never implies a default for is_protected.
        bucket = CapitalBucket(
            account_id=account.id,
            name="Tax Reserve (unprotected on purpose, for this test)",
            bucket_role=BucketRole.TAX_RESERVE,
            is_protected=False,
            status="ACTIVE",
            created_at=dt.datetime.now(dt.timezone.utc),
        )
        session.add(bucket)
        session.commit()

        fetched = session.get(CapitalBucket, bucket.id)
        assert fetched is not None
        assert fetched.bucket_role == BucketRole.TAX_RESERVE
        assert fetched.is_protected is False
    engine.dispose()


def test_multiple_tax_reserve_buckets_are_schema_valid() -> None:
    engine = _engine_with_schema()
    with Session(engine) as session:
        account = _make_account(session)

        bucket_a = CapitalBucket(
            account_id=account.id, name="Tax Reserve — Business",
            bucket_role=BucketRole.TAX_RESERVE, is_protected=True,
            status="ACTIVE", created_at=dt.datetime.now(dt.timezone.utc),
        )
        bucket_b = CapitalBucket(
            account_id=account.id, name="Tax Reserve — Personal",
            bucket_role=BucketRole.TAX_RESERVE, is_protected=True,
            status="ACTIVE", created_at=dt.datetime.now(dt.timezone.utc),
        )
        session.add_all([bucket_a, bucket_b])
        session.commit()  # must not raise -- no uniqueness constraint on bucket_role

        count = (
            session.query(CapitalBucket)
            .filter(CapitalBucket.bucket_role == BucketRole.TAX_RESERVE)
            .count()
        )
        assert count == 2
    engine.dispose()


def test_bucket_role_has_no_implicit_default() -> None:
    engine = _engine_with_schema()
    with Session(engine) as session:
        account = _make_account(session)
        bucket = CapitalBucket(
            account_id=account.id,
            name="No role given",
            is_protected=True,
            status="ACTIVE",
            created_at=dt.datetime.now(dt.timezone.utc),
        )
        session.add(bucket)
        raised = False
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raised = True
        assert raised, "bucket_role must be required with no implicit default"
    engine.dispose()


def test_is_protected_has_no_implicit_default() -> None:
    engine = _engine_with_schema()
    with Session(engine) as session:
        account = _make_account(session)
        bucket = CapitalBucket(
            account_id=account.id,
            name="No is_protected given",
            bucket_role=BucketRole.GENERAL,
            status="ACTIVE",
            created_at=dt.datetime.now(dt.timezone.utc),
        )
        session.add(bucket)
        raised = False
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raised = True
        assert raised, "is_protected must be required with no implicit default"
    engine.dispose()
