"""
Unit of Work for Personal OS's Repository Layer (Step 6, item 7:
"Transaction Boundary").

A future Service Layer use-case (a 2-leg transfer, a 2-leg bucket
reallocation, or a write plus its audit-log entry) must be able to
perform several repository operations and commit them as a single
atomic transaction, or roll all of them back together on error. No
individual repository method commits on its own -- only UnitOfWork
does. Step 6 does not implement any such use-case itself (no transfer
or reallocation business logic yet); this is purely the transaction
boundary infrastructure a future Service Layer will use.
"""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.orm import Session, sessionmaker

from personal_os.repository.accounts import AccountRepository
from personal_os.repository.audit_logs import AuditLogRepository
from personal_os.repository.bucket_allocations import BucketAllocationRepository
from personal_os.repository.capital_buckets import CapitalBucketRepository
from personal_os.repository.financial_metrics import FinancialMetricRepository
from personal_os.repository.financial_targets import FinancialTargetRepository
from personal_os.repository.monthly_targets import MonthlyTargetRepository
from personal_os.repository.transactions import TransactionRepository


class UnitOfWork:
    """Groups repository operations into a single commit/rollback boundary.

    Usage (by a future Service Layer)::

        with UnitOfWork(session_factory) as uow:
            uow.accounts.add(account_record)
            uow.transactions.add(transaction_record)
            uow.commit()

    If the `with` block exits via an exception -- including one raised
    deliberately after some writes already happened -- every write in
    this Unit of Work is rolled back; nothing partial is committed.
    commit() is always explicit: a clean exit with no commit() call
    still rolls back, so a caller that forgets to commit never gets a
    silent partial success.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self.session: Session | None = None

    def __enter__(self) -> "UnitOfWork":
        self.session = self._session_factory()
        self.accounts = AccountRepository(self.session)
        self.transactions = TransactionRepository(self.session)
        self.capital_buckets = CapitalBucketRepository(self.session)
        self.bucket_allocations = BucketAllocationRepository(self.session)
        self.financial_metrics = FinancialMetricRepository(self.session)
        self.financial_targets = FinancialTargetRepository(self.session)
        self.monthly_targets = MonthlyTargetRepository(self.session)
        self.audit_logs = AuditLogRepository(self.session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self.session is not None
        if exc_type is not None:
            self.session.rollback()
        self.session.close()
        # Returning None (falsy) re-raises any exception -- a Unit of
        # Work never swallows the caller's error.

    def commit(self) -> None:
        """Commit the Unit of Work's transaction.

        If the underlying session.commit() itself raises (e.g. a
        constraint violation deferred to commit time, or any other
        DBAPI error), this rolls the session back immediately -- not
        left to a caller who might catch the exception without also
        rolling back -- and then re-raises the original exception
        unchanged. No failed/half-committed transaction is left
        pending on the session either way.
        """
        assert self.session is not None
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def rollback(self) -> None:
        assert self.session is not None
        self.session.rollback()
