"""
Repository interfaces (Protocols) for Personal OS's Service Layer
(Step 6, item 5: "Repository Interfaces").

A future Service Layer is expected to depend on these Protocols --
not on the concrete SQLAlchemy-backed repository classes -- so that
personal_os.services never needs to import sqlalchemy, even indirectly
through a type hint, and so that a future Service Layer's own tests
can substitute a fake/in-memory implementation without touching SQLite
at all.

These are intentionally NOT a generic BaseRepository / CRUD
abstraction. Each Protocol lists only the operations Finance v0.1
actually needs for that entity right now -- see each concrete
repository module's own docstring for why an append-only entity has no
update/delete method.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from personal_os.domain.enums import ExternalSource
from personal_os.domain.records import (
    AccountRecord,
    AuditLogRecord,
    BucketAllocationRecord,
    CapitalBucketRecord,
    ExternalTransactionLinkRecord,
    FinancialMetricRecord,
    FinancialTargetRecord,
    MonthlyTargetRecord,
    TransactionRecord,
)


class AccountRepositoryProtocol(Protocol):
    def add(self, record: AccountRecord) -> None: ...
    def get(self, account_id: uuid.UUID) -> AccountRecord | None: ...
    def list_all(self) -> list[AccountRecord]: ...


class TransactionRepositoryProtocol(Protocol):
    def add(self, record: TransactionRecord) -> None: ...
    def get(self, transaction_id: uuid.UUID) -> TransactionRecord | None: ...
    def list_by_account(self, account_id: uuid.UUID) -> list[TransactionRecord]: ...


class CapitalBucketRepositoryProtocol(Protocol):
    def add(self, record: CapitalBucketRecord) -> None: ...
    def get(self, bucket_id: uuid.UUID) -> CapitalBucketRecord | None: ...
    def list_by_account(self, account_id: uuid.UUID) -> list[CapitalBucketRecord]: ...


class BucketAllocationRepositoryProtocol(Protocol):
    def add(self, record: BucketAllocationRecord) -> None: ...
    def list_by_bucket(self, bucket_id: uuid.UUID) -> list[BucketAllocationRecord]: ...


class FinancialMetricRepositoryProtocol(Protocol):
    def add(self, record: FinancialMetricRecord) -> None: ...
    def get_by_key(self, key: str) -> FinancialMetricRecord | None: ...


class FinancialTargetRepositoryProtocol(Protocol):
    def add(self, record: FinancialTargetRecord) -> None: ...
    def list_by_metric(self, metric_key: str) -> list[FinancialTargetRecord]: ...


class MonthlyTargetRepositoryProtocol(Protocol):
    def add(self, record: MonthlyTargetRecord) -> None: ...
    def list_by_metric_year_month(
        self, metric_key: str, year: int, month: int
    ) -> list[MonthlyTargetRecord]: ...


class AuditLogRepositoryProtocol(Protocol):
    def add(self, record: AuditLogRecord) -> None: ...
    def list_all(self) -> list[AuditLogRecord]: ...


class ExternalTransactionLinkRepositoryProtocol(Protocol):
    def add(self, record: ExternalTransactionLinkRecord) -> None: ...
    def find(
        self,
        *,
        source: ExternalSource,
        external_office_id: str,
        external_account_id: str,
        external_transaction_id: str,
    ) -> ExternalTransactionLinkRecord | None: ...
