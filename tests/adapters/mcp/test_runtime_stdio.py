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
    assert result.is_error is False
    assert result.structured_content=={
        "metric_key":"net_worth",
        "value":{"amount_minor":0,"currency_code":None},
        "as_of":"2026-09-22T12:00:00+00:00",
        "kind":"DERIVED",
    }

    db=fake_home/"PersonalOS-data"/"personal_os.db"
    assert db.is_file()
    assert db.stat().st_mode & 0o777 == 0o600
    assert db.parent.stat().st_mode & 0o777 == 0o700
