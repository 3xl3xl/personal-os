"""Obtain a trusted, request-bound decision before invoking the metric write contract."""
from __future__ import annotations

from collections.abc import Callable

from personal_os.domain.metric_write_contracts import AddMetricInput, AddMetricResult
from personal_os.domain.write_contracts import WriteContext
from personal_os.services.metric_write_contract import MetricWriteContract


class ApprovedMetricWrite:
    def __init__(
        self, contract: MetricWriteContract,
        approve: Callable[[AddMetricInput, WriteContext], bool],
        *, actor: str, model_or_agent: str, source: str,
    ) -> None:
        self._contract = contract
        self._approve = approve
        self._actor = actor
        self._agent = model_or_agent
        self._source = source

    def add_metric(self, request: AddMetricInput, *, reason: str) -> AddMetricResult:
        request = AddMetricInput.model_validate({
            name: getattr(request, name) for name in AddMetricInput.model_fields
        })
        context = WriteContext(actor=self._actor, reason=reason,
                               model_or_agent=self._agent, source=self._source)
        approved = self._approve(request, context) is True
        return self._contract.add_metric(request, context=context.model_copy(update={"approved": approved}))
