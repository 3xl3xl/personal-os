"""Thin write translation; approval and mutation are Service responsibilities.

Input is exactly RawBankTransaction's vendor-neutral fields plus a target
Personal OS account_id per line -- never a freee-shaped payload (ADR-016).
The calling AI client is responsible for mapping whatever an external MCP
(e.g. freee's official server) returned into this shape before calling here.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import ValidationError

from personal_os.domain.enums import ExternalSource
from personal_os.domain.external_facts import RawBankTransaction
from personal_os.domain.money import CurrencyMismatchError, Money
from personal_os.services.approved_import_write import ApprovedImportWrite
from personal_os.services.write_contract import WriteReferenceError


def register_import_tools(server: MCPServer, service: ApprovedImportWrite) -> None:
    @server.tool(annotations=ToolAnnotations(
        read_only_hint=False, destructive_hint=False,
        idempotent_hint=False, open_world_hint=False,
    ))
    def import_bank_transactions(
        transactions: list[dict[str, Any]], reason: str,
    ) -> dict[str, Any]:
        """Stage, batch-review, and write already-normalized external bank lines.

        Each entry must already be normalized into Personal OS's own shape --
        source, external_office_id, external_account_id,
        external_transaction_id, account_id, amount_minor, currency_code,
        occurred_at, and an optional description -- never a vendor-specific
        payload. A native macOS multi-select dialog lists every new-or-changed
        line; only the lines a human selects there are written. An empty
        selection or a cancelled dialog writes nothing. Atomicity is per
        line, not per batch: if one line fails validation, lines already
        written earlier in this same call stay committed.
        """
        try:
            raw_transactions = [
                (
                    RawBankTransaction(
                        source=ExternalSource(entry["source"]),
                        external_office_id=entry["external_office_id"],
                        external_account_id=entry["external_account_id"],
                        external_transaction_id=entry["external_transaction_id"],
                        amount=Money(entry["amount_minor"], entry["currency_code"]),
                        occurred_at=dt.datetime.fromisoformat(entry["occurred_at"]),
                        description=entry.get("description"),
                    ),
                    uuid.UUID(entry["account_id"]),
                )
                for entry in transactions
            ]
        except (KeyError, ValueError, TypeError, ValidationError):
            return {"error": {"code": "INVALID_INPUT", "message": "Invalid transaction arguments."}}
        try:
            preview, result = service.import_batch(raw_transactions, reason=reason)
        except (ValidationError, WriteReferenceError, CurrencyMismatchError):
            return {"error": {"code": "INVALID_INPUT",
                               "message": "Invalid transaction or account reference. "
                                          "Lines already written earlier in this call, if any, stay committed."}}
        except Exception:
            return {"error": {"code": "WRITE_FAILED",
                               "message": "Import could not be confirmed. "
                                          "Lines already written earlier in this call, if any, stay committed."}}
        by_id = {c.candidate_id: c for c in preview.candidates}
        return {
            "imported": [
                {"external_transaction_id": by_id[item.candidate_id].raw.external_transaction_id,
                 "transaction_id": str(item.transaction_id), "audit_id": str(item.audit_id)}
                for item in result.imported
            ],
            "skipped_external_transaction_ids": [
                by_id[cid].raw.external_transaction_id
                for cid in result.skipped_candidate_ids if cid in by_id
            ],
        }
