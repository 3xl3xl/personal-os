"""Verifies ADR-002's layering boundary: personal_os.domain never imports SQLAlchemy."""

from __future__ import annotations

import ast
from pathlib import Path

import personal_os.domain as domain_package


def _iter_domain_source_files():
    domain_dir = Path(domain_package.__file__).parent
    yield from domain_dir.glob("*.py")


def test_domain_package_source_does_not_import_sqlalchemy() -> None:
    checked_any = False
    for path in _iter_domain_source_files():
        checked_any = True
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("sqlalchemy"), (
                        f"{path.name} imports sqlalchemy directly: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith("sqlalchemy"), (
                    f"{path.name} imports from sqlalchemy: {module}"
                )
    assert checked_any, "expected to find at least one file under personal_os/domain"
