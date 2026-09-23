"""Real stdio subprocess verification for the Step 18 MCP runtime entrypoint.

The child process receives a temporary HOME, so the production-shaped default
path is exercised without touching the user's real ~/PersonalOS-data.
"""
from __future__ import annotations

import os
import sys

import pytest
from mcp import Client, StdioServerParameters

READ_TOOLS={
    "get_net_worth",
    "get_available_capital",
    "get_tax_reserve",
    "get_goal_gap",
    "get_required_revenue",
}


@pytest.mark.anyio
async def test_runtime_entrypoint_over_real_stdio_subprocess(tmp_path):
    fake_home=tmp_path/"home"
    fake_home.mkdir()

    params=StdioServerParameters(
        command=sys.executable,
        args=["-m","personal_os.adapters.mcp.runtime_server"],
        env={**os.environ,"HOME":str(fake_home)},
    )

    async with Client(params,raise_exceptions=True) as client:
        listed=await client.list_tools()
        result=await client.call_tool(
            "get_net_worth",
            {"evaluation_time":"2026-09-22T12:00:00+00:00"},
        )

    assert {tool.name for tool in listed.tools}==READ_TOOLS

    # A brand-new runtime contains no currency-bearing facts. Finance v0.1
    # deliberately refuses to invent JPY (or any other currency), so an empty
    # Net Worth read is a domain error. The important Step 18 assertion is that
    # the real child process completed MCP tools/list + tools/call and surfaced
    # that domain condition through the protocol rather than failing transport.
    assert result.is_error is True
    assert result.structured_content is None
    assert result.content

    db=fake_home/"PersonalOS-data"/"personal_os.db"
    assert db.is_file()
    assert db.stat().st_mode & 0o777 == 0o600
    assert db.parent.stat().st_mode & 0o777 == 0o700


@pytest.mark.anyio
async def test_write_enabled_stdio_lists_tool_without_dialog(tmp_path):
    database = tmp_path / "explicit-runtime.db"
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "personal_os.adapters.mcp.runtime_server", "--enable-writes",
              "--database-path", str(database)],
        env=dict(os.environ),
    )
    async with Client(params, raise_exceptions=False) as client:
        listed = await client.list_tools()
        # Invalid input must terminate before any OS dialog or DB mutation.
        response = await client.call_tool("add_transaction", {
            "id": "not-a-uuid", "account_id": "not-a-uuid", "amount_minor": 1,
            "currency_code": "JPY", "occurred_at": "2026-01-01T00:00:00Z", "reason": "synthetic",
        })
    assert {tool.name for tool in listed.tools} == READ_TOOLS | {"add_transaction", "add_account", "import_bank_transactions", "add_metric", "add_financial_target", "add_monthly_target", "add_opening_balance"}
    assert response.structured_content["error"]["code"] == "INVALID_INPUT"
