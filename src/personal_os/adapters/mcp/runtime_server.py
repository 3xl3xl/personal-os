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

from personal_os.adapters.mcp.account_tools import register_account_tools
from personal_os.adapters.mcp.import_tools import register_import_tools
from personal_os.adapters.mcp.metric_tools import register_metric_tools
from personal_os.adapters.mcp.server import create_server
from personal_os.adapters.mcp.target_tools import register_target_tools
from personal_os.adapters.mcp.write_tools import register_write_tools
from personal_os.approval._account import confirm_account
from personal_os.approval._batch_import import confirm_import_batch
from personal_os.approval._metric import confirm_metric
from personal_os.approval._target import confirm_financial_target, confirm_monthly_target
from personal_os.approval.macos import confirm_transaction
from personal_os.services.account_write_contract import AccountWriteContract
from personal_os.services.approved_account_write import ApprovedAccountWrite
from personal_os.services.approved_import_write import ApprovedImportWrite
from personal_os.services.approved_metric_write import ApprovedMetricWrite
from personal_os.services.approved_target_write import ApprovedTargetWrite
from personal_os.services.approved_write import ApprovedTransactionWrite
from personal_os.services.metric_write_contract import MetricWriteContract
from personal_os.services.target_write_contract import TargetWriteContract
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
        account_service = ApprovedAccountWrite(
            AccountWriteContract(lambda: UnitOfWork(runtime.session_factory)),
            confirm_account, actor=getpass.getuser(),
            model_or_agent="personal-os-mcp", source="mcp:stdio",
        )
        register_account_tools(server, account_service)
        import_service = ApprovedImportWrite(
            lambda: UnitOfWork(runtime.session_factory),
            confirm_import_batch, actor=getpass.getuser(),
            model_or_agent="personal-os-mcp", source="mcp:stdio",
        )
        register_import_tools(server, import_service)
        metric_service = ApprovedMetricWrite(
            MetricWriteContract(lambda: UnitOfWork(runtime.session_factory)),
            confirm_metric, actor=getpass.getuser(),
            model_or_agent="personal-os-mcp", source="mcp:stdio",
        )
        register_metric_tools(server, metric_service)
        target_service = ApprovedTargetWrite(
            TargetWriteContract(lambda: UnitOfWork(runtime.session_factory)),
            confirm_financial_target, confirm_monthly_target, actor=getpass.getuser(),
            model_or_agent="personal-os-mcp", source="mcp:stdio",
        )
        register_target_tools(server, target_service)
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
