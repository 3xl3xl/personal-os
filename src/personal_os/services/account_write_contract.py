"""Approval-gated Account-creation write; persistence injected through a Protocol.

Deliberately its own small contract rather than a method added to
personal_os.services.write_contract.FinanceWriteContract: that class and its
tests (Step 19/20) are left completely unmodified, matching this project's
established pattern of adding parallel modules for new write shapes instead
of editing already-tested ones (see services/import_review.py's rationale).
"""
from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Callable
from typing import Protocol

from personal_os.domain.account_write_contracts import (
    AddAccountInput, AddAccountResult, canonical_account,
)
from personal_os.domain.datetime import to_utc, utc_now
from personal_os.domain.enums import AccountStatus
from personal_os.domain.records import AccountRecord, AuditLogRecord
from personal_os.domain.write_contracts import ApprovalStatus, WriteContext
from personal_os.repository.protocols import AccountRepositoryProtocol, AuditLogRepositoryProtocol
from personal_os.services.permissions import OperationClass, require_permission
from personal_os.services.write_contract import WriteReferenceError

__all__ = ["AccountWriteUnitOfWork", "AccountWriteContract", "WriteReferenceError"]


class AccountWriteUnitOfWork(Protocol):
    """Fresh isolated transaction; rollback on exceptional exit, never suppress."""
    accounts: AccountRepositoryProtocol
    audit_logs: AuditLogRepositoryProtocol

    def __enter__(self) -> AccountWriteUnitOfWork: ...
    def __exit__(self, exc_type, exc, tb) -> None: ...
    def commit(self) -> None: ...


class AccountWriteContract:
    def __init__(
        self, uow_factory: Callable[[], AccountWriteUnitOfWork], *,
        clock: Callable[[], dt.datetime] = utc_now,
        audit_id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._audit_id_factory = audit_id_factory

    def add_account(
        self, request: AddAccountInput, *, context: WriteContext,
    ) -> AddAccountResult:
        # Revalidate even model_construct/model_copy instances at the boundary.
        context = WriteContext.model_validate(context.model_dump())
        require_permission(
            OperationClass.LOCAL_PERSONAL_DATA_WRITE,
            user_approved=context.approved,
        )
        request = AddAccountInput.model_validate({
            name: getattr(request, name) for name in AddAccountInput.model_fields
        })
        account = AccountRecord(
            id=request.id, name=request.name, account_type=request.account_type,
            currency_code=request.currency_code, opened_at=request.opened_at,
            status=AccountStatus.ACTIVE,
        )
        audit_id = self._audit_id_factory()
        if not isinstance(audit_id, uuid.UUID):
            raise TypeError("audit ID must be UUID")
        audit = AuditLogRecord(
            id=audit_id, actor=context.actor, action="add_account",
            affected_entity_type="account", affected_entity_id=account.id,
            old_value=None, new_value=canonical_account(account),
            reason=context.reason,
            approval_status=ApprovalStatus.EXPLICITLY_APPROVED.value,
            occurred_at=to_utc(self._clock()),
            model_or_agent=context.model_or_agent,
            tool="add_account", source=context.source,
        )
        result = AddAccountResult(account=account, audit_id=audit.id)
        with self._uow_factory() as uow:
            if uow.accounts.get(account.id) is not None:
                raise WriteReferenceError("account ID already exists")
            uow.accounts.add(account)
            uow.audit_logs.add(audit)
            uow.commit()
        return result
