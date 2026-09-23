"""Approval-gated FinancialMetric registration; persistence injected via Protocol.

Its own small contract, not a method on FinanceWriteContract or
AccountWriteContract -- matching this project's established pattern (see
ADR-015's identical reasoning for AccountWriteContract).
"""
from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Callable
from typing import Protocol

from personal_os.domain.datetime import to_utc, utc_now
from personal_os.domain.metric_write_contracts import (
    AddMetricInput, AddMetricResult, canonical_metric,
)
from personal_os.domain.records import AuditLogRecord, FinancialMetricRecord
from personal_os.domain.write_contracts import ApprovalStatus, WriteContext
from personal_os.repository.protocols import AuditLogRepositoryProtocol, FinancialMetricRepositoryProtocol
from personal_os.services.permissions import OperationClass, require_permission
from personal_os.services.write_contract import WriteReferenceError

__all__ = ["MetricWriteUnitOfWork", "MetricWriteContract", "WriteReferenceError"]


class MetricWriteUnitOfWork(Protocol):
    financial_metrics: FinancialMetricRepositoryProtocol
    audit_logs: AuditLogRepositoryProtocol

    def __enter__(self) -> MetricWriteUnitOfWork: ...
    def __exit__(self, exc_type, exc, tb) -> None: ...
    def commit(self) -> None: ...


class MetricWriteContract:
    def __init__(
        self, uow_factory: Callable[[], MetricWriteUnitOfWork], *,
        clock: Callable[[], dt.datetime] = utc_now,
        audit_id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._audit_id_factory = audit_id_factory

    def add_metric(
        self, request: AddMetricInput, *, context: WriteContext,
    ) -> AddMetricResult:
        context = WriteContext.model_validate(context.model_dump())
        require_permission(
            OperationClass.LOCAL_PERSONAL_DATA_WRITE,
            user_approved=context.approved,
        )
        request = AddMetricInput.model_validate({
            name: getattr(request, name) for name in AddMetricInput.model_fields
        })
        recorded_at = to_utc(self._clock())
        metric = FinancialMetricRecord(
            id=request.id, key=request.key, display_name=request.display_name,
            created_at=recorded_at,
        )
        audit_id = self._audit_id_factory()
        if not isinstance(audit_id, uuid.UUID):
            raise TypeError("audit ID must be UUID")
        audit = AuditLogRecord(
            id=audit_id, actor=context.actor, action="add_metric",
            affected_entity_type="financial_metric", affected_entity_id=metric.id,
            old_value=None, new_value=canonical_metric(metric),
            reason=context.reason,
            approval_status=ApprovalStatus.EXPLICITLY_APPROVED.value,
            occurred_at=recorded_at,
            model_or_agent=context.model_or_agent,
            tool="add_metric", source=context.source,
        )
        result = AddMetricResult(metric=metric, audit_id=audit.id)
        with self._uow_factory() as uow:
            if uow.financial_metrics.get_by_key(metric.key) is not None:
                raise WriteReferenceError("metric key already exists")
            uow.financial_metrics.add(metric)
            uow.audit_logs.add(audit)
            uow.commit()
        return result
