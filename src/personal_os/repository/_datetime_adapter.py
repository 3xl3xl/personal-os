"""
Repository-boundary datetime adapter (Step 6, item 9).

Empirically verified in tests/repository/test_datetime_persistence.py:
SQLAlchemy's DateTime(timezone=True) column type, on SQLite, silently
drops tzinfo on read. pysqlite's DATETIME shim formats whatever
wall-clock numbers the given datetime object carries into a string
with NO offset marker, and does NOT convert to UTC on write -- it
literally writes the wall-clock value of the datetime it is given,
verbatim, whatever timezone that datetime happened to be in. Reading
that string back produces a naive datetime.datetime (tzinfo=None)
with those same wall-clock numbers.

Two consequences, both handled here:

1. Every datetime written through the Repository Layer is first
   canonicalized to UTC via personal_os.domain.datetime.to_utc().
   Skipping this would silently store the wrong wall-clock value (no
   offset is recorded) for any caller that passed a non-UTC aware
   datetime -- there would be no way to recover the original instant.
2. Every datetime read back from SQLite is naive but is known to hold
   true UTC wall-clock numbers (guaranteed by step 1 above), so it is
   both safe and necessary -- per ADR-006's "aware datetime only"
   rule -- to re-attach UTC tzinfo here, at the Repository boundary,
   rather than let a naive datetime leak into a domain record.

This is not a change to database.schema: the column type declared in
Step 4 (DateTime(timezone=True)) is unchanged, and its own docstring
already flagged that UTC-canonicalization is an application-layer
responsibility the column type cannot itself enforce. This module is
that application-layer responsibility, confined to the Repository
Layer as Step 6 instructs -- not a Step 4/5 schema change.
"""

from __future__ import annotations

import datetime as dt

from personal_os.domain.datetime import to_utc


def to_storage(value: dt.datetime) -> dt.datetime:
    """Canonicalize an aware datetime to UTC before handing it to the ORM.

    Raises NaiveDatetimeError (via to_utc -> require_aware) if `value`
    is naive -- the Repository Layer never accepts naive datetimes.
    """
    return to_utc(value)


def from_storage(value: dt.datetime) -> dt.datetime:
    """Restore UTC-awareness on a datetime read back from SQLite.

    Personal OS only ever writes UTC-canonicalized values (via
    to_storage()), so a naive value read back is re-attached as UTC,
    never guessed as some other offset. A value that already carries
    tzinfo (e.g. a future non-SQLite backend that preserves it) is
    left alone rather than blindly overwritten.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value
