"""
Step 5 -- Migration independence (item 7).

Migration revision files must be self-contained Alembic operations:
they must never import application ORM models
(personal_os.database.schema or any submodule) and must never call
metadata.create_all(). A migration whose meaning depends on importing
the current application model would silently change what an old,
already-applied migration produces the moment that model is edited
later -- breaking the append-only, reviewable meaning a migration
script is supposed to have (ADR-002).
"""

from __future__ import annotations

import ast
from pathlib import Path


def _migration_files(migrations_dir: Path) -> list[Path]:
    versions_dir = migrations_dir / "versions"
    return sorted(p for p in versions_dir.glob("*.py") if p.name != "__init__.py")


def test_at_least_one_migration_file_exists(migrations_dir):
    assert _migration_files(migrations_dir), "Expected at least one migration under versions/"


def test_migration_files_do_not_import_application_schema_package(migrations_dir):
    for path in _migration_files(migrations_dir):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("personal_os"), (
                        f"{path.name} imports {alias.name}; migrations must be self-contained"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith("personal_os"), (
                    f"{path.name} imports from {module}; migrations must be self-contained"
                )


def test_migration_files_never_call_create_all(migrations_dir):
    for path in _migration_files(migrations_dir):
        text = path.read_text()
        assert "create_all" not in text, (
            f"{path.name} must not call metadata.create_all(); use explicit "
            "op.create_table()/op.drop_table() operations instead"
        )


def test_migration_files_use_op_create_table_directly(migrations_dir):
    for path in _migration_files(migrations_dir):
        tree = ast.parse(path.read_text(), filename=str(path))
        called_attrs = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert "create_table" in called_attrs, f"{path.name}: expected explicit op.create_table() calls"


def test_no_tax_rule_table_introduced_by_migration(migrations_dir):
    for path in _migration_files(migrations_dir):
        text_lower = path.read_text().lower()
        assert "tax_rule" not in text_lower, (
            f"{path.name}: TaxRule tables are explicitly out of scope for Step 5 "
            "(deferred per Step 4 Decision 5)"
        )
