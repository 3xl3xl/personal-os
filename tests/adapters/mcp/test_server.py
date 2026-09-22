"""Step 15 MCP adapter boundary tests."""
from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path

import pytest
from mcp.server import MCPServer

from personal_os.adapters.mcp.server import _evaluation_time, create_server

UTC = dt.timezone.utc


class NeverUsedUow:
    def __enter__(self):
        raise AssertionError("not used by server construction")
    def __exit__(self, exc_type, exc, tb):
        return None


def test_official_sdk_server_is_constructed_without_touching_persistence():
    server=create_server(lambda: NeverUsedUow())
    assert isinstance(server,MCPServer)


def test_evaluation_time_requires_explicit_timezone_and_canonicalizes_utc():
    assert _evaluation_time("2026-09-22T21:00:00+09:00")==dt.datetime(2026,9,22,12,0,tzinfo=UTC)
    with pytest.raises(ValueError,match="timezone-aware"):
        _evaluation_time("2026-09-22T12:00:00")


def test_adapter_imports_sdk_but_core_does_not_import_mcp():
    adapter=Path("src/personal_os/adapters/mcp/server.py").read_text()
    assert "from mcp.server import MCPServer" in adapter
    for root in (Path("src/personal_os/domain"),Path("src/personal_os/repository"),Path("src/personal_os/services")):
        for path in root.rglob("*.py"):
            tree=ast.parse(path.read_text())
            imports=[]
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node,ast.ImportFrom) and node.module:
                    imports.append(node.module)
            assert not any(name=="mcp" or name.startswith("mcp.") for name in imports), path


def test_adapter_defines_only_the_five_read_tools():
    tree=ast.parse(Path("src/personal_os/adapters/mcp/server.py").read_text())
    names={
        node.name for node in ast.walk(tree)
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))
        and any(
            isinstance(dec,ast.Call)
            and isinstance(dec.func,ast.Attribute)
            and dec.func.attr=="tool"
            for dec in node.decorator_list
        )
    }
    assert names=={"get_net_worth","get_available_capital","get_tax_reserve","get_goal_gap","get_required_revenue"}
