"""Approved append-only writes, with atomic audits and stable operation IDs."""
from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import Protocol

from personal_os.domain.bucket_write_contracts import (
    AddCapitalBucketInput, AddCashLinkedAllocationInput, ReallocateCapitalInput,
)
from personal_os.domain.datetime import utc_now
from personal_os.domain.enums import (
    AccountStatus, AccountType, CapitalBucketStatus, EntryType,
    TransactionKind, TransactionStatus,
)
from personal_os.domain.money import Money
from personal_os.domain.records import AuditLogRecord, BucketAllocationRecord, CapitalBucketRecord, TransactionRecord
from personal_os.domain.write_contracts import ApprovalStatus, WriteContext
from personal_os.repository.protocols import (
    AccountRepositoryProtocol, AuditLogRepositoryProtocol, BucketAllocationRepositoryProtocol,
    CapitalBucketRepositoryProtocol, TransactionRepositoryProtocol,
)
from personal_os.services.permissions import OperationClass, require_permission
from personal_os.services.write_contract import WriteReferenceError


class BucketWriteUnitOfWork(Protocol):
    accounts: AccountRepositoryProtocol
    audit_logs: AuditLogRepositoryProtocol
    bucket_allocations: BucketAllocationRepositoryProtocol
    capital_buckets: CapitalBucketRepositoryProtocol
    transactions: TransactionRepositoryProtocol
    def __enter__(self) -> BucketWriteUnitOfWork: ...
    def __exit__(self, exc_type, exc, tb) -> None: ...
    def commit(self) -> None: ...


class BucketWriteContract:
    def __init__(self, uow_factory: Callable[[], BucketWriteUnitOfWork], *, clock=utc_now):
        self._factory = uow_factory
        self._clock = clock

    def execute(self, request, *, context: WriteContext) -> dict:
        context = WriteContext.model_validate(context.model_dump())
        require_permission(OperationClass.LOCAL_PERSONAL_DATA_WRITE, user_approved=context.approved)
        if type(request) not in (AddCapitalBucketInput, AddCashLinkedAllocationInput, ReallocateCapitalInput):
            raise ValueError("unsupported request")
        request = type(request).model_validate({name: getattr(request, name) for name in type(request).model_fields})
        tool = {AddCapitalBucketInput: "add_capital_bucket", AddCashLinkedAllocationInput: "add_cash_linked_allocation",
                ReallocateCapitalInput: "reallocate_capital"}[type(request)]
        audit_id = uuid.uuid5(request.id, tool + ":audit")
        payload = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        with self._factory() as uow:
            # The persisted audit is the operation receipt, not an untrusted client flag.
            prior = next((a for a in uow.audit_logs.list_all() if a.id == audit_id), None)
            if prior is not None:
                if (prior.tool, prior.new_value, prior.actor, prior.model_or_agent, prior.source, prior.reason) != (
                    tool, payload, context.actor, context.model_or_agent, context.source, context.reason
                ):
                    raise WriteReferenceError("operation ID reused with changed request or provenance")
                return {"operation_id": str(request.id), "audit_id": str(audit_id), "replayed": True}
            if isinstance(request, AddCapitalBucketInput):
                account = uow.accounts.get(request.account_id)
                self._account(account)
                if request.created_at < account.opened_at:
                    raise WriteReferenceError("bucket predates account")
                if uow.capital_buckets.get(request.id) is not None:
                    raise WriteReferenceError("bucket ID already exists")
                uow.capital_buckets.add(CapitalBucketRecord(
                    request.id, account.id, request.name, request.bucket_role, request.is_protected,
                    CapitalBucketStatus.ACTIVE, request.created_at,
                ))
            else:
                bucket_ids = ([request.bucket_id] if isinstance(request, AddCashLinkedAllocationInput)
                              else [request.from_bucket_id, request.to_bucket_id])
                buckets = [uow.capital_buckets.get(i) for i in bucket_ids]
                if any(b is None or b.status != CapitalBucketStatus.ACTIVE for b in buckets):
                    raise WriteReferenceError("active buckets required")
                account = uow.accounts.get(buckets[0].account_id)
                self._account(account)
                if any(b.account_id != account.id or b.created_at > request.created_at for b in buckets):
                    raise WriteReferenceError("same account and existing buckets required")
                if account.currency_code != request.currency_code:
                    raise WriteReferenceError("currency mismatch")
                if isinstance(request, AddCashLinkedAllocationInput):
                    if request.amount_minor == 0:
                        raise WriteReferenceError("nonzero amount required")
                    tx_id = uuid.uuid5(request.id, "transaction")
                    if uow.transactions.get(tx_id) is not None:
                        raise WriteReferenceError("transaction ID already exists")
                    uow.transactions.add(TransactionRecord(
                        tx_id, account.id, TransactionKind.NORMAL,
                        Money(request.amount_minor, request.currency_code), request.created_at, TransactionStatus.ACTIVE,
                    ))
                    legs = [(request.id, buckets[0], request.amount_minor)]
                    kind, origin, group = EntryType.CASH_LINKED, tx_id, None
                else:
                    if bucket_ids[0] == bucket_ids[1]:
                        raise WriteReferenceError("distinct buckets required")
                    legs = [(uuid.uuid5(request.id, "debit"), buckets[0], -request.amount_minor),
                            (uuid.uuid5(request.id, "credit"), buckets[1], request.amount_minor)]
                    kind, origin, group = EntryType.REALLOCATION, None, request.id
                for leg_id, bucket, amount in legs:
                    if uow.bucket_allocations.get(leg_id) is not None:
                        raise WriteReferenceError("allocation ID already exists")
                    uow.bucket_allocations.add(BucketAllocationRecord(
                        leg_id, bucket.id, account.id, Money(amount, request.currency_code),
                        kind, request.created_at, origin, group,
                    ))
            uow.audit_logs.add(AuditLogRecord(
                id=audit_id, actor=context.actor, action=tool, affected_entity_type="capital_bucket" if isinstance(request, AddCapitalBucketInput) else "bucket_allocation_operation",
                affected_entity_id=request.id, old_value=None, new_value=payload,
                reason=context.reason, approval_status=ApprovalStatus.EXPLICITLY_APPROVED.value,
                occurred_at=self._clock(), model_or_agent=context.model_or_agent, tool=tool, source=context.source,
            ))
            uow.commit()
        return {"operation_id": str(request.id), "audit_id": str(audit_id), "replayed": False}

    @staticmethod
    def _account(account):
        if account is None or account.status != AccountStatus.ACTIVE or account.account_type != AccountType.CASH:
            raise WriteReferenceError("active CASH account required")


class ApprovedBucketWrite:
    def __init__(self, contract: BucketWriteContract, approve: Callable, *, actor: str, model_or_agent: str, source: str):
        self._contract, self._approve = contract, approve
        self._actor, self._agent, self._source = actor, model_or_agent, source

    def execute(self, request, *, reason: str):
        request = type(request).model_validate({name: getattr(request, name) for name in type(request).model_fields})
        context = WriteContext(actor=self._actor, reason=reason, model_or_agent=self._agent, source=self._source)
        approved = self._approve(request, context) is True
        return self._contract.execute(request, context=context.model_copy(update={"approved": approved}))
