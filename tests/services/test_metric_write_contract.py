"""Synthetic service-level permission, validation, ordering and rollback tests."""
import datetime as dt
import json
import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from personal_os.domain.metric_write_contracts import AddMetricInput, canonical_metric
from personal_os.domain.write_contracts import ApprovalStatus, WriteContext
from personal_os.services import metric_write_contract as writes
from personal_os.services.permissions import PermissionDeniedError, OperationClass

NOW = dt.datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=dt.timezone.utc)
METRIC_ID = uuid.UUID("00000000-0000-4000-8000-0000000000b1")
AUDIT_ID = uuid.UUID("00000000-0000-4000-8000-0000000000b2")


def request(**changes):
    values = dict(id=METRIC_ID, key="net_worth_2026_goal", display_name="ヨーロッパ旅行資金")
    values.update(changes)
    return AddMetricInput(**values)


def context(**changes):
    return WriteContext(**(dict(actor="synthetic operator", reason="synthetic fact", approved=True, model_or_agent="synthetic-agent", source="synthetic-test") | changes))


class FakeUow:
    def __init__(self, failure=None):
        self.events = []
        self.failure = failure
        self.staged_metric, self.staged_audit = [], []
        self.saved_metric, self.saved_audit = [], []
        self.financial_metrics = SimpleNamespace(get_by_key=lambda _: None, add=self.add_metric)
        self.audit_logs = SimpleNamespace(add=self.add_audit)

    def __enter__(self):
        self.events.append("enter")
        return self

    def __exit__(self, kind, error, tb):
        if kind:
            self.events.append("rollback")
        self.staged_metric.clear()
        self.staged_audit.clear()
        self.events.append("exit")

    def fail(self, phase):
        if self.failure == phase:
            raise RuntimeError(phase)

    def add_metric(self, record):
        self.events.append("metric")
        self.staged_metric.append(record)
        self.fail("metric")

    def add_audit(self, record):
        self.events.append("audit")
        self.staged_audit.append(record)
        self.fail("audit")

    def commit(self):
        self.events.append("commit")
        self.fail("commit")
        self.saved_metric.extend(self.staged_metric)
        self.saved_audit.extend(self.staged_audit)


def contract(uow, **kwargs):
    return writes.MetricWriteContract(lambda: uow, clock=lambda: NOW, audit_id_factory=lambda: AUDIT_ID, **kwargs)


def test_success_order_full_audit(monkeypatch):
    uow = FakeUow()
    real_permission = writes.require_permission
    def permission(operation, *, user_approved):
        assert operation is OperationClass.LOCAL_PERSONAL_DATA_WRITE
        assert user_approved is True
        uow.events.append("permission")
        return real_permission(operation, user_approved=user_approved)
    monkeypatch.setattr(writes, "require_permission", permission)
    result = contract(uow).add_metric(request(), context=context())
    assert uow.events == ["permission", "enter", "metric", "audit", "commit", "exit"]
    assert uow.saved_metric == [result.metric]
    audit = uow.saved_audit[0]
    assert (audit.id, audit.actor, audit.action, audit.affected_entity_type) == (AUDIT_ID, "synthetic operator", "add_metric", "financial_metric")
    assert audit.new_value == canonical_metric(result.metric)
    assert audit.approval_status == "EXPLICITLY_APPROVED"
    assert result.approval_status is ApprovalStatus.EXPLICITLY_APPROVED
    assert (audit.model_or_agent, audit.tool, audit.source) == ("synthetic-agent", "add_metric", "synthetic-test")


def test_unapproved_stops_before_factory_or_clock():
    def forbidden():
        pytest.fail("unapproved write reached dependencies")
    service = writes.MetricWriteContract(forbidden, clock=forbidden, audit_id_factory=forbidden)
    with pytest.raises(PermissionDeniedError):
        service.add_metric(request(), context=context(approved=False))


@pytest.mark.parametrize("phase", ["metric", "audit", "commit"])
def test_failures_leave_no_partial_fact_or_audit(phase):
    uow = FakeUow(phase)
    with pytest.raises(RuntimeError, match=phase):
        contract(uow).add_metric(request(), context=context())
    assert uow.saved_metric == uow.saved_audit == []
    assert "rollback" in uow.events


def test_duplicate_key_precedes_mutation():
    uow = FakeUow()
    uow.financial_metrics.get_by_key = lambda _: object()
    with pytest.raises(writes.WriteReferenceError):
        contract(uow).add_metric(request(), context=context())
    assert "metric" not in uow.events and "commit" not in uow.events


@pytest.mark.parametrize("field,value", [("key", ""), ("key", "  "), ("display_name", "")])
def test_blank_fields_rejected(field, value):
    with pytest.raises(ValidationError):
        request(**{field: value})


def test_revalidate_copy_before_uow():
    uow = FakeUow()
    with pytest.raises(ValidationError):
        contract(uow).add_metric(request().model_copy(update={"key": ""}), context=context())
    assert not uow.events


def test_service_and_domain_have_no_orm_or_adapter_imports():
    import ast
    from pathlib import Path
    root = Path(__file__).parents[2] / "src/personal_os"
    for relative in ("services/metric_write_contract.py", "domain/metric_write_contracts.py"):
        for node in ast.walk(ast.parse((root / relative).read_text())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            assert not any(n.startswith(("sqlalchemy", "sqlite3", "personal_os.database", "personal_os.adapters", "mcp")) for n in names)


def test_canonical_json_is_deterministic():
    uow = FakeUow()
    result = contract(uow).add_metric(request(), context=context())
    canonical = canonical_metric(result.metric)
    data = json.loads(canonical)
    assert set(data) == {"id", "key", "display_name", "created_at"}
    assert data["created_at"] == "2026-01-02T03:04:05.123456Z"
    assert canonical == json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
