"""Central v0.1 permission boundary.

All adapters must ask this Service-layer policy before performing an operation.
The policy classifies capability, not caller identity. Approval is explicit
input; this module never infers approval from conversational context.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OperationClass(StrEnum):
    READ = "READ"
    LOCAL_PERSONAL_DATA_WRITE = "LOCAL_PERSONAL_DATA_WRITE"
    EXTERNAL_WRITE = "EXTERNAL_WRITE"
    FINANCIAL_EXECUTION = "FINANCIAL_EXECUTION"


class PermissionDecision(StrEnum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    BLOCK = "BLOCK"


class PermissionDeniedError(PermissionError):
    """Raised when an operation is not authorized to execute."""


@dataclass(frozen=True, slots=True)
class PermissionResult:
    operation_class: OperationClass
    decision: PermissionDecision
    approved: bool
    may_execute: bool


def evaluate_permission(
    operation_class: OperationClass,
    *,
    user_approved: bool = False,
) -> PermissionResult:
    """Evaluate the fixed v0.1 permission policy without side effects."""
    if operation_class is OperationClass.READ:
        return PermissionResult(operation_class, PermissionDecision.ALLOW, user_approved, True)

    if operation_class in {
        OperationClass.LOCAL_PERSONAL_DATA_WRITE,
        OperationClass.EXTERNAL_WRITE,
    }:
        return PermissionResult(
            operation_class,
            PermissionDecision.REQUIRE_APPROVAL,
            user_approved,
            user_approved,
        )

    if operation_class is OperationClass.FINANCIAL_EXECUTION:
        return PermissionResult(operation_class, PermissionDecision.BLOCK, user_approved, False)

    raise ValueError(f"unsupported operation class: {operation_class!r}")


def require_permission(
    operation_class: OperationClass,
    *,
    user_approved: bool = False,
) -> PermissionResult:
    """Return an executable decision or raise; blocked stays blocked even if approved."""
    result = evaluate_permission(operation_class, user_approved=user_approved)
    if result.may_execute:
        return result
    if result.decision is PermissionDecision.BLOCK:
        raise PermissionDeniedError(
            "financial execution is blocked in Personal OS v0.1"
        )
    raise PermissionDeniedError(
        f"{operation_class.value} requires explicit user approval"
    )
