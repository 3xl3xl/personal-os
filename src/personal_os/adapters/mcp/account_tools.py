"""Thin write translation; approval and mutation are Service responsibilities."""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import ValidationError

from personal_os.domain.account_write_contracts import AddAccountInput
from personal_os.domain.enums import AccountType
from personal_os.services.approved_account_write import ApprovedAccountWrite
from personal_os.services.permissions import PermissionDeniedError
from personal_os.services.write_contract import WriteReferenceError


def register_account_tools(server: MCPServer, service: ApprovedAccountWrite) -> None:
    @server.tool(annotations=ToolAnnotations(
        read_only_hint=False, destructive_hint=False,
        idempotent_hint=False, open_world_hint=False,
    ))
    def add_account(
        id: str, name: str, account_type: str, currency_code: str,
        opened_at: str, reason: str,
    ) -> dict[str, Any]:
        """Create ONE local Account ledger record. A local human dialog must approve it.

        This does not open, link, or authenticate any real bank or broker
        account -- it only creates a Personal OS record you can later post
        transactions against. Cancelled requests write nothing.
        """
        try:
            request = AddAccountInput(
                id=uuid.UUID(id), name=name,
                account_type=AccountType(account_type),
                currency_code=currency_code,
                opened_at=dt.datetime.fromisoformat(opened_at),
            )
        except (ValueError, TypeError, ValidationError):
            return {"error": {"code": "INVALID_INPUT", "message": "Invalid account arguments."}}
        try:
            result = service.add_account(request, reason=reason)
            return {"account_id": str(result.account.id), "audit_id": str(result.audit_id),
                    "approval_status": result.approval_status.value}
        except PermissionDeniedError:
            return {"error": {"code": "APPROVAL_REQUIRED", "message": "The local user did not approve this account."}}
        except (ValidationError, WriteReferenceError):
            return {"error": {"code": "INVALID_INPUT", "message": "Invalid account metadata."}}
        except Exception:
            return {"error": {"code": "WRITE_FAILED", "message": "Write could not be confirmed. Check the account ID before retrying."}}
