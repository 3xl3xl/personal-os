"""Thin write translation; approval and mutation are Service responsibilities."""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import ValidationError

from personal_os.domain.money import Money
from personal_os.domain.target_write_contracts import AddFinancialTargetInput, AddMonthlyTargetInput
from personal_os.services.approved_target_write import ApprovedTargetWrite
from personal_os.services.permissions import PermissionDeniedError
from personal_os.services.write_contract import WriteReferenceError


def register_target_tools(server: MCPServer, service: ApprovedTargetWrite) -> None:
    @server.tool(annotations=ToolAnnotations(
        read_only_hint=False, destructive_hint=False,
        idempotent_hint=False, open_world_hint=False,
    ))
    def add_financial_target(
        id: str, metric_key: str, target_amount_minor: int, currency_code: str,
        effective_from: str, reason: str,
    ) -> dict[str, Any]:
        """Set ONE new version of an overall target for an existing metric (Q4).
        Append/version-only -- no prior version is changed or deleted. A
        local human dialog must approve it. Cancelled requests write nothing.
        """
        try:
            request = AddFinancialTargetInput(
                id=uuid.UUID(id), metric_key=metric_key,
                target_amount=Money(target_amount_minor, currency_code),
                effective_from=dt.datetime.fromisoformat(effective_from),
            )
        except (ValueError, TypeError, ValidationError):
            return {"error": {"code": "INVALID_INPUT", "message": "Invalid financial target arguments."}}
        try:
            result = service.add_financial_target(request, reason=reason)
            return {"target_id": str(result.target.id), "audit_id": str(result.audit_id),
                    "approval_status": result.approval_status.value}
        except PermissionDeniedError:
            return {"error": {"code": "APPROVAL_REQUIRED", "message": "The local user did not approve this financial target."}}
        except (ValidationError, WriteReferenceError):
            return {"error": {"code": "INVALID_INPUT", "message": "Invalid target metadata or unknown metric."}}
        except Exception:
            return {"error": {"code": "WRITE_FAILED", "message": "Write could not be confirmed. Check for a duplicate effective_from before retrying."}}

    @server.tool(annotations=ToolAnnotations(
        read_only_hint=False, destructive_hint=False,
        idempotent_hint=False, open_world_hint=False,
    ))
    def add_monthly_target(
        id: str, metric_key: str, year: int, month: int,
        target_amount_minor: int, currency_code: str, effective_from: str, reason: str,
    ) -> dict[str, Any]:
        """Set ONE new version of a (year, month) target for an existing
        metric (Q5). Append/version-only -- no prior version is changed or
        deleted. A local human dialog must approve it. Cancelled requests
        write nothing.
        """
        try:
            request = AddMonthlyTargetInput(
                id=uuid.UUID(id), metric_key=metric_key, year=year, month=month,
                target_amount=Money(target_amount_minor, currency_code),
                effective_from=dt.datetime.fromisoformat(effective_from),
            )
        except (ValueError, TypeError, ValidationError):
            return {"error": {"code": "INVALID_INPUT", "message": "Invalid monthly target arguments."}}
        try:
            result = service.add_monthly_target(request, reason=reason)
            return {"target_id": str(result.target.id), "audit_id": str(result.audit_id),
                    "approval_status": result.approval_status.value}
        except PermissionDeniedError:
            return {"error": {"code": "APPROVAL_REQUIRED", "message": "The local user did not approve this monthly target."}}
        except (ValidationError, WriteReferenceError):
            return {"error": {"code": "INVALID_INPUT", "message": "Invalid target metadata or unknown metric."}}
        except Exception:
            return {"error": {"code": "WRITE_FAILED", "message": "Write could not be confirmed. Check for a duplicate effective_from before retrying."}}
