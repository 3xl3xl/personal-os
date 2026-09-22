"""Verifies the full Finance v0.1 schema creates cleanly on an in-memory SQLite engine.

No persistent DB file is created anywhere in this test module or
elsewhere in Step 4 -- every engine here uses the sqlite:///:memory:
URI.
"""

from __future__ import annotations

from sqlalchemy import create_engine, inspect

from personal_os.database.schema import Base


def test_full_schema_creates_on_in_memory_sqlite() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    assert table_names == set(Base.metadata.tables.keys())

    engine.dispose()
