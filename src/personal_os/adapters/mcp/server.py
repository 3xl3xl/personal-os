"""Official MCP SDK adapter for Personal OS Finance v0.1 read operations.

Protocol translation only: business calculations and permissions remain in Core.
The caller supplies a Unit-of-Work factory, so this adapter does not choose or
create a runtime database.
"""
from __future__ import annotations

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

from mcp.server import MCPServer

from personal_os.services import reads
from personal_os.services.reads import UnitOfWorkFactory


def _evaluation_time(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("evaluation_time must be timezone-aware ISO 8601")
    return parsed.astimezone(dt.timezone.utc)


def _money(value: Any) -> dict[str, Any]:
    return {"amount_minor": value.amount_minor, "currency_code": value.currency_code}


def _finance_value(value: Any) -> dict[str, Any]:
    return {
        "metric_key": value.metric_key,
        "value": _money(value.value),
        "as_of": value.as_of.isoformat(),
        "kind": value.kind.value,
    }


def _monthly_value(value: Any) -> dict[str, Any]:
    return {
        "metric_key": value.metric_key,
        "year": value.year,
        "month": value.month,
        "target": _money(value.target),
        "actual": _money(value.actual),
        "variance": _money(value.variance),
        "required": _money(value.required),
        "as_of": value.as_of.isoformat(),
        "target_kind": value.target_kind.value,
        "actual_kind": value.actual_kind.value,
        "variance_kind": value.variance_kind.value,
        "required_kind": value.required_kind.value,
    }


def create_server(uow_factory: UnitOfWorkFactory) -> MCPServer:
    """Create a read-only MCP server over an injected Personal OS UoW factory."""
    server = MCPServer("Personal OS Finance")

    @server.tool()
    def get_net_worth(evaluation_time: str) -> dict[str, Any]:
        """Return derived net worth at a timezone-aware ISO 8601 evaluation time."""
        return _finance_value(reads.get_net_worth(uow_factory, evaluation_time=_evaluation_time(evaluation_time)))

    @server.tool()
    def get_available_capital(evaluation_time: str) -> dict[str, Any]:
        """Return derived available capital at a timezone-aware ISO 8601 evaluation time."""
        return _finance_value(reads.get_available_capital(uow_factory, evaluation_time=_evaluation_time(evaluation_time)))

    @server.tool()
    def get_tax_reserve(evaluation_time: str) -> dict[str, Any]:
        """Return capital currently reserved in TAX_RESERVE buckets."""
        return _finance_value(reads.get_tax_reserve(uow_factory, evaluation_time=_evaluation_time(evaluation_time)))

    @server.tool()
    def get_goal_gap(metric_key: str, evaluation_time: str) -> dict[str, Any]:
        """Return the signed target-minus-actual gap for a metric."""
        return _finance_value(
            reads.get_goal_gap(
                uow_factory,
                metric_key=metric_key,
                evaluation_time=_evaluation_time(evaluation_time),
            )
        )

    @server.tool()
    def get_required_revenue(
        metric_key: str,
        evaluation_time: str,
        business_timezone: str,
    ) -> dict[str, Any]:
        """Return the current month's target, actual, variance, and required revenue."""
        return _monthly_value(
            reads.get_required_revenue(
                uow_factory,
                metric_key=metric_key,
                evaluation_time=_evaluation_time(evaluation_time),
                business_timezone=ZoneInfo(business_timezone),
            )
        )

    return server
