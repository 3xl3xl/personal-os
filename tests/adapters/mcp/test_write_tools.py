"""MCP -> human approval boundary -> write contract -> real temporary SQLite."""
import uuid

import pytest
from mcp import Client
from sqlalchemy import select

from personal_os.adapters.mcp.server import create_server
from personal_os.adapters.mcp.write_tools import register_write_tools
from personal_os.database.schema import Transaction, AuditLog
from personal_os.repository.unit_of_work import UnitOfWork
from personal_os.services.approved_write import ApprovedTransactionWrite
from personal_os.services.write_contract import FinanceWriteContract
from tests.services.test_write_contract import ACCOUNT, NOW


def arguments():
    return dict(id=str(uuid.uuid4()), account_id=str(ACCOUNT.id), amount_minor=-125,
                currency_code="JPY", occurred_at=NOW.isoformat(), reason="synthetic reason")


def setup_server(session_factory, approval):
    with UnitOfWork(session_factory) as uow:
        uow.accounts.add(ACCOUNT)
        uow.commit()
    factory = lambda: UnitOfWork(session_factory)
    service = ApprovedTransactionWrite(FinanceWriteContract(factory), approval,
                                      actor="synthetic local user", model_or_agent="synthetic-agent", source="synthetic-mcp")
    server = create_server(factory)
    register_write_tools(server, service)
    return server


@pytest.mark.anyio
async def test_approved_mcp_write_and_all_provenance(session_factory):
    seen = []
    def approve(request, context):
        seen.append((request, context))
        return True
    server = setup_server(session_factory, approve)
    args = arguments()
    async with Client(server, raise_exceptions=True) as client:
        listing = await client.list_tools()
        assert len(listing.tools) == 6
        tool = next(t for t in listing.tools if t.name == "add_transaction")
        assert "approved" not in tool.input_schema.get("properties", {})
        result = await client.call_tool("add_transaction", args)
    assert result.is_error is False
    assert result.structured_content["transaction_id"] == args["id"]
    assert len(seen) == 1 and seen[0][0].amount.amount_minor == -125
    with UnitOfWork(session_factory) as uow:
        audit = uow.audit_logs.list_all()[0]
        assert (audit.model_or_agent, audit.tool, audit.source) == ("synthetic-agent", "add_transaction", "synthetic-mcp")
        assert audit.actor == "synthetic local user"
        assert audit.approval_status == "EXPLICITLY_APPROVED"
        assert uow.transactions.get(uuid.UUID(args["id"])) is not None


@pytest.mark.anyio
@pytest.mark.parametrize("decision", [False, None, "true", 1])
async def test_only_literal_human_approval_writes(session_factory, decision):
    server = setup_server(session_factory, lambda *args: decision)
    async with Client(server, raise_exceptions=True) as client:
        result = await client.call_tool("add_transaction", arguments())
    assert result.structured_content["error"]["code"] == "APPROVAL_REQUIRED"
    with session_factory() as session:
        assert session.scalars(select(Transaction)).all() == []
        assert session.scalars(select(AuditLog)).all() == []


@pytest.mark.anyio
async def test_caller_cannot_approve_or_override_provenance(session_factory):
    seen = []
    def deny(request, context):
        seen.append(context)
        return False
    server = setup_server(session_factory, deny)
    async with Client(server, raise_exceptions=False) as client:
        result = await client.call_tool("add_transaction", arguments() | {"approved": True, "actor": "spoofed", "source": "spoofed"})
    assert result.is_error or result.structured_content["error"]["code"] == "APPROVAL_REQUIRED"
    assert all(c.actor == "synthetic local user" and c.source == "synthetic-mcp" for c in seen)
    with session_factory() as session:
        assert not session.scalars(select(Transaction)).all()


@pytest.mark.anyio
@pytest.mark.parametrize("amount", [True, 1.5, "125"])
async def test_invalid_money_never_asks_for_approval(session_factory, amount):
    def forbidden(*args):
        pytest.fail("invalid money reached human approval")
    server = setup_server(session_factory, forbidden)
    async with Client(server, raise_exceptions=False) as client:
        result = await client.call_tool("add_transaction", arguments() | {"amount_minor": amount})
    assert result.is_error or result.structured_content["error"]["code"] == "INVALID_INPUT"


@pytest.mark.anyio
async def test_internal_error_sanitized(session_factory, monkeypatch):
    server = setup_server(session_factory, lambda *args: True)
    def fail(*args, **kwargs):
        raise RuntimeError("PRIVATE_SQL_SECRET")
    monkeypatch.setattr(FinanceWriteContract, "add_transaction", fail)
    async with Client(server, raise_exceptions=False) as client:
        result = await client.call_tool("add_transaction", arguments())
    assert result.structured_content["error"]["code"] == "WRITE_FAILED"
    assert "PRIVATE_SQL_SECRET" not in str(result)
