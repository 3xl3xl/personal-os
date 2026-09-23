"""Obtain a trusted, request-bound decision before invoking the write contract."""
from __future__ import annotations

from collections.abc import Callable

from personal_os.domain.write_contracts import AddTransactionInput, WriteContext, AddTransactionResult
from personal_os.services.write_contract import FinanceWriteContract


class ApprovedTransactionWrite:
    def __init__(
        self, contract: FinanceWriteContract,
        approve: Callable[[AddTransactionInput, WriteContext], bool],
        *, actor: str, model_or_agent: str, source: str,
    ) -> None:
        self._contract = contract
        self._approve = approve
        self._actor = actor
        self._agent = model_or_agent
        self._source = source

    def add_transaction(self, request: AddTransactionInput, *, reason: str) -> AddTransactionResult:
        # Immutable, validated instances are the exact values displayed and used.
        request = AddTransactionInput.model_validate({
            name: getattr(request, name) for name in AddTransactionInput.model_fields
        })
        context = WriteContext(actor=self._actor, reason=reason,
                               model_or_agent=self._agent, source=self._source)
        approved = self._approve(request, context) is True
        return self._contract.add_transaction(request, context=context.model_copy(update={"approved": approved}))
