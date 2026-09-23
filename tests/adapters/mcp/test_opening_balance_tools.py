"""MCP -> human approval boundary -> opening balance write contract -> real temporary SQLite."""
import uuid

import pytest
from mcp import Client
from sqlalchemy import select

from personal_os.adapters.mcp.account_tools import register_account_tools
from personal_os.adapters.mcp.opening_balance_tools import register_opening_balance_tools
from personal_os.adapters.mcp.server import create_server
from personal_os.database.schema import AuditLog, Transaction
from personal_os.repository.unit_of_work import UnitOfWork
from personal_os.services.account_write_contract import AccountWriteContract
from personal_os.services.approved_account_write import ApprovedAccountWrite
from personal_os.services.approved_opening_balance_write import ApprovedOpeningBalanceWrite
from personal_os.services.opening_balance_write_contract import OpeningBalanceWriteContract
from tests.services.test_account_write_contract import request as account_request, context as account_context
from tests.services.test_opening_balance_write_contract import NOW, TRANSACTION_ID, ACCOUNT_ID


def arguments():
    return dict(id=str(TRANSACTION_ID), account_id=str(ACCOUNT_ID), amount_minor=500_000_00,
                currency_code="JPY", occurred_at=NOW.isoformat(), reason="synthetic reason")


def setup_server(session_factory, approval, *, seed_account=True):
    factory = lambda: UnitOfWork(session_factory)
    if seed_account:
        AccountWriteContract(factory).add_account(account_request(id=ACCOUNT_ID), context=account_context())
    service = ApprovedOpeningBalanceWrite(OpeningBalanceWriteContract(factory), approval,
                                          actor="synthetic local user", model_or_agent="synthetic-agent", source="synthetic-mcp")
    server = create_server(factory)
    account_service = ApprovedAccountWrite(AccountWriteContract(factory), lambda *a: True,
                                           actor="synthetic local user", model_or_agent="synthetic-agent", source="synthetic-mcp")
    register_account_tools(server, account_service)
    register_opening_balance_tools(server, service)
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
        tool = next(t for t in listing.tools if t.name == "add_opening_balance")
        assert "approved" not in tool.input_schema.get("properties", {})
        result = await client.call_tool("add_opening_balance", args)
    assert result.is_error is False
    assert result.structured_content["transaction_id"] == args["id"]
    assert len(seen) == 1 and seen[0][0].account_id == ACCOUNT_ID
    with UnitOfWork(session_factory) as uow:
        audits = [a for a in uow.audit_logs.list_all() if a.action == "add_opening_balance"]
        assert len(audits) == 1
        audit = audits[0]
        assert (audit.model_or_agent, audit.tool, audit.source) == ("synthetic-agent", "add_opening_balance", "synthetic-mcp")
        assert audit.actor == "synthetic local user"
        assert audit.approval_status == "EXPLICITLY_APPROVED"
        stored = uow.transactions.get(uuid.UUID(args["id"]))
        assert stored is not None and stored.transaction_type.value == "OPENING_BALANCE"


@pytest.mark.anyio
@pytest.mark.parametrize("decision", [False, None, "true", 1])
async def test_only_literal_human_approval_writes(session_factory, decision):
    server = setup_server(session_factory, lambda *args: decision)
    async with Client(server, raise_exceptions=True) as client:
        result = await client.call_tool("add_opening_balance", arguments())
    assert result.structured_content["error"]["code"] == "APPROVAL_REQUIRED"
    with session_factory() as session:
        assert session.scalars(select(Transaction)).all() == []
        assert session.scalars(select(AuditLog).where(AuditLog.action == "add_opening_balance")).all() == []


@pytest.mark.anyio
async def test_caller_cannot_approve_or_override_provenance(session_factory):
    seen = []
    def deny(request, context):
        seen.append(context)
        return False
    server = setup_server(session_factory, deny)
    async with Client(server, raise_exceptions=False) as client:
        result = await client.call_tool("add_opening_balance", arguments() | {"approved": True, "actor": "spoofed", "source": "spoofed"})
    assert result.is_error or result.structured_content["error"]["code"] == "APPROVAL_REQUIRED"
    assert all(c.actor == "synthetic local user" and c.source == "synthetic-mcp" for c in seen)
    with session_factory() as session:
        assert not session.scalars(select(Transaction)).all()


@pytest.mark.anyio
async def test_missing_account_reported_as_invalid_input(session_factory):
    # Unlike a malformed/unparseable argument (which fails before the Service
    # is ever called), a missing account is a WriteReferenceError raised
    # inside OpeningBalanceWriteContract's UoW block -- which only runs AFTER
    # ApprovedOpeningBalanceWrite has already obtained approval. So the
    # dialog does fire here; only the eventual write is rejected.
    server = setup_server(session_factory, lambda *args: True, seed_account=False)
    async with Client(server, raise_exceptions=False) as client:
        result = await client.call_tool("add_opening_balance", arguments())
    assert result.is_error or result.structured_content["error"]["code"] == "INVALID_INPUT"
    with session_factory() as session:
        assert not session.scalars(select(Transaction)).all()


@pytest.mark.anyio
async def test_currency_mismatch_reported(session_factory):
    server = setup_server(session_factory, lambda *args: True)
    async with Client(server, raise_exceptions=False) as client:
        result = await client.call_tool("add_opening_balance", arguments() | {"currency_code": "USD"})
    assert result.structured_content["error"]["code"] == "CURRENCY_MISMATCH"
    with session_factory() as session:
        assert not session.scalars(select(Transaction)).all()


@pytest.mark.anyio
async def test_internal_error_sanitized(session_factory, monkeypatch):
    server = setup_server(session_factory, lambda *args: True)
    def fail(*args, **kwargs):
        raise RuntimeError("PRIVATE_SQL_SECRET")
    monkeypatch.setattr(OpeningBalanceWriteContract, "add_opening_balance", fail)
    async with Client(server, raise_exceptions=False) as client:
        result = await client.call_tool("add_opening_balance", arguments())
    assert result.structured_content["error"]["code"] == "WRITE_FAILED"
    assert "PRIVATE_SQL_SECRET" not in str(result)


@pytest.mark.anyio
async def test_second_opening_balance_on_same_account_reported_as_invalid_input(session_factory):
    server = setup_server(session_factory, lambda *args: True)
    args = arguments()
    async with Client(server, raise_exceptions=True) as client:
        first = await client.call_tool("add_opening_balance", args)
        assert first.is_error is False
        second = await client.call_tool("add_opening_balance", args | {"id": str(uuid.uuid4())})
    assert second.structured_content["error"]["code"] == "INVALID_INPUT"
    with session_factory() as session:
        assert len(session.scalars(select(Transaction)).all()) == 1
