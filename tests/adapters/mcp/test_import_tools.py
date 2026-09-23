"""MCP -> human batch-approval boundary -> import pipeline -> real temporary SQLite."""
import uuid

import pytest
from mcp import Client
from sqlalchemy import select

from personal_os.adapters.mcp.import_tools import register_import_tools
from personal_os.adapters.mcp.server import create_server
from personal_os.database.schema import AuditLog, ExternalTransactionLink, Transaction
from personal_os.repository.unit_of_work import UnitOfWork
from personal_os.services.approved_import_write import ApprovedImportWrite
from tests.services.test_write_contract import ACCOUNT, NOW


def entry(**changes):
    values = dict(source="FREEE", external_office_id="office-1", external_account_id="wallet-1",
                  external_transaction_id="line-1", account_id=str(ACCOUNT.id),
                  amount_minor=-500, currency_code="JPY", occurred_at=NOW.isoformat(),
                  description="synthetic coffee")
    values.update(changes)
    return values


def setup_server(session_factory, confirm):
    with UnitOfWork(session_factory) as uow:
        uow.accounts.add(ACCOUNT)
        uow.commit()
    factory = lambda: UnitOfWork(session_factory)
    service = ApprovedImportWrite(factory, confirm, actor="synthetic local user",
                                  model_or_agent="synthetic-agent", source="synthetic-mcp")
    server = create_server(factory)
    register_import_tools(server, service)
    return server


@pytest.mark.anyio
async def test_approved_line_written_and_all_provenance(session_factory):
    seen = []
    def confirm(candidates):
        seen.append(candidates)
        return {candidates[0].candidate_id}
    server = setup_server(session_factory, confirm)
    async with Client(server, raise_exceptions=True) as client:
        listing = await client.list_tools()
        assert any(t.name == "import_bank_transactions" for t in listing.tools)
        result = await client.call_tool("import_bank_transactions", {"transactions": [entry()], "reason": "synthetic reason"})
    assert result.is_error is False
    assert result.structured_content["imported"] == [
        {"external_transaction_id": "line-1",
         "transaction_id": result.structured_content["imported"][0]["transaction_id"],
         "audit_id": result.structured_content["imported"][0]["audit_id"]}
    ]
    assert result.structured_content["skipped_external_transaction_ids"] == []
    assert len(seen) == 1
    with session_factory() as session:
        audit = session.scalars(select(AuditLog)).one()
        assert (audit.model_or_agent, audit.tool, audit.source) == ("synthetic-agent", "import_freee_transaction", "synthetic-mcp")
        assert audit.actor == "synthetic local user"
        assert session.scalars(select(Transaction)).one() is not None
        link = session.scalars(select(ExternalTransactionLink)).one()
        assert (link.source, link.external_transaction_id) == ("FREEE", "line-1")


@pytest.mark.anyio
async def test_invalid_input_never_opens_the_dialog(session_factory):
    def forbidden(candidates):
        pytest.fail("invalid input reached the batch dialog")
    server = setup_server(session_factory, forbidden)
    async with Client(server, raise_exceptions=False) as client:
        result = await client.call_tool("import_bank_transactions", {"transactions": [entry(account_id="not-a-uuid")], "reason": "synthetic"})
    assert result.is_error or result.structured_content["error"]["code"] == "INVALID_INPUT"
    with session_factory() as session:
        assert session.scalars(select(Transaction)).all() == []


@pytest.mark.anyio
async def test_cancelled_dialog_writes_nothing_and_reports_skipped(session_factory):
    server = setup_server(session_factory, lambda candidates: set())
    async with Client(server, raise_exceptions=True) as client:
        result = await client.call_tool("import_bank_transactions", {"transactions": [entry()], "reason": "synthetic"})
    assert result.structured_content["imported"] == []
    assert result.structured_content["skipped_external_transaction_ids"] == ["line-1"]
    with session_factory() as session:
        assert session.scalars(select(Transaction)).all() == []


@pytest.mark.anyio
async def test_second_call_same_identity_is_not_reoffered(session_factory):
    server = setup_server(session_factory, lambda candidates: {candidates[0].candidate_id})
    async with Client(server, raise_exceptions=True) as client:
        first = await client.call_tool("import_bank_transactions", {"transactions": [entry()], "reason": "synthetic"})
        assert first.structured_content["imported"]
        def forbidden(candidates):
            pytest.fail("already-imported unchanged line was re-offered for approval")
        second_server = setup_server_noop_seed(session_factory, forbidden)
    async with Client(second_server, raise_exceptions=True) as client:
        second = await client.call_tool("import_bank_transactions", {"transactions": [entry()], "reason": "synthetic"})
    assert second.structured_content["imported"] == []
    assert second.structured_content["skipped_external_transaction_ids"] == ["line-1"]
    with session_factory() as session:
        assert len(session.scalars(select(Transaction)).all()) == 1


def setup_server_noop_seed(session_factory, confirm):
    """Like setup_server but does not re-add ACCOUNT (already seeded)."""
    factory = lambda: UnitOfWork(session_factory)
    service = ApprovedImportWrite(factory, confirm, actor="synthetic local user",
                                  model_or_agent="synthetic-agent", source="synthetic-mcp")
    server = create_server(factory)
    register_import_tools(server, service)
    return server


@pytest.mark.anyio
async def test_internal_error_sanitized_and_admits_partial_write(session_factory, monkeypatch):
    server = setup_server(session_factory, lambda candidates: {candidates[0].candidate_id})
    def fail(*args, **kwargs):
        raise RuntimeError("PRIVATE_SQL_SECRET")
    monkeypatch.setattr(ApprovedImportWrite, "import_batch", fail)
    async with Client(server, raise_exceptions=False) as client:
        result = await client.call_tool("import_bank_transactions", {"transactions": [entry()], "reason": "synthetic"})
    assert result.structured_content["error"]["code"] == "WRITE_FAILED"
    assert "PRIVATE_SQL_SECRET" not in str(result)
    assert "already written earlier in this call" in result.structured_content["error"]["message"]
