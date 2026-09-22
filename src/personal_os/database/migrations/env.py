"""
Alembic migration environment for Personal OS.

Source of truth: ADR-002 (Persistence & ORM Strategy). This module
must never hardcode a real database path or secret, and must never
define application schema itself — the single source of table/column
definitions is personal_os.database.schema.Base.metadata, imported
directly below and used as target_metadata.

## Database URL injection (deliberately not hardcoded here)

Two supported injection paths, checked in this order:

1. Programmatic callers (a future Repository/runtime layer, or a
   test) construct an `alembic.config.Config` object and call
   `cfg.set_main_option("sqlalchemy.url", url)` before invoking an
   Alembic `command` (e.g. `command.upgrade(cfg, "head")`). This is
   the primary injection path for anything running inside the
   Personal OS process, and requires no environment variable.
2. Direct `alembic <cmd>` CLI invocations (a human running
   `alembic upgrade head` from a shell, with no programmatic Config)
   instead set the PERSONAL_OS_DATABASE_URL environment variable.

alembic.ini's own `sqlalchemy.url` is intentionally left blank (see
its module comment). If neither injection path above supplies a URL,
migrations refuse to run with a clear error rather than silently
falling back to a guessed or real path. In particular, this module
never references ~/PersonalOS-data/personal_os.db (see SECURITY.md) —
Step 5 only ever runs migrations against temporary SQLite databases.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from personal_os.database.schema import Base

# Alembic Config object, providing access to values within alembic.ini.
config = context.config

# Configure Python logging per alembic.ini's [loggers]/[handlers]/
# [formatters] sections, unless Alembic was invoked without a config
# file (e.g. constructed purely programmatically in a test).
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The single source of schema truth (ADR-002). Migrations are hand-
# authored Alembic operations reviewed against this metadata — they
# never import it to call create_all() (see Step 5 "Migration
# independence": migration revisions must stay self-contained and
# must not import application ORM models).
target_metadata = Base.metadata


def _resolve_database_url() -> str:
    """Resolve the database URL from Config first, then environment.

    Raises RuntimeError rather than defaulting to any path, so a
    misconfigured caller fails loudly instead of silently touching an
    unintended database.
    """
    configured = config.get_main_option("sqlalchemy.url")
    if configured:
        return configured

    env_url = os.environ.get("PERSONAL_OS_DATABASE_URL")
    if env_url:
        return env_url

    raise RuntimeError(
        "No database URL configured for Alembic. Set it programmatically "
        "via Config.set_main_option('sqlalchemy.url', ...) before running "
        "an Alembic command, or set the PERSONAL_OS_DATABASE_URL "
        "environment variable for direct CLI use. Personal OS never "
        "hardcodes a real database path in alembic.ini or env.py."
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL, no live connection)."""
    url = _resolve_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live DBAPI connection)."""
    url = _resolve_database_url()
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
