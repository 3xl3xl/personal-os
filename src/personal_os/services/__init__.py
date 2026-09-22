"""Application Service Layer for Personal OS.

Service modules depend only on personal_os.domain and repository
Protocols/abstractions. Persistence implementations stay below this
boundary.
"""

from personal_os.services.finance import (
    NoFinancialDataError,
    TargetNotFoundError,
    available_capital,
    goal_gap,
    net_worth,
    required_monthly_revenue,
    tax_reserved,
)
from personal_os.services.permissions import (
    OperationClass,
    PermissionDecision,
    PermissionDeniedError,
    PermissionResult,
    evaluate_permission,
    require_permission,
)

__all__ = [
    "NoFinancialDataError",
    "TargetNotFoundError",
    "available_capital",
    "goal_gap",
    "net_worth",
    "required_monthly_revenue",
    "tax_reserved",
    "OperationClass",
    "PermissionDecision",
    "PermissionDeniedError",
    "PermissionResult",
    "evaluate_permission",
    "require_permission",
]
