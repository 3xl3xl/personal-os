"""Thin write translation; approval and mutation are Service responsibilities."""
from __future__ import annotations

import uuid
from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import ValidationError

from personal_os.domain.metric_write_contracts import AddMetricInput
from personal_os.services.approved_metric_write import ApprovedMetricWrite
from personal_os.services.permissions import PermissionDeniedError
from personal_os.services.write_contract import WriteReferenceError


def register_metric_tools(server: MCPServer, service: ApprovedMetricWrite) -> None:
    @server.tool(annotations=ToolAnnotations(
        read_only_hint=False, destructive_hint=False,
        idempotent_hint=False, open_world_hint=False,
    ))
    def add_metric(id: str, key: str, display_name: str, reason: str) -> dict[str, Any]:
        """Register ONE local tracked KPI (Target-vs-Actual only; never a
        revenue source or accounting category). A local human dialog must
        approve it. This does not itself set a target value -- see
        add_financial_target / add_monthly_target. Cancelled requests write
        nothing.
        """
        try:
            request = AddMetricInput(id=uuid.UUID(id), key=key, display_name=display_name)
        except (ValueError, TypeError, ValidationError):
            return {"error": {"code": "INVALID_INPUT", "message": "Invalid metric arguments."}}
        try:
            result = service.add_metric(request, reason=reason)
            return {"metric_key": result.metric.key, "audit_id": str(result.audit_id),
                    "approval_status": result.approval_status.value}
        except PermissionDeniedError:
            return {"error": {"code": "APPROVAL_REQUIRED", "message": "The local user did not approve this metric."}}
        except (ValidationError, WriteReferenceError):
            return {"error": {"code": "INVALID_INPUT", "message": "Invalid metric metadata."}}
        except Exception:
            return {"error": {"code": "WRITE_FAILED", "message": "Write could not be confirmed. Check the metric key before retrying."}}
