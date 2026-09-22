"""
Repository Layer public API (Step 6).

Source of truth: ARCHITECTURE.md Sec.1 ("the only architectural layer
that knows the persistence implementation") and this Step's
requirements. Everything importable from this package is either:
- runtime infrastructure (engine/session factory, UnitOfWork), or
- a repository class or Protocol whose public surface accepts/returns
  only personal_os.domain.records.* DTOs -- never a SQLAlchemy ORM
  instance (see each repository module's own docstring).

personal_os.services (and anything above it) is expected to import
from here and from personal_os.domain only -- never sqlalchemy
directly, and never personal_os.database.schema directly. Step 6 does
not implement personal_os.services itself.
"""

from __future__ import annotations

from personal_os.repository.accounts import AccountRepository
from personal_os.repository.audit_logs import AuditLogRepository
from personal_os.repository.bucket_allocations import BucketAllocationRepository
from personal_os.repository.capital_buckets import CapitalBucketRepository
from personal_os.repository.engine import create_session_factory, create_sqlite_engine
from personal_os.repository.financial_metrics import FinancialMetricRepository
from personal_os.repository.financial_targets import FinancialTargetRepository
from personal_os.repository.monthly_targets import MonthlyTargetRepository
from personal_os.repository.transactions import TransactionRepository
from personal_os.repository.unit_of_work import UnitOfWork

__all__ = [
    "AccountRepository",
    "AuditLogRepository",
    "BucketAllocationRepository",
    "CapitalBucketRepository",
    "FinancialMetricRepository",
    "FinancialTargetRepository",
    "MonthlyTargetRepository",
    "TransactionRepository",
    "UnitOfWork",
    "create_session_factory",
    "create_sqlite_engine",
]
