"""
Step 5 -- Alembic configuration sanity checks.

These verify the Alembic setup itself (no hardcoded database URL or
Private Runtime Data Store path *in actual configuration/logic*,
exactly one migration head, a clear failure when no URL is injected
at all) -- not migration content, which is covered by the other
modules in this package.

Note: alembic.ini's and env.py's own comments/docstrings *do*
legitimately mention "~/PersonalOS-data/personal_os.db" and
"PersonalOS-data" -- as prose explaining *why* no real path is
configured there (see SECURITY.md). That is intentional transparency,
not a defect. What must never happen is that string being used as an
actual configuration value or hardcoded fallback in the executable
logic, which is what the tests below actually check (by stripping
comments for the ini file, and by inspecting only the
_resolve_database_url() function body -- not the module docstring --
for env.py).
"""

from __future__ import annotations

import ast
import configparser
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_ini_exists_at_repo_root(repo_root):
    assert (repo_root / "alembic.ini").is_file()


def test_alembic_ini_has_no_hardcoded_database_url(alembic_ini_path):
    parser = configparser.ConfigParser()
    parser.read(alembic_ini_path)
    url = parser.get("alembic", "sqlalchemy.url", fallback="")
    assert url.strip() == "", f"alembic.ini must not hardcode a database URL; got: {url!r}"


def test_alembic_ini_config_values_have_no_private_runtime_data_store_reference(alembic_ini_path):
    """Checks non-comment lines only -- explanatory comments may mention
    the Private Runtime Data Store path; actual config values must not.
    """
    lines = alembic_ini_path.read_text().splitlines()
    config_lines = [line for line in lines if not line.strip().startswith("#")]
    config_text = "\n".join(config_lines)
    assert "PersonalOS-data" not in config_text
    assert "personal_os.db" not in config_text


def test_resolve_database_url_function_has_no_hardcoded_private_data_path(migrations_dir):
    """Checks only the _resolve_database_url() function body -- not the
    module docstring, which legitimately explains the policy in prose.
    """
    env_py_path = migrations_dir / "env.py"
    source = env_py_path.read_text()
    tree = ast.parse(source, filename=str(env_py_path))
    target = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_resolve_database_url"
    )
    segment = ast.get_source_segment(source, target)
    assert segment is not None
    assert "PersonalOS-data" not in segment
    assert "personal_os.db" not in segment


def test_alembic_config_loads_and_finds_script_directory(alembic_config, migrations_dir):
    script_dir = ScriptDirectory.from_config(alembic_config)
    assert Path(script_dir.dir).resolve() == migrations_dir.resolve()


def test_exactly_one_migration_head_exists(alembic_config):
    script_dir = ScriptDirectory.from_config(alembic_config)
    heads = script_dir.get_heads()
    assert len(heads) == 1, (
        "Expected exactly one Alembic head (a single linear initial "
        f"migration); found: {heads}"
    )


def test_running_migration_without_any_url_configured_raises_clear_error(
    alembic_ini_path, migrations_dir, monkeypatch
):
    """Neither PERSONAL_OS_DATABASE_URL nor a programmatic sqlalchemy.url."""
    monkeypatch.delenv("PERSONAL_OS_DATABASE_URL", raising=False)
    cfg = Config(str(alembic_ini_path))
    cfg.set_main_option("script_location", str(migrations_dir))
    # sqlalchemy.url deliberately left unset on this Config too.

    with pytest.raises(Exception) as exc_info:  # noqa: PT011 - Alembic wraps env.py errors
        command.upgrade(cfg, "head")
    assert "No database URL configured" in str(exc_info.value)
