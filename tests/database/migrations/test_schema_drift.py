"""
Step 5 -- Schema drift detection (item 6).

After `alembic upgrade head`, the migrated database's actual schema
must match personal_os.database.schema.Base.metadata, using Alembic's
own autogenerate comparison API rather than a shallow table-name
check.

Known limitation, reported rather than silently ignored: Alembic's
compare_metadata does not compare CHECK constraints by default (a
long-standing, documented Alembic/SQLAlchemy limitation -- CHECK
constraint reflection is dialect-specific text with no reliable
cross-backend comparison). CHECK constraint presence is therefore
verified separately, by direct inspection, in
test_schema_structure_matches_step4.py. This module covers what
compare_metadata *does* reliably check: tables, columns, types,
nullability, primary keys, foreign keys, unique constraints, indexes.
"""

from __future__ import annotations

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from personal_os.database.schema import Base


def test_migrated_schema_matches_sqlalchemy_metadata_with_no_drift(alembic_config, temp_sqlite_url):
    command.upgrade(alembic_config, "head")

    engine = create_engine(temp_sqlite_url)
    try:
        with engine.connect() as connection:
            migration_context = MigrationContext.configure(connection)
            diff = compare_metadata(migration_context, Base.metadata)
    finally:
        engine.dispose()

    assert diff == [], (
        "Schema drift detected between the migrated database and "
        "Base.metadata -- the migration is out of sync with the "
        f"SQLAlchemy models it is supposed to mirror: {diff!r}"
    )
