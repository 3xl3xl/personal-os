"""Obtain a trusted, request-bound decision before invoking the target write contract."""
from __future__ import annotations

from collections.abc import Callable

from personal_os.domain.target_write_contracts import (
    AddFinancialTargetInput, AddFinancialTargetResult,
    AddMonthlyTargetInput, AddMonthlyTargetResult,
)
from personal_os.domain.write_contracts import WriteContext
from personal_os.services.target_write_contract import TargetWriteContract


class ApprovedTargetWrite:
    def __init__(
        self, contract: TargetWriteContract,
        approve_financial: Callable[[AddFinancialTargetInput, WriteContext], bool],
        approve_monthly: Callable[[AddMonthlyTargetInput, WriteContext], bool],
        *, actor: str, model_or_agent: str, source: str,
    ) -> None:
        self._contract = contract
        self._approve_financial = approve_financial
        self._approve_monthly = approve_monthly
        self._actor = actor
        self._agent = model_or_agent
        self._source = source

    def _context(self, reason: str) -> WriteContext:
        return WriteContext(actor=self._actor, reason=reason,
                            model_or_agent=self._agent, source=self._source)

    def add_financial_target(self, request: AddFinancialTargetInput, *, reason: str) -> AddFinancialTargetResult:
        request = AddFinancialTargetInput.model_validate({
            name: getattr(request, name) for name in AddFinancialTargetInput.model_fields
        })
        context = self._context(reason)
        approved = self._approve_financial(request, context) is True
        return self._contract.add_financial_target(request, context=context.model_copy(update={"approved": approved}))

    def add_monthly_target(self, request: AddMonthlyTargetInput, *, reason: str) -> AddMonthlyTargetResult:
        request = AddMonthlyTargetInput.model_validate({
            name: getattr(request, name) for name in AddMonthlyTargetInput.model_fields
        })
        context = self._context(reason)
        approved = self._approve_monthly(request, context) is True
        return self._contract.add_monthly_target(request, context=context.model_copy(update={"approved": approved}))
