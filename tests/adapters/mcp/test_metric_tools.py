"""MCP -> human approval boundary -> metric write contract -> real temporary SQLite."""
import uuid

import pytest
from mcp import Client
from sqlalchemy import select

from personal_os.adapters.mcp.metric_tools import register_metric_tools
from personal_os.adapters.mcp.server import create_server
from personal_os.database.schema import AuditLog, FinancialMetric
from personal_os.repository.unit_of_work import UnitOfWork
from personal_os.services.metric_write_contract import MetricWriteContract
from personal_os.services.approved_metric_write import ApprovedMetricWrite


def arguments():
    return dict(id=str(uuid.uuid4()), key="net_worth_2026_goal",
                display_name="ヨーロッパ旅行資金", reason="synthetic reason")


def setup_server(session_factory, approval):
    factory = lambda: UnitOfWork(session_factory)
    service = ApprovedMetricWrite(MetricWriteContract(factory), approval,
                                  actor="synthetic local user", model_or_agent="synthetic-agent", source="synthetic-mcp")
    server = create_server(factory)
    register_metric_tools(server, service)
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
        tool = next(t for t in listing.tools if t.name == "add_metric")
        assert "approved" not in tool.input_schema.get("properties", {})
        result = await client.call_tool("add_metric", args)
    assert result.is_error is False
    assert result.structured_content["metric_key"] == args["key"]
    assert len(seen) == 1 and seen[0][0].key == "net_worth_2026_goal"
    with UnitOfWork(session_factory) as uow:
        audit = uow.audit_logs.list_all()[0]
        assert (audit.model_or_agent, audit.tool, audit.source) == ("synthetic-agent", "add_metric", "synthetic-mcp")
        assert audit.actor == "synthetic local user"
        assert audit.approval_status == "EXPLICITLY_APPROVED"
        assert uow.financial_metrics.get_by_key(args["key"]) is not None


@pytest.mark.anyio
@pytest.mark.parametrize("decision", [False, None, "true", 1])
async def test_only_literal_human_approval_writes(session_factory, decision):
    server = setup_server(session_factory, lambda *args: decision)
    async with Client(server, raise_exceptions=True) as client:
        result = await client.call_tool("add_metric", arguments())
    assert result.structured_content["error"]["code"] == "APPROVAL_REQUIRED"
    with session_factory() as session:
        assert session.scalars(select(FinancialMetric)).all() == []
        assert session.scalars(select(AuditLog)).all() == []


@pytest.mark.anyio
async def test_caller_cannot_approve_or_override_provenance(session_factory):
    seen = []
    def deny(request, context):
        seen.append(context)
        return False
    server = setup_server(session_factory, deny)
    async with Client(server, raise_exceptions=False) as client:
        result = await client.call_tool("add_metric", arguments() | {"approved": True, "actor": "spoofed", "source": "spoofed"})
    assert result.is_error or result.structured_content["error"]["code"] == "APPROVAL_REQUIRED"
    assert all(c.actor == "synthetic local user" and c.source == "synthetic-mcp" for c in seen)
    with session_factory() as session:
        assert not session.scalars(select(FinancialMetric)).all()


@pytest.mark.anyio
async def test_blank_display_name_never_asks_for_approval(session_factory):
    def forbidden(*args):
        pytest.fail("invalid display_name reached human approval")
    server = setup_server(session_factory, forbidden)
    async with Client(server, raise_exceptions=False) as client:
        result = await client.call_tool("add_metric", arguments() | {"display_name": ""})
    assert result.is_error or result.structured_content["error"]["code"] == "INVALID_INPUT"


@pytest.mark.anyio
async def test_internal_error_sanitized(session_factory, monkeypatch):
    server = setup_server(session_factory, lambda *args: True)
    def fail(*args, **kwargs):
        raise RuntimeError("PRIVATE_SQL_SECRET")
    monkeypatch.setattr(MetricWriteContract, "add_metric", fail)
    async with Client(server, raise_exceptions=False) as client:
        result = await client.call_tool("add_metric", arguments())
    assert result.structured_content["error"]["code"] == "WRITE_FAILED"
    assert "PRIVATE_SQL_SECRET" not in str(result)


@pytest.mark.anyio
async def test_duplicate_metric_key_reported_as_invalid_input(session_factory):
    server = setup_server(session_factory, lambda *args: True)
    args = arguments()
    async with Client(server, raise_exceptions=True) as client:
        first = await client.call_tool("add_metric", args)
        assert first.is_error is False
        second = await client.call_tool("add_metric", args | {"id": str(uuid.uuid4())})
    assert second.structured_content["error"]["code"] == "INVALID_INPUT"
    with session_factory() as session:
        assert len(session.scalars(select(FinancialMetric)).all()) == 1
