"""Approval-gated OPENING_BALANCE transaction write; persistence injected via Protocol.

Deliberately its own small contract, following the same additive-module
pattern as services/account_write_contract.py: personal_os.services.write_contract
(the NORMAL transaction write, Step 19/20) and its tests are left completely
unmodified. See ADR-012 (which explicitly scoped "opening-balance bootstrap"
out of that contract) and ADR-018 (this contract's own decision).
"""
from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Callable
from typing import Protocol

from personal_os.domain.datetime import to_utc, utc_now
from personal_os.domain.enums import TransactionKind, TransactionStatus
from personal_os.domain.money import CurrencyMismatchError
from personal_os.domain.opening_balance_write_contracts import (
    AddOpeningBalanceInput, AddOpeningBalanceResult,
)
from personal_os.domain.records import AuditLogRecord, TransactionRecord
from personal_os.domain.write_contracts import ApprovalStatus, WriteContext, canonical_transaction
from personal_os.repository.protocols import (
    AccountRepositoryProtocol, AuditLogRepositoryProtocol, TransactionRepositoryProtocol,
)
from personal_os.services.permissions import OperationClass, require_permission
from personal_os.services.write_contract import WriteReferenceError

__all__ = ["OpeningBalanceWriteUnitOfWork", "OpeningBalanceWriteContract", "WriteReferenceError"]


class OpeningBalanceWriteUnitOfWork(Protocol):
    """Fresh isolated transaction; rollback on exceptional exit, never suppress."""
    accounts: AccountRepositoryProtocol
    transactions: TransactionRepositoryProtocol
    audit_logs: AuditLogRepositoryProtocol

    def __enter__(self) -> OpeningBalanceWriteUnitOfWork: ...
    def __exit__(self, exc_type, exc, tb) -> None: ...
    def commit(self) -> None: ...


class OpeningBalanceWriteContract:
    def __init__(
        self, uow_factory: Callable[[], OpeningBalanceWriteUnitOfWork], *,
        clock: Callable[[], dt.datetime] = utc_now,
        audit_id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._audit_id_factory = audit_id_factory

    def add_opening_balance(
        self, request: AddOpeningBalanceInput, *, context: WriteContext,
    ) -> AddOpeningBalanceResult:
        # Revalidate even model_construct/model_copy instances at the boundary.
        context = WriteContext.model_validate(context.model_dump())
        require_permission(
            OperationClass.LOCAL_PERSONAL_DATA_WRITE,
            user_approved=context.approved,
        )
        request = AddOpeningBalanceInput.model_validate({
            name: getattr(request, name) for name in AddOpeningBalanceInput.model_fields
        })
        transaction = TransactionRecord(
            id=request.id, account_id=request.account_id,
            transaction_type=TransactionKind.OPENING_BALANCE, amount=request.amount,
            occurred_at=request.occurred_at, status=TransactionStatus.ACTIVE,
            memo=request.memo,
        )
        audit_id = self._audit_id_factory()
        if not isinstance(audit_id, uuid.UUID):
            raise TypeError("audit ID must be UUID")
        audit = AuditLogRecord(
            id=audit_id, actor=context.actor, action="add_opening_balance",
            affected_entity_type="transaction", affected_entity_id=transaction.id,
            old_value=None, new_value=canonical_transaction(transaction),
            reason=context.reason,
            approval_status=ApprovalStatus.EXPLICITLY_APPROVED.value,
            occurred_at=to_utc(self._clock()),
            model_or_agent=context.model_or_agent,
            tool="add_opening_balance", source=context.source,
        )
        result = AddOpeningBalanceResult(transaction=transaction, audit_id=audit.id)
        with self._uow_factory() as uow:
            account = uow.accounts.get(transaction.account_id)
            if account is None:
                raise WriteReferenceError("account not found")
            if account.currency_code != transaction.amount.currency_code:
                raise CurrencyMismatchError("opening balance currency must match account currency")
            if uow.transactions.get(transaction.id) is not None:
                raise WriteReferenceError("transaction ID already exists")
            existing = uow.transactions.list_by_account(transaction.account_id)
            if any(tx.transaction_type is TransactionKind.OPENING_BALANCE for tx in existing):
                raise WriteReferenceError("account already has an opening balance")
            uow.transactions.add(transaction)
            uow.audit_logs.add(audit)
            uow.commit()
        return result
