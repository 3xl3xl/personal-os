"""Step 18 runtime MCP composition tests."""
from __future__ import annotations

import os
import subprocess
import sys

import pytest
from mcp import Client

from personal_os.adapters.mcp.runtime_server import create_runtime_server

READ_TOOLS={
    "get_net_worth",
    "get_available_capital",
    "get_tax_reserve",
    "get_goal_gap",
    "get_required_revenue",
}


def test_import_has_no_runtime_storage_side_effect(tmp_path):
    fake_home=tmp_path/"home"
    fake_home.mkdir()
    result=subprocess.run(
        [sys.executable,"-c","import personal_os.adapters.mcp.runtime_server"],
        env={**os.environ,"HOME":str(fake_home)},
        capture_output=True,text=True,
    )
    assert result.returncode==0,result.stderr
    assert not (fake_home/"PersonalOS-data").exists()


@pytest.mark.anyio
async def test_runtime_server_binds_real_runtime_repositories_to_five_read_tools(tmp_path):
    path=tmp_path/"private"/"personal_os.db"
    server,runtime=create_runtime_server(path)
    try:
        async with Client(server,raise_exceptions=True) as client:
            listed=await client.list_tools()
        assert {tool.name for tool in listed.tools}==READ_TOOLS
        assert path.is_file()
    finally:
        runtime.engine.dispose()


def test_runtime_entrypoint_uses_stdio_run_and_disposes_engine(monkeypatch,tmp_path):
    import personal_os.adapters.mcp.runtime_server as entrypoint

    server,runtime=create_runtime_server(tmp_path/"personal_os.db")
    called=[]
    monkeypatch.setattr(entrypoint,"create_runtime_server",lambda *args, **kwargs:(server,runtime))
    monkeypatch.setattr(server,"run",lambda:called.append("run"))
    disposed=[]
    monkeypatch.setattr(runtime.engine,"dispose",lambda:disposed.append("dispose"))

    assert entrypoint.main([])==0
    assert called==["run"]
    assert disposed==["dispose"]
