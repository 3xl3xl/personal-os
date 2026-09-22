"""
SQLAlchemy declarative base for Personal OS v0.1 persistence models.

Source of truth: ADR-002 (Persistence & ORM Strategy). SQLAlchemy is
confined to this package (personal_os.database.schema) and the future
Repository Layer. personal_os.domain must never import SQLAlchemy —
the dependency direction is one-way: database.schema may import
domain; domain may never import database.schema or sqlalchemy.

## UUID storage representation (ADR-007)

Every primary/foreign key in this schema is typed `uuid.UUID` in
Python and mapped via SQLAlchemy's generic `Uuid` type
(`Uuid(as_uuid=True)`), configured once here via `type_annotation_map`.
SQLAlchemy's dialect layer — not Personal OS code — decides the
on-disk representation per database: PostgreSQL gets its native UUID
column type, and SQLite gets a 32-character hex string. This matches
ADR-007's own stated rationale ("natively supported... in PostgreSQL
and easily stored as TEXT in SQLite"). Application and Repository
code always works with plain Python `uuid.UUID` objects; nothing in
Personal OS depends on which concrete on-disk representation a given
dialect happens to choose. This is the generic SQLAlchemy cross-
dialect UUID type, not a database-specific type — there is no lock-in
to either engine's native UUID feature.

## Datetime storage representation (ADR-006)

Every datetime column is mapped via `DateTime(timezone=True)`,
configured once here via `type_annotation_map`. This asks the DB
driver to preserve timezone-awareness on write/read, but it is not,
by itself, a guarantee that every stored value is UTC — SQLite in
particular does not enforce or normalize timezone offsets at the
storage layer. The guarantee that a value is aware and UTC-
canonicalized before it is ever persisted is an application/domain-
boundary responsibility (see personal_os.domain.datetime.to_utc /
require_aware), to be enforced by the future Repository Layer. This
module only declares that a column carries timezone-aware datetimes;
it does not and cannot enforce UTC canonicalization at the SQL level.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, Uuid
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all Personal OS v0.1 persistence models."""

    type_annotation_map = {
        uuid.UUID: Uuid(as_uuid=True),
        dt.datetime: DateTime(timezone=True),
    }
