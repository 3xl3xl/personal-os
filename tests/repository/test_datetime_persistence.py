"""
Step 6, item 9 -- empirical investigation of SQLite/SQLAlchemy
DateTime(timezone=True) round-trip behavior, and verification that the
Repository-boundary adapter (personal_os.repository._datetime_adapter)
restores ADR-006 semantics (aware, UTC-canonical) despite it.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from personal_os.database.schema import Account
from personal_os.domain.datetime import NaiveDatetimeError, to_timezone
from personal_os.domain.enums import AccountStatus, AccountType
from personal_os.domain.ids import new_id
from personal_os.domain.records import AccountRecord
from personal_os.repository._datetime_adapter import from_storage, to_storage
from personal_os.repository.accounts import AccountRepository


def test_raw_sqlalchemy_sqlite_datetime_column_drops_tzinfo_on_read(session_factory):
    """Empirical baseline, bypassing the Repository adapter entirely:
    write a UTC-aware datetime straight through the ORM, and observe
    that reading it back on a fresh Session produces a naive
    datetime.datetime (tzinfo=None). This is the gap
    _datetime_adapter.py exists to close.
    """
    session: Session = session_factory()
    try:
        aware_utc = dt.datetime(2026, 6, 15, 9, 30, 0, 123456, tzinfo=dt.timezone.utc)
        row = Account(
            id=new_id(), name="Raw Test", account_type=AccountType.CASH,
            currency_code="JPY", opened_at=aware_utc, status=AccountStatus.ACTIVE,
        )
        session.add(row)
        session.commit()
        session.expire_all()  # force a fresh SELECT, not the identity map

        reread = session.get(Account, row.id)
        assert reread.opened_at.tzinfo is None, (
            "expected SQLite's DateTime(timezone=True) shim to drop tzinfo on "
            "read -- if this now fails, SQLAlchemy/pysqlite behavior has "
            "changed and _datetime_adapter.py's docstring needs updating"
        )
        assert reread.opened_at.replace(tzinfo=dt.timezone.utc) == aware_utc
    finally:
        session.close()


def test_raw_sqlalchemy_sqlite_datetime_column_does_not_convert_to_utc_on_write(session_factory):
    """Empirical baseline: a non-UTC aware datetime is stored with its
    own wall-clock numbers, unconverted -- proving why the Repository
    Layer must call to_utc() itself before writing (this module's
    to_storage()), rather than relying on the column type to convert.
    """
    session: Session = session_factory()
    try:
        jst_wall_clock = dt.datetime(2026, 6, 15, 18, 30, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
        row = Account(
            id=new_id(), name="Raw JST Test", account_type=AccountType.CASH,
            currency_code="JPY", opened_at=jst_wall_clock, status=AccountStatus.ACTIVE,
        )
        session.add(row)
        session.commit()
        session.expire_all()

        reread = session.get(Account, row.id)
        # The column stored the JST wall-clock numbers verbatim, not the
        # UTC-equivalent instant -- reading it back naive and comparing
        # wall-clock fields (not astimezone-normalized) proves no UTC
        # conversion happened at the column-type level.
        assert reread.opened_at == jst_wall_clock.replace(tzinfo=None)
    finally:
        session.close()


def test_datetime_adapter_to_storage_canonicalizes_non_utc_input_to_utc():
    jst = dt.datetime(2026, 6, 15, 18, 30, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    result = to_storage(jst)
    assert result.tzinfo == dt.timezone.utc
    assert result == jst  # same instant, UTC representation


def test_datetime_adapter_to_storage_rejects_naive_input():
    naive = dt.datetime(2026, 6, 15, 18, 30, 0)
    with pytest.raises(NaiveDatetimeError):
        to_storage(naive)


def test_datetime_adapter_from_storage_reattaches_utc_on_naive_value():
    naive = dt.datetime(2026, 6, 15, 9, 30, 0)
    restored = from_storage(naive)
    assert restored.tzinfo == dt.timezone.utc
    assert restored == naive.replace(tzinfo=dt.timezone.utc)


def test_repository_boundary_round_trip_preserves_instant_and_is_utc_aware(session_factory):
    """The end-to-end guarantee: writing a non-UTC aware datetime
    through the Repository and reading it back yields a UTC-aware
    datetime representing the identical instant -- despite the raw
    column-level gaps demonstrated above.
    """
    session = session_factory()
    try:
        jst = dt.datetime(2026, 6, 15, 18, 30, 0, 500000, tzinfo=ZoneInfo("Asia/Tokyo"))
        repo = AccountRepository(session)
        record = AccountRecord(
            id=new_id(), name="Repo Boundary Test", account_type=AccountType.CASH,
            currency_code="JPY", opened_at=jst, status=AccountStatus.ACTIVE,
        )
        repo.add(record)
        session.commit()
        session.expire_all()

        got = repo.get(record.id)
        assert got.opened_at.tzinfo == dt.timezone.utc
        assert got.opened_at == jst  # same instant as the original JST input

        # Round-tripping the already-UTC value back to JST recovers the
        # original wall-clock time, using the existing domain helper.
        assert to_timezone(got.opened_at, ZoneInfo("Asia/Tokyo")) == jst
    finally:
        session.close()
