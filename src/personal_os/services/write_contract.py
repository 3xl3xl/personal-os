"""Approval-gated local fact write; persistence is injected through a Protocol."""
from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Callable
from typing import Protocol

from personal_os.domain.datetime import to_utc, utc_now
from personal_os.domain.enums import TransactionKind, TransactionStatus
from personal_os.domain.records import AuditLogRecord, TransactionRecord
from personal_os.domain.money import CurrencyMismatchError
from personal_os.domain.write_contracts import (
    AddTransactionInput, AddTransactionResult, ApprovalStatus, WriteContext,
    canonical_transaction,
)
from personal_os.repository.protocols import (
    AccountRepositoryProtocol, AuditLogRepositoryProtocol,
    FinancialMetricRepositoryProtocol, TransactionRepositoryProtocol,
)
from personal_os.services.permissions import OperationClass, require_permission


class WriteUnitOfWork(Protocol):
    """Fresh isolated transaction; rollback on exceptional exit, never suppress.

    commit() is explicit and atomic; repository add() must never commit.
    The external composition owns concrete session creation and cleanup.
    """
    accounts: AccountRepositoryProtocol
    transactions: TransactionRepositoryProtocol
    audit_logs: AuditLogRepositoryProtocol
    financial_metrics: FinancialMetricRepositoryProtocol

    def __enter__(self) -> WriteUnitOfWork: ...
    def __exit__(self, exc_type, exc, tb) -> None: ...
    def commit(self) -> None: ...


class WriteReferenceError(ValueError):
    """Missing account/metric or an already-used transaction ID."""


class FinanceWriteContract:
    def __init__(
        self, uow_factory: Callable[[], WriteUnitOfWork], *,
        clock: Callable[[], dt.datetime] = utc_now,
        audit_id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._audit_id_factory = audit_id_factory

    def add_transaction(
        self, request: AddTransactionInput, *, context: WriteContext,
    ) -> AddTransactionResult:
        # Revalidate even model_construct/model_copy instances at the boundary.
        context = WriteContext.model_validate(context.model_dump())
        require_permission(
            OperationClass.LOCAL_PERSONAL_DATA_WRITE,
            user_approved=context.approved,
        )
        request = AddTransactionInput.model_validate({
            name: getattr(request, name) for name in AddTransactionInput.model_fields
        })
        transaction = TransactionRecord(
            id=request.id, account_id=request.account_id,
            transaction_type=TransactionKind.NORMAL, amount=request.amount,
            occurred_at=request.occurred_at, status=TransactionStatus.ACTIVE,
            metric_key=request.metric_key, memo=request.memo,
        )
        audit_id = self._audit_id_factory()
        if not isinstance(audit_id, uuid.UUID):
            raise TypeError("audit ID must be UUID")
        audit = AuditLogRecord(
            id=audit_id, actor=context.actor, action="add_transaction",
            affected_entity_type="transaction", affected_entity_id=transaction.id,
            old_value=None, new_value=canonical_transaction(transaction),
            reason=context.reason,
            approval_status=ApprovalStatus.EXPLICITLY_APPROVED.value,
            occurred_at=to_utc(self._clock()),
        )
        result = AddTransactionResult(transaction=transaction, audit_id=audit.id)
        with self._uow_factory() as uow:
            account = uow.accounts.get(transaction.account_id)
            if account is None:
                raise WriteReferenceError("account not found")
            if account.currency_code != transaction.amount.currency_code:
                raise CurrencyMismatchError("transaction currency must match account currency")
            if uow.transactions.get(transaction.id) is not None:
                raise WriteReferenceError("transaction ID already exists")
            if transaction.metric_key is not None and uow.financial_metrics.get_by_key(transaction.metric_key) is None:
                raise WriteReferenceError("financial metric not found")
            uow.transactions.add(transaction)
            uow.audit_logs.add(audit)
            uow.commit()
        return result
