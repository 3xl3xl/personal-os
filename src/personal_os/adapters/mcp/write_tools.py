"""Thin write translation; approval and mutation are Service responsibilities."""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field, ValidationError

from personal_os.domain.money import Money, CurrencyMismatchError
from personal_os.domain.write_contracts import AddTransactionInput
from personal_os.services.approved_write import ApprovedTransactionWrite
from personal_os.services.permissions import PermissionDeniedError
from personal_os.services.write_contract import WriteReferenceError


def register_write_tools(server: MCPServer, service: ApprovedTransactionWrite) -> None:
    @server.tool(annotations=ToolAnnotations(
        read_only_hint=False, destructive_hint=False,
        idempotent_hint=False, open_world_hint=False,
    ))
    def add_transaction(
        id: str, account_id: str,
        amount_minor: Annotated[int, Field(strict=True)],
        currency_code: str, occurred_at: str, reason: str,
        metric_key: str | None = None, memo: str | None = None,
    ) -> dict[str, Any]:
        """Propose one NORMAL local ledger fact. A local human dialog must approve it.

        Amount is an exact integer in minor units. No transfer or payment occurs.
        Cancelled requests write nothing. Never retry without the user's intent.
        """
        try:
            request = AddTransactionInput(
                id=uuid.UUID(id), account_id=uuid.UUID(account_id),
                amount=Money(amount_minor, currency_code),
                occurred_at=dt.datetime.fromisoformat(occurred_at),
                metric_key=metric_key, memo=memo,
            )
        except (ValueError, TypeError, ValidationError):
            return {"error": {"code": "INVALID_INPUT", "message": "Invalid transaction arguments."}}
        try:
            result = service.add_transaction(request, reason=reason)
            return {"transaction_id": str(result.transaction.id), "audit_id": str(result.audit_id),
                    "approval_status": result.approval_status.value}
        except PermissionDeniedError:
            return {"error": {"code": "APPROVAL_REQUIRED", "message": "The local user did not approve this transaction."}}
        except (ValidationError, WriteReferenceError):
            return {"error": {"code": "INVALID_INPUT", "message": "Invalid transaction or audit metadata."}}
        except CurrencyMismatchError:
            return {"error": {"code": "CURRENCY_MISMATCH", "message": "Transaction and account currencies must match."}}
        except Exception:
            return {"error": {"code": "WRITE_FAILED", "message": "Write could not be confirmed. Check the transaction ID before retrying."}}
