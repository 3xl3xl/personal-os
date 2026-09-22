"""
Step 6, item 12 -- import-dependency architecture check.

Expected dependency directions:
    domain            -> no sqlalchemy import (already verified by
                          tests/database/schema/test_domain_boundary.py,
                          which globs personal_os/domain/*.py and so
                          automatically covers the new records.py too
                          -- not duplicated here)
    database/schema   -> may depend on domain
    repository        -> may depend on sqlalchemy/schema
    services          -> repository abstraction/domain only, no
                          sqlalchemy import (personal_os.services is
                          not implemented in Step 6; this is a
                          forward-looking guard for whenever it is)
"""

from __future__ import annotations

import ast
from pathlib import Path

import personal_os.repository.protocols as protocols_module
import personal_os.services as services_package


def _iter_py_files(package):
    package_dir = Path(package.__file__).parent
    yield from package_dir.rglob("*.py")


def test_services_package_source_does_not_import_sqlalchemy():
    checked_any = False
    for path in _iter_py_files(services_package):
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
    assert checked_any, "expected to find at least personal_os/services/__init__.py"


def test_services_package_source_does_not_import_database_schema_directly():
    for path in _iter_py_files(services_package):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith("personal_os.database.schema"), (
                    f"{path.name} imports personal_os.database.schema directly: "
                    f"{module} -- services must depend on the Repository "
                    "abstraction, never on ORM models directly"
                )


def test_repository_protocols_reference_only_domain_records_not_orm_models():
    tree = ast.parse(Path(protocols_module.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith("personal_os.database.schema"), (
                f"protocols.py imports {module}; Service-Layer-facing "
                "protocols must reference personal_os.domain.records only"
            )
            assert not module.startswith("sqlalchemy"), (
                f"protocols.py imports {module}; Protocol interfaces must not "
                "depend on sqlalchemy"
            )
