"""MCP -> human approval boundary -> target write contract -> real temporary
SQLite, covering both add_financial_target and add_monthly_target tools."""
import uuid

import pytest
from mcp import Client
from sqlalchemy import select

from personal_os.adapters.mcp.server import create_server
from personal_os.adapters.mcp.target_tools import register_target_tools
from personal_os.database.schema import AuditLog, FinancialMetric, FinancialTarget, MonthlyTarget
from personal_os.domain.records import FinancialMetricRecord
from personal_os.repository.unit_of_work import UnitOfWork
from personal_os.services.approved_target_write import ApprovedTargetWrite
from personal_os.services.target_write_contract import TargetWriteContract
from tests.services.test_target_write_contract import NOW

METRIC_KEY = "net_worth_2026_goal"


def financial_arguments():
    return dict(id=str(uuid.uuid4()), metric_key=METRIC_KEY,
                target_amount_minor=10_000_000, currency_code="JPY",
                effective_from=NOW.isoformat(), reason="synthetic reason")


def monthly_arguments():
    return dict(id=str(uuid.uuid4()), metric_key=METRIC_KEY, year=2026, month=3,
                target_amount_minor=500_000, currency_code="JPY",
                effective_from=NOW.isoformat(), reason="synthetic reason")


def seed_metric(session_factory):
    with UnitOfWork(session_factory) as uow:
        uow.financial_metrics.add(FinancialMetricRecord(
            id=uuid.uuid4(), key=METRIC_KEY, display_name="synthetic KPI", created_at=NOW,
        ))
        uow.commit()


def setup_server(session_factory, approve_financial, approve_monthly):
    factory = lambda: UnitOfWork(session_factory)
    service = ApprovedTargetWrite(TargetWriteContract(factory), approve_financial, approve_monthly,
                                  actor="synthetic local user", model_or_agent="synthetic-agent", source="synthetic-mcp")
    server = create_server(factory)
    register_target_tools(server, service)
    return server


@pytest.mark.anyio
async def test_approved_financial_target_write_and_provenance(session_factory):
    seed_metric(session_factory)
    seen = []
    def approve(request, context):
        seen.append((request, context))
        return True
    server = setup_server(session_factory, approve, lambda *a: pytest.fail("wrong callable used"))
    args = financial_arguments()
    async with Client(server, raise_exceptions=True) as client:
        listing = await client.list_tools()
        names = {t.name for t in listing.tools}
        assert {"add_financial_target", "add_monthly_target"} <= names
        result = await client.call_tool("add_financial_target", args)
    assert result.is_error is False
    assert result.structured_content["target_id"] == args["id"]
    assert len(seen) == 1
    with UnitOfWork(session_factory) as uow:
        audit = uow.audit_logs.list_all()[0]
        assert (audit.model_or_agent, audit.tool, audit.source) == ("synthetic-agent", "add_financial_target", "synthetic-mcp")
        assert uow.financial_targets.list_by_metric(METRIC_KEY)


@pytest.mark.anyio
async def test_approved_monthly_target_write_and_provenance(session_factory):
    seed_metric(session_factory)
    seen = []
    def approve(request, context):
        seen.append((request, context))
        return True
    server = setup_server(session_factory, lambda *a: pytest.fail("wrong callable used"), approve)
    args = monthly_arguments()
    async with Client(server, raise_exceptions=True) as client:
        result = await client.call_tool("add_monthly_target", args)
    assert result.is_error is False
    assert result.structured_content["target_id"] == args["id"]
    assert len(seen) == 1
    with UnitOfWork(session_factory) as uow:
        assert uow.monthly_targets.list_by_metric_year_month(METRIC_KEY, 2026, 3)


@pytest.mark.anyio
@pytest.mark.parametrize("decision", [False, None, "true", 1])
async def test_only_literal_human_approval_writes(session_factory, decision):
    seed_metric(session_factory)
    server = setup_server(session_factory, lambda *a: decision, lambda *a: decision)
    async with Client(server, raise_exceptions=True) as client:
        financial = await client.call_tool("add_financial_target", financial_arguments())
        monthly = await client.call_tool("add_monthly_target", monthly_arguments())
    assert financial.structured_content["error"]["code"] == "APPROVAL_REQUIRED"
    assert monthly.structured_content["error"]["code"] == "APPROVAL_REQUIRED"
    with session_factory() as session:
        assert session.scalars(select(FinancialTarget)).all() == []
        assert session.scalars(select(MonthlyTarget)).all() == []
        assert session.scalars(select(AuditLog)).all() == []


@pytest.mark.anyio
async def test_unknown_metric_key_reported_as_invalid_input(session_factory):
    """WriteReferenceError is a post-approval DB-existence check (same
    pattern as the duplicate-id check in test_account_tools.py) -- the human
    dialog IS shown, then the write is rejected with no rows written."""
    server = setup_server(session_factory, lambda *a: True, lambda *a: True)
    async with Client(server, raise_exceptions=False) as client:
        result = await client.call_tool("add_financial_target", financial_arguments() | {"metric_key": "does_not_exist"})
    assert result.is_error or result.structured_content["error"]["code"] == "INVALID_INPUT"
    with session_factory() as session:
        assert session.scalars(select(FinancialTarget)).all() == []


@pytest.mark.anyio
async def test_month_out_of_range_never_asks_for_approval(session_factory):
    seed_metric(session_factory)
    def forbidden(*args):
        pytest.fail("out-of-range month reached human approval")
    server = setup_server(session_factory, forbidden, forbidden)
    async with Client(server, raise_exceptions=False) as client:
        result = await client.call_tool("add_monthly_target", monthly_arguments() | {"month": 13})
    assert result.is_error or result.structured_content["error"]["code"] == "INVALID_INPUT"


@pytest.mark.anyio
async def test_internal_error_sanitized(session_factory, monkeypatch):
    seed_metric(session_factory)
    server = setup_server(session_factory, lambda *a: True, lambda *a: True)
    def fail(*args, **kwargs):
        raise RuntimeError("PRIVATE_SQL_SECRET")
    monkeypatch.setattr(TargetWriteContract, "add_financial_target", fail)
    async with Client(server, raise_exceptions=False) as client:
        result = await client.call_tool("add_financial_target", financial_arguments())
    assert result.structured_content["error"]["code"] == "WRITE_FAILED"
    assert "PRIVATE_SQL_SECRET" not in str(result)


@pytest.mark.anyio
async def test_duplicate_effective_from_reported_as_invalid_input(session_factory):
    seed_metric(session_factory)
    server = setup_server(session_factory, lambda *a: True, lambda *a: True)
    args = financial_arguments()
    async with Client(server, raise_exceptions=True) as client:
        first = await client.call_tool("add_financial_target", args)
        assert first.is_error is False
        second = await client.call_tool("add_financial_target", args | {"id": str(uuid.uuid4())})
    assert second.structured_content["error"]["code"] == "INVALID_INPUT"
    with session_factory() as session:
        assert len(session.scalars(select(FinancialTarget)).all()) == 1
