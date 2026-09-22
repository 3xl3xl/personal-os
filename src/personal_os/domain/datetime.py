"""
Datetime domain primitives for Personal OS v0.1.

Source of truth: ADR-006 (Date/Time & Jurisdiction Handling).

Rules enforced here:
- All datetimes handled by Personal OS Core must be timezone-aware.
  Naive (timezone-unaware) datetimes are rejected outright — there is
  no implicit "assume UTC" or "assume local timezone" fallback.
- UTC is the canonical representation for storage and comparison.
- Local-timezone conversion is always explicit: callers must supply a
  `zoneinfo.ZoneInfo`. Personal OS Core never reads or assumes the
  host machine's local timezone.

Note on this module's name: because Python 3 uses absolute imports by
default, `import datetime` from anywhere in personal_os (including
from within this file) still resolves to the standard library module,
never to this one. This is verified by an explicit sanity-import test
in tests/domain/test_datetime.py, following the same shadowing concern
raised (and resolved via src-layout + personal_os.adapters.mcp) for
the MCP SDK namespace during Step 1.
"""

from __future__ import annotations

import datetime as _dt
from zoneinfo import ZoneInfo


class NaiveDatetimeError(ValueError):
    """Raised when a naive (timezone-less) datetime is supplied where an aware one is required."""


def utc_now() -> _dt.datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return _dt.datetime.now(_dt.timezone.utc)


def require_aware(value: _dt.datetime) -> _dt.datetime:
    """
    Validate that `value` is timezone-aware and return it unchanged.

    Raises NaiveDatetimeError if `value` is naive. Does not convert or
    canonicalize the timezone — use to_utc() for that.
    """
    if not isinstance(value, _dt.datetime):
        raise TypeError(f"expected datetime.datetime, got {type(value).__name__}: {value!r}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise NaiveDatetimeError(f"naive datetime is not allowed: {value!r}")
    return value


def to_utc(value: _dt.datetime) -> _dt.datetime:
    """
    Canonicalize an aware datetime to UTC.

    Raises NaiveDatetimeError if `value` is naive — the caller must
    resolve the timezone explicitly (e.g. via to_timezone with a known
    ZoneInfo) before a value can be canonicalized to UTC.
    """
    require_aware(value)
    return value.astimezone(_dt.timezone.utc)


def to_timezone(value: _dt.datetime, tz: ZoneInfo) -> _dt.datetime:
    """
    Convert an aware datetime to an explicitly supplied timezone.

    `tz` must be provided by the caller as a zoneinfo.ZoneInfo —
    Personal OS Core never infers the local/system timezone
    implicitly. Raises NaiveDatetimeError if `value` is naive.
    """
    require_aware(value)
    if not isinstance(tz, ZoneInfo):
        raise TypeError(f"expected zoneinfo.ZoneInfo, got {type(tz).__name__}: {tz!r}")
    return value.astimezone(tz)
