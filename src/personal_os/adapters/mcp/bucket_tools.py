"""MCP translation: clients cannot provide approval or audit provenance."""
import datetime as dt
import uuid
from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import ValidationError

from personal_os.domain.bucket_write_contracts import AddCapitalBucketInput, AddCashLinkedAllocationInput, ReallocateCapitalInput
from personal_os.domain.enums import BucketRole
from personal_os.services.permissions import PermissionDeniedError
from personal_os.services.write_contract import WriteReferenceError


def register_bucket_tools(server: MCPServer, service) -> None:
    def execute(cls, values, reason):
        try:
            for key in ("id", "account_id", "bucket_id", "from_bucket_id", "to_bucket_id"):
                if key in values:
                    values[key] = uuid.UUID(values[key])
            values["created_at"] = dt.datetime.fromisoformat(values["created_at"])
            if "bucket_role" in values:
                values["bucket_role"] = BucketRole(values["bucket_role"])
            request = cls(**values)
            return service.execute(request, reason=reason)
        except PermissionDeniedError:
            return {"error": {"code": "APPROVAL_REQUIRED", "message": "Local approval required."}}
        except (ValueError, TypeError, ValidationError, WriteReferenceError):
            return {"error": {"code": "INVALID_INPUT", "message": "Invalid bucket request or conflicting operation ID."}}
        except Exception:
            return {"error": {"code": "WRITE_FAILED", "message": "Outcome unknown. Retry only the exact same operation ID and request after checking the audit receipt."}}

    annotations = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False)

    @server.tool(annotations=annotations)
    def add_capital_bucket(id: str, account_id: str, name: str, bucket_role: str,
                           is_protected: bool, created_at: str, reason: str) -> dict[str, Any]:
        """Create an ACTIVE bucket on an ACTIVE CASH account after local approval.

        No rename, role/protection update, or archive. Reuse the same ID and all
        arguments for an uncertain retry; changed content is rejected.
        """
        return execute(AddCapitalBucketInput, dict(id=id, account_id=account_id, name=name,
                       bucket_role=bucket_role, is_protected=is_protected, created_at=created_at), reason)

    @server.tool(annotations=annotations)
    def add_cash_linked_allocation(id: str, bucket_id: str, amount_minor: int,
                                   currency_code: str, created_at: str, reason: str) -> dict[str, Any]:
        """Create ONE NEW NORMAL cash transaction AND its full bucket allocation.

        Changes Q1 as well as Q2/Q3. Do not use for cash already entered through
        add_transaction, add_opening_balance, or import: that would double count.
        Signed nonzero integer minor units. Local approval required. A correcting
        opposite signed operation must use a NEW ID and an explanatory reason.
        """
        return execute(AddCashLinkedAllocationInput, dict(id=id, bucket_id=bucket_id,
                       amount_minor=amount_minor, currency_code=currency_code, created_at=created_at), reason)

    @server.tool(annotations=annotations)
    def reallocate_capital(id: str, from_bucket_id: str, to_bucket_id: str,
                           amount_minor: int, currency_code: str, created_at: str, reason: str) -> dict[str, Any]:
        """Append an atomic zero-sum pair between distinct buckets in ONE CASH account.

        No cash movement or Q1 change. Positive integer minor units. Local approval
        required even for protected buckets. Reverse with a NEW ID, swapped buckets,
        and an explanatory reason; never overwrite history. Does not enforce a
        nonnegative bucket balance, consistent with the signed ledger semantics.
        """
        return execute(ReallocateCapitalInput, dict(id=id, from_bucket_id=from_bucket_id,
                       to_bucket_id=to_bucket_id, amount_minor=amount_minor,
                       currency_code=currency_code, created_at=created_at), reason)
