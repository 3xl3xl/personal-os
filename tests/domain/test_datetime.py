"""Tests for personal_os.domain.datetime — see ADR-006."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from personal_os.domain.datetime import (
    NaiveDatetimeError,
    require_aware,
    to_timezone,
    to_utc,
    utc_now,
)


def test_module_does_not_shadow_stdlib_datetime() -> None:
    """
    This module is named datetime.py. Verify that importing the stdlib
    `datetime` module elsewhere in the codebase still resolves to the
    real standard library, not to this module (the same shadowing
    concern raised for the MCP SDK namespace in Step 1).
    """
    import datetime as stdlib_datetime

    assert stdlib_datetime.datetime is dt.datetime
    assert hasattr(stdlib_datetime, "timezone")


def test_utc_now_is_aware_and_utc() -> None:
    now = utc_now()
    assert now.tzinfo is not None
    assert now.utcoffset() == dt.timedelta(0)


def test_aware_utc_datetime_accepted() -> None:
    value = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    assert require_aware(value) is value
    assert to_utc(value) == value


def test_non_utc_aware_datetime_is_canonicalized_to_utc() -> None:
    tokyo = ZoneInfo("Asia/Tokyo")
    value = dt.datetime(2026, 1, 1, 9, 0, tzinfo=tokyo)  # JST, UTC+9
    canonical = to_utc(value)
    assert canonical.tzinfo == dt.timezone.utc
    assert canonical == dt.datetime(2026, 1, 1, 0, 0, tzinfo=dt.timezone.utc)


def test_naive_datetime_rejected() -> None:
    naive = dt.datetime(2026, 1, 1)
    with pytest.raises(NaiveDatetimeError):
        require_aware(naive)
    with pytest.raises(NaiveDatetimeError):
        to_utc(naive)


def test_explicit_timezone_conversion() -> None:
    utc_value = dt.datetime(2026, 1, 1, 0, 0, tzinfo=dt.timezone.utc)
    tokyo = ZoneInfo("Asia/Tokyo")
    converted = to_timezone(utc_value, tokyo)
    assert converted == dt.datetime(2026, 1, 1, 9, 0, tzinfo=tokyo)
    assert converted.tzinfo is not None


def test_to_timezone_rejects_naive_input() -> None:
    naive = dt.datetime(2026, 1, 1)
    with pytest.raises(NaiveDatetimeError):
        to_timezone(naive, ZoneInfo("Asia/Tokyo"))
