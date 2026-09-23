"""Approval-gated FinancialTarget/MonthlyTarget version write; persistence
injected via Protocol.

Its own small contract covering both Q4 and Q5's write shapes together
(they are the same append/version-only family), not a method on
FinanceWriteContract or AccountWriteContract -- matching this project's
established pattern (see ADR-015's identical reasoning for
AccountWriteContract). Requires a FinancialMetric to already exist for the
given metric_key -- registering one is MetricWriteContract's job, not this
one's (same "one concern per contract" reasoning).
"""
from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Callable
from typing import Protocol

from personal_os.domain.datetime import to_utc, utc_now
from personal_os.domain.records import AuditLogRecord, FinancialTargetRecord, MonthlyTargetRecord
from personal_os.domain.target_write_contracts import (
    AddFinancialTargetInput, AddFinancialTargetResult,
    AddMonthlyTargetInput, AddMonthlyTargetResult,
    canonical_financial_target, canonical_monthly_target,
)
from personal_os.domain.write_contracts import ApprovalStatus, WriteContext
from personal_os.repository.protocols import (
    AuditLogRepositoryProtocol, FinancialMetricRepositoryProtocol,
    FinancialTargetRepositoryProtocol, MonthlyTargetRepositoryProtocol,
)
from personal_os.services.permissions import OperationClass, require_permission
from personal_os.services.write_contract import WriteReferenceError

__all__ = ["TargetWriteUnitOfWork", "TargetWriteContract", "WriteReferenceError"]


class TargetWriteUnitOfWork(Protocol):
    financial_metrics: FinancialMetricRepositoryProtocol
    financial_targets: FinancialTargetRepositoryProtocol
    monthly_targets: MonthlyTargetRepositoryProtocol
    audit_logs: AuditLogRepositoryProtocol

    def __enter__(self) -> TargetWriteUnitOfWork: ...
    def __exit__(self, exc_type, exc, tb) -> None: ...
    def commit(self) -> None: ...


class TargetWriteContract:
    def __init__(
        self, uow_factory: Callable[[], TargetWriteUnitOfWork], *,
        clock: Callable[[], dt.datetime] = utc_now,
        audit_id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._audit_id_factory = audit_id_factory

    def _audit_id(self) -> uuid.UUID:
        audit_id = self._audit_id_factory()
        if not isinstance(audit_id, uuid.UUID):
            raise TypeError("audit ID must be UUID")
        return audit_id

    def add_financial_target(
        self, request: AddFinancialTargetInput, *, context: WriteContext,
    ) -> AddFinancialTargetResult:
        context = WriteContext.model_validate(context.model_dump())
        require_permission(
            OperationClass.LOCAL_PERSONAL_DATA_WRITE,
            user_approved=context.approved,
        )
        request = AddFinancialTargetInput.model_validate({
            name: getattr(request, name) for name in AddFinancialTargetInput.model_fields
        })
        recorded_at = to_utc(self._clock())
        target = FinancialTargetRecord(
            id=request.id, metric_key=request.metric_key,
            target_amount=request.target_amount, effective_from=request.effective_from,
            created_at=recorded_at,
        )
        audit_id = self._audit_id()
        audit = AuditLogRecord(
            id=audit_id, actor=context.actor, action="add_financial_target",
            affected_entity_type="financial_target", affected_entity_id=target.id,
            old_value=None, new_value=canonical_financial_target(target),
            reason=context.reason,
            approval_status=ApprovalStatus.EXPLICITLY_APPROVED.value,
            occurred_at=recorded_at,
            model_or_agent=context.model_or_agent,
            tool="add_financial_target", source=context.source,
        )
        result = AddFinancialTargetResult(target=target, audit_id=audit.id)
        with self._uow_factory() as uow:
            if uow.financial_metrics.get_by_key(target.metric_key) is None:
                raise WriteReferenceError("financial metric not found")
            if any(existing.effective_from == target.effective_from
                   for existing in uow.financial_targets.list_by_metric(target.metric_key)):
                raise WriteReferenceError("a target version already exists for this metric and effective_from")
            uow.financial_targets.add(target)
            uow.audit_logs.add(audit)
            uow.commit()
        return result

    def add_monthly_target(
        self, request: AddMonthlyTargetInput, *, context: WriteContext,
    ) -> AddMonthlyTargetResult:
        context = WriteContext.model_validate(context.model_dump())
        require_permission(
            OperationClass.LOCAL_PERSONAL_DATA_WRITE,
            user_approved=context.approved,
        )
        request = AddMonthlyTargetInput.model_validate({
            name: getattr(request, name) for name in AddMonthlyTargetInput.model_fields
        })
        recorded_at = to_utc(self._clock())
        target = MonthlyTargetRecord(
            id=request.id, metric_key=request.metric_key, year=request.year, month=request.month,
            target_amount=request.target_amount, effective_from=request.effective_from,
            created_at=recorded_at,
        )
        audit_id = self._audit_id()
        audit = AuditLogRecord(
            id=audit_id, actor=context.actor, action="add_monthly_target",
            affected_entity_type="monthly_target", affected_entity_id=target.id,
            old_value=None, new_value=canonical_monthly_target(target),
            reason=context.reason,
            approval_status=ApprovalStatus.EXPLICITLY_APPROVED.value,
            occurred_at=recorded_at,
            model_or_agent=context.model_or_agent,
            tool="add_monthly_target", source=context.source,
        )
        result = AddMonthlyTargetResult(target=target, audit_id=audit.id)
        with self._uow_factory() as uow:
            if uow.financial_metrics.get_by_key(target.metric_key) is None:
                raise WriteReferenceError("financial metric not found")
            if any(existing.effective_from == target.effective_from
                   for existing in uow.monthly_targets.list_by_metric_year_month(
                       target.metric_key, target.year, target.month)):
                raise WriteReferenceError("a target version already exists for this metric, month, and effective_from")
            uow.monthly_targets.add(target)
            uow.audit_logs.add(audit)
            uow.commit()
        return result
