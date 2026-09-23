"""Local-private MCP runtime entrypoint.

The default server is read-only; explicit write enablement requires a local
macOS confirmation for each transaction. This root binds services to Runtime.
Importing it has no filesystem side effects.
"""
from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from mcp.server import MCPServer

from personal_os.adapters.mcp.server import create_server
from personal_os.adapters.mcp.write_tools import register_write_tools
from personal_os.approval.macos import confirm_transaction
from personal_os.services.approved_write import ApprovedTransactionWrite
from personal_os.services.write_contract import FinanceWriteContract
from personal_os.repository.unit_of_work import UnitOfWork
from personal_os.runtime import DEFAULT_DATABASE_PATH, Runtime, initialize_runtime


def create_runtime_server(
    database_path: Path = DEFAULT_DATABASE_PATH, *, enable_writes: bool = False,
) -> tuple[MCPServer, Runtime]:
    """Initialize the chosen DB; optionally add locally approved writes."""
    runtime = initialize_runtime(database_path)
    server = create_server(lambda: UnitOfWork(runtime.session_factory))
    if enable_writes:
        service = ApprovedTransactionWrite(
            FinanceWriteContract(lambda: UnitOfWork(runtime.session_factory)),
            confirm_transaction, actor=getpass.getuser(),
            model_or_agent="personal-os-mcp", source="mcp:stdio",
        )
        register_write_tools(server, service)
    return server, runtime


def main(argv: list[str] | None = None) -> int:
    """Serve local Finance over stdio, with opt-in human-approved writes."""
    parser = argparse.ArgumentParser(description="Personal OS local MCP server")
    parser.add_argument("--database-path", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--enable-writes", action="store_true", help="Enable add_transaction with local macOS confirmation for every request")
    args = parser.parse_args(argv)
    server, runtime = create_runtime_server(args.database_path, enable_writes=args.enable_writes)
    try:
        server.run()
    finally:
        runtime.engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
