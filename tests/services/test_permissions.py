from __future__ import annotations

import ast
from pathlib import Path

import pytest

from personal_os.services.permissions import (
    OperationClass,
    PermissionDecision,
    PermissionDeniedError,
    evaluate_permission,
    require_permission,
)


def test_read_is_automatic():
    result = evaluate_permission(OperationClass.READ)
    assert result.decision is PermissionDecision.ALLOW
    assert result.may_execute is True


@pytest.mark.parametrize(
    "operation",
    [OperationClass.LOCAL_PERSONAL_DATA_WRITE, OperationClass.EXTERNAL_WRITE],
)
def test_writes_require_explicit_approval(operation):
    result = evaluate_permission(operation)
    assert result.decision is PermissionDecision.REQUIRE_APPROVAL
    assert result.may_execute is False
    with pytest.raises(PermissionDeniedError):
        require_permission(operation)


@pytest.mark.parametrize(
    "operation",
    [OperationClass.LOCAL_PERSONAL_DATA_WRITE, OperationClass.EXTERNAL_WRITE],
)
def test_explicitly_approved_write_may_execute(operation):
    result = require_permission(operation, user_approved=True)
    assert result.decision is PermissionDecision.REQUIRE_APPROVAL
    assert result.approved is True
    assert result.may_execute is True


@pytest.mark.parametrize("approved", [False, True])
def test_financial_execution_is_blocked_even_if_approved(approved):
    result = evaluate_permission(
        OperationClass.FINANCIAL_EXECUTION, user_approved=approved
    )
    assert result.decision is PermissionDecision.BLOCK
    assert result.may_execute is False
    with pytest.raises(PermissionDeniedError):
        require_permission(
            OperationClass.FINANCIAL_EXECUTION, user_approved=approved
        )


def test_policy_has_exactly_four_operation_classes():
    assert {item.value for item in OperationClass} == {
        "READ",
        "LOCAL_PERSONAL_DATA_WRITE",
        "EXTERNAL_WRITE",
        "FINANCIAL_EXECUTION",
    }


def test_permission_service_has_no_persistence_or_adapter_imports():
    path = (
        Path(__file__).parents[2]
        / "src"
        / "personal_os"
        / "services"
        / "permissions.py"
    )
    tree = ast.parse(path.read_text())
    forbidden = ("sqlalchemy", "sqlite3", "personal_os.database", "personal_os.adapters")
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert not any(name.startswith(forbidden) for name in imports), imports


def test_repository_does_not_import_permission_policy():
    root = Path(__file__).parents[2] / "src" / "personal_os" / "repository"
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text())
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        assert not any(name.startswith("personal_os.services.permissions") for name in imports), path
