"""
Finance v0.1 SQLAlchemy persistence models (personal_os.database.schema).

Source of truth: ADR-002 (Persistence & ORM Strategy), ADR-005
(Money), ADR-006 (Datetime), ADR-007 (IDs), and Finance v0.1 Schema
Design v0.3.

This package (together with the future Repository Layer) is the only
place SQLAlchemy is imported. personal_os.domain must never import
this package or sqlalchemy directly (ADR-002's layering boundary).

Importing this module registers every table onto Base.metadata, so
that Base.metadata.create_all(engine) creates the full Finance v0.1
schema in one call. No Alembic migration exists yet (Step 5).
"""

from __future__ import annotations

from personal_os.database.schema.accounts import Account
from personal_os.database.schema.audit_logs import AuditLog
from personal_os.database.schema.base import Base
from personal_os.database.schema.bucket_allocations import BucketAllocation
from personal_os.database.schema.capital_buckets import CapitalBucket
from personal_os.database.schema.financial_metrics import FinancialMetric
from personal_os.database.schema.financial_targets import FinancialTarget
from personal_os.database.schema.monthly_targets import MonthlyTarget
from personal_os.database.schema.transactions import Transaction

__all__ = [
    "Base",
    "Account",
    "Transaction",
    "CapitalBucket",
    "BucketAllocation",
    "FinancialMetric",
    "FinancialTarget",
    "MonthlyTarget",
    "AuditLog",
]
