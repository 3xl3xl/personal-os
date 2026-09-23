"""Obtain a trusted, request-bound decision before invoking the opening balance write contract."""
from __future__ import annotations

from collections.abc import Callable

from personal_os.domain.opening_balance_write_contracts import (
    AddOpeningBalanceInput, AddOpeningBalanceResult,
)
from personal_os.domain.write_contracts import WriteContext
from personal_os.services.opening_balance_write_contract import OpeningBalanceWriteContract


class ApprovedOpeningBalanceWrite:
    def __init__(
        self, contract: OpeningBalanceWriteContract,
        approve: Callable[[AddOpeningBalanceInput, WriteContext], bool],
        *, actor: str, model_or_agent: str, source: str,
    ) -> None:
        self._contract = contract
        self._approve = approve
        self._actor = actor
        self._agent = model_or_agent
        self._source = source

    def add_opening_balance(self, request: AddOpeningBalanceInput, *, reason: str) -> AddOpeningBalanceResult:
        # Immutable, validated instances are the exact values displayed and used.
        request = AddOpeningBalanceInput.model_validate({
            name: getattr(request, name) for name in AddOpeningBalanceInput.model_fields
        })
        context = WriteContext(actor=self._actor, reason=reason,
                               model_or_agent=self._agent, source=self._source)
        approved = self._approve(request, context) is True
        return self._contract.add_opening_balance(request, context=context.model_copy(update={"approved": approved}))
