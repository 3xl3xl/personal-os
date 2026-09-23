"""Obtain a trusted, request-bound decision before invoking the account write contract."""
from __future__ import annotations

from collections.abc import Callable

from personal_os.domain.account_write_contracts import AddAccountInput, AddAccountResult
from personal_os.domain.write_contracts import WriteContext
from personal_os.services.account_write_contract import AccountWriteContract


class ApprovedAccountWrite:
    def __init__(
        self, contract: AccountWriteContract,
        approve: Callable[[AddAccountInput, WriteContext], bool],
        *, actor: str, model_or_agent: str, source: str,
    ) -> None:
        self._contract = contract
        self._approve = approve
        self._actor = actor
        self._agent = model_or_agent
        self._source = source

    def add_account(self, request: AddAccountInput, *, reason: str) -> AddAccountResult:
        # Immutable, validated instances are the exact values displayed and used.
        request = AddAccountInput.model_validate({
            name: getattr(request, name) for name in AddAccountInput.model_fields
        })
        context = WriteContext(actor=self._actor, reason=reason,
                               model_or_agent=self._agent, source=self._source)
        approved = self._approve(request, context) is True
        return self._contract.add_account(request, context=context.model_copy(update={"approved": approved}))
