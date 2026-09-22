"""Local-private MCP runtime entrypoint.

This composition root is the only adapter that binds the read-only MCP server
to the real local Runtime database. Importing it has no filesystem side effects.
"""
from __future__ import annotations

from pathlib import Path

from mcp.server import MCPServer

from personal_os.adapters.mcp.server import create_server
from personal_os.repository.unit_of_work import UnitOfWork
from personal_os.runtime import DEFAULT_DATABASE_PATH, Runtime, initialize_runtime


def create_runtime_server(
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> tuple[MCPServer, Runtime]:
    """Initialize the chosen private DB and bind the five read tools to it."""
    runtime = initialize_runtime(database_path)
    server = create_server(lambda: UnitOfWork(runtime.session_factory))
    return server, runtime


def main() -> int:
    """Serve the local Personal OS Finance reads over MCP stdio."""
    server, runtime = create_runtime_server()
    try:
        server.run()
    finally:
        runtime.engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
