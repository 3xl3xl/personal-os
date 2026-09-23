"""MCP -> human approval boundary -> account write contract -> real temporary SQLite."""
import uuid

import pytest
from mcp import Client
from sqlalchemy import select

from personal_os.adapters.mcp.account_tools import register_account_tools
from personal_os.adapters.mcp.server import create_server
from personal_os.database.schema import Account, AuditLog
from personal_os.repository.unit_of_work import UnitOfWork
from personal_os.services.account_write_contract import AccountWriteContract
from personal_os.services.approved_account_write import ApprovedAccountWrite
from tests.services.test_account_write_contract import NOW


def arguments():
    return dict(id=str(uuid.uuid4()), name="SMBC 普通口座", account_type="CASH",
                currency_code="JPY", opened_at=NOW.isoformat(), reason="synthetic reason")


def setup_server(session_factory, approval):
    factory = lambda: UnitOfWork(session_factory)
    service = ApprovedAccountWrite(AccountWriteContract(factory), approval,
                                   actor="synthetic local user", model_or_agent="synthetic-agent", source="synthetic-mcp")
    server = create_server(factory)
    register_account_tools(server, service)
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
        tool = next(t for t in listing.tools if t.name == "add_account")
        assert "approved" not in tool.input_schema.get("properties", {})
        result = await client.call_tool("add_account", args)
    assert result.is_error is False
    assert result.structured_content["account_id"] == args["id"]
    assert len(seen) == 1 and seen[0][0].name == "SMBC 普通口座"
    with UnitOfWork(session_factory) as uow:
        audit = uow.audit_logs.list_all()[0]
        assert (audit.model_or_agent, audit.tool, audit.source) == ("synthetic-agent", "add_account", "synthetic-mcp")
        assert audit.actor == "synthetic local user"
        assert audit.approval_status == "EXPLICITLY_APPROVED"
        assert uow.accounts.get(uuid.UUID(args["id"])) is not None


@pytest.mark.anyio
@pytest.mark.parametrize("decision", [False, None, "true", 1])
async def test_only_literal_human_approval_writes(session_factory, decision):
    server = setup_server(session_factory, lambda *args: decision)
    async with Client(server, raise_exceptions=True) as client:
        result = await client.call_tool("add_account", arguments())
    assert result.structured_content["error"]["code"] == "APPROVAL_REQUIRED"
    with session_factory() as session:
        assert session.scalars(select(Account)).all() == []
        assert session.scalars(select(AuditLog)).all() == []


@pytest.mark.anyio
async def test_caller_cannot_approve_or_override_provenance(session_factory):
    seen = []
    def deny(request, context):
        seen.append(context)
        return False
    server = setup_server(session_factory, deny)
    async with Client(server, raise_exceptions=False) as client:
        result = await client.call_tool("add_account", arguments() | {"approved": True, "actor": "spoofed", "source": "spoofed"})
    assert result.is_error or result.structured_content["error"]["code"] == "APPROVAL_REQUIRED"
    assert all(c.actor == "synthetic local user" and c.source == "synthetic-mcp" for c in seen)
    with session_factory() as session:
        assert not session.scalars(select(Account)).all()


@pytest.mark.anyio
async def test_invalid_account_type_never_asks_for_approval(session_factory):
    def forbidden(*args):
        pytest.fail("invalid account_type reached human approval")
    server = setup_server(session_factory, forbidden)
    async with Client(server, raise_exceptions=False) as client:
        result = await client.call_tool("add_account", arguments() | {"account_type": "NOT_A_TYPE"})
    assert result.is_error or result.structured_content["error"]["code"] == "INVALID_INPUT"


@pytest.mark.anyio
async def test_internal_error_sanitized(session_factory, monkeypatch):
    server = setup_server(session_factory, lambda *args: True)
    def fail(*args, **kwargs):
        raise RuntimeError("PRIVATE_SQL_SECRET")
    monkeypatch.setattr(AccountWriteContract, "add_account", fail)
    async with Client(server, raise_exceptions=False) as client:
        result = await client.call_tool("add_account", arguments())
    assert result.structured_content["error"]["code"] == "WRITE_FAILED"
    assert "PRIVATE_SQL_SECRET" not in str(result)


@pytest.mark.anyio
async def test_duplicate_account_id_reported_as_invalid_input(session_factory):
    server = setup_server(session_factory, lambda *args: True)
    args = arguments()
    async with Client(server, raise_exceptions=True) as client:
        first = await client.call_tool("add_account", args)
        assert first.is_error is False
        second = await client.call_tool("add_account", args)
    assert second.structured_content["error"]["code"] == "INVALID_INPUT"
    with session_factory() as session:
        assert len(session.scalars(select(Account)).all()) == 1
