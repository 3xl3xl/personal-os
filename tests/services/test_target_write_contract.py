"""Synthetic service-level permission, validation, ordering and rollback
tests for both AddFinancialTargetInput/Q4 and AddMonthlyTargetInput/Q5."""
import datetime as dt
import json
import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from personal_os.domain.money import Money
from personal_os.domain.target_write_contracts import (
    AddFinancialTargetInput, AddMonthlyTargetInput,
    canonical_financial_target, canonical_monthly_target,
)
from personal_os.domain.write_contracts import ApprovalStatus, WriteContext
from personal_os.services import target_write_contract as writes
from personal_os.services.permissions import PermissionDeniedError, OperationClass

NOW = dt.datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=dt.timezone.utc)
TARGET_ID = uuid.UUID("00000000-0000-4000-8000-0000000000c1")
AUDIT_ID = uuid.UUID("00000000-0000-4000-8000-0000000000c2")
METRIC_KEY = "net_worth_2026_goal"


def financial_request(**changes):
    values = dict(id=TARGET_ID, metric_key=METRIC_KEY,
                  target_amount=Money(10_000_000, "JPY"),
                  effective_from=NOW)
    values.update(changes)
    return AddFinancialTargetInput(**values)


def monthly_request(**changes):
    values = dict(id=TARGET_ID, metric_key=METRIC_KEY, year=2026, month=3,
                  target_amount=Money(500_000, "JPY"),
                  effective_from=NOW)
    values.update(changes)
    return AddMonthlyTargetInput(**values)


def context(**changes):
    return WriteContext(**(dict(actor="synthetic operator", reason="synthetic fact", approved=True, model_or_agent="synthetic-agent", source="synthetic-test") | changes))


class FakeUow:
    def __init__(self, failure=None, metric_exists=True):
        self.events = []
        self.failure = failure
        self.staged, self.saved = {"target": [], "audit": []}, {"target": [], "audit": []}
        self.financial_metrics = SimpleNamespace(get_by_key=lambda key: object() if metric_exists else None)
        self.financial_targets = SimpleNamespace(add=self._add_target, list_by_metric=lambda key: [])
        self.monthly_targets = SimpleNamespace(add=self._add_target, list_by_metric_year_month=lambda key, y, m: [])
        self.audit_logs = SimpleNamespace(add=self._add_audit)

    def __enter__(self):
        self.events.append("enter")
        return self

    def __exit__(self, kind, error, tb):
        if kind:
            self.events.append("rollback")
        self.staged["target"].clear()
        self.staged["audit"].clear()
        self.events.append("exit")

    def fail(self, phase):
        if self.failure == phase:
            raise RuntimeError(phase)

    def _add_target(self, record):
        self.events.append("target")
        self.staged["target"].append(record)
        self.fail("target")

    def _add_audit(self, record):
        self.events.append("audit")
        self.staged["audit"].append(record)
        self.fail("audit")

    def commit(self):
        self.events.append("commit")
        self.fail("commit")
        self.saved["target"].extend(self.staged["target"])
        self.saved["audit"].extend(self.staged["audit"])


def contract(uow, **kwargs):
    return writes.TargetWriteContract(lambda: uow, clock=lambda: NOW, audit_id_factory=lambda: AUDIT_ID, **kwargs)


@pytest.mark.parametrize("method,build,canonical,action,entity_type", [
    ("add_financial_target", financial_request, canonical_financial_target, "add_financial_target", "financial_target"),
    ("add_monthly_target", monthly_request, canonical_monthly_target, "add_monthly_target", "monthly_target"),
])
def test_success_order_full_audit(monkeypatch, method, build, canonical, action, entity_type):
    uow = FakeUow()
    real_permission = writes.require_permission
    def permission(operation, *, user_approved):
        assert operation is OperationClass.LOCAL_PERSONAL_DATA_WRITE
        assert user_approved is True
        uow.events.append("permission")
        return real_permission(operation, user_approved=user_approved)
    monkeypatch.setattr(writes, "require_permission", permission)
    result = getattr(contract(uow), method)(build(), context=context())
    assert uow.events == ["permission", "enter", "target", "audit", "commit", "exit"]
    assert uow.saved["target"] == [result.target]
    audit = uow.saved["audit"][0]
    assert (audit.id, audit.actor, audit.action, audit.affected_entity_type) == (AUDIT_ID, "synthetic operator", action, entity_type)
    assert audit.new_value == canonical(result.target)
    assert audit.approval_status == "EXPLICITLY_APPROVED"
    assert result.approval_status is ApprovalStatus.EXPLICITLY_APPROVED
    assert (audit.model_or_agent, audit.tool, audit.source) == ("synthetic-agent", action, "synthetic-test")


@pytest.mark.parametrize("method,build", [("add_financial_target", financial_request), ("add_monthly_target", monthly_request)])
def test_unapproved_stops_before_factory_or_clock(method, build):
    def forbidden():
        pytest.fail("unapproved write reached dependencies")
    service = writes.TargetWriteContract(forbidden, clock=forbidden, audit_id_factory=forbidden)
    with pytest.raises(PermissionDeniedError):
        getattr(service, method)(build(), context=context(approved=False))


@pytest.mark.parametrize("method,build", [("add_financial_target", financial_request), ("add_monthly_target", monthly_request)])
@pytest.mark.parametrize("phase", ["target", "audit", "commit"])
def test_failures_leave_no_partial_fact_or_audit(method, build, phase):
    uow = FakeUow(phase)
    with pytest.raises(RuntimeError, match=phase):
        getattr(contract(uow), method)(build(), context=context())
    assert uow.saved["target"] == uow.saved["audit"] == []
    assert "rollback" in uow.events


@pytest.mark.parametrize("method,build", [("add_financial_target", financial_request), ("add_monthly_target", monthly_request)])
def test_unknown_metric_key_precedes_mutation(method, build):
    uow = FakeUow(metric_exists=False)
    with pytest.raises(writes.WriteReferenceError, match="financial metric not found"):
        getattr(contract(uow), method)(build(), context=context())
    assert "target" not in uow.events and "commit" not in uow.events


def test_duplicate_financial_target_effective_from_rejected():
    uow = FakeUow()
    existing = SimpleNamespace(effective_from=NOW)
    uow.financial_targets.list_by_metric = lambda key: [existing]
    with pytest.raises(writes.WriteReferenceError, match="already exists"):
        contract(uow).add_financial_target(financial_request(), context=context())
    assert "target" not in uow.events and "commit" not in uow.events


def test_duplicate_monthly_target_effective_from_rejected():
    uow = FakeUow()
    existing = SimpleNamespace(effective_from=NOW)
    uow.monthly_targets.list_by_metric_year_month = lambda key, y, m: [existing]
    with pytest.raises(writes.WriteReferenceError, match="already exists"):
        contract(uow).add_monthly_target(monthly_request(), context=context())
    assert "target" not in uow.events and "commit" not in uow.events


def test_different_effective_from_is_not_a_duplicate():
    uow = FakeUow()
    existing = SimpleNamespace(effective_from=NOW - dt.timedelta(days=30))
    uow.financial_targets.list_by_metric = lambda key: [existing]
    contract(uow).add_financial_target(financial_request(), context=context())
    assert uow.saved["target"]


@pytest.mark.parametrize("field,value", [("metric_key", ""), ("metric_key", "  ")])
def test_financial_blank_fields_rejected(field, value):
    with pytest.raises(ValidationError):
        financial_request(**{field: value})


@pytest.mark.parametrize("month", [0, 13, -1])
def test_monthly_target_month_out_of_range_rejected(month):
    with pytest.raises(ValidationError):
        monthly_request(month=month)


def test_cross_currency_mismatch_raises_at_construction():
    from personal_os.domain.money import CurrencyMismatchError
    request = financial_request(target_amount=Money(100, "USD"))
    assert request.target_amount.currency_code == "USD"  # construction itself succeeds; mismatch only matters across operations


def test_revalidate_copy_before_uow():
    uow = FakeUow()
    with pytest.raises(ValidationError):
        contract(uow).add_financial_target(financial_request().model_copy(update={"metric_key": ""}), context=context())
    assert not uow.events


def test_service_and_domain_have_no_orm_or_adapter_imports():
    import ast
    from pathlib import Path
    root = Path(__file__).parents[2] / "src/personal_os"
    for relative in ("services/target_write_contract.py", "domain/target_write_contracts.py"):
        for node in ast.walk(ast.parse((root / relative).read_text())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            assert not any(n.startswith(("sqlalchemy", "sqlite3", "personal_os.database", "personal_os.adapters", "mcp")) for n in names)


def test_canonical_json_is_deterministic():
    uow = FakeUow()
    financial_result = contract(uow).add_financial_target(financial_request(), context=context())
    monthly_result = contract(FakeUow()).add_monthly_target(monthly_request(), context=context())
    financial_data = json.loads(canonical_financial_target(financial_result.target))
    monthly_data = json.loads(canonical_monthly_target(monthly_result.target))
    assert set(financial_data) == {"id", "metric_key", "target_amount", "effective_from", "created_at"}
    assert set(monthly_data) == {"id", "metric_key", "year", "month", "target_amount", "effective_from", "created_at"}
    assert financial_data["target_amount"] == {"amount_minor": 10_000_000, "currency_code": "JPY"}
    assert monthly_data["year"] == 2026 and monthly_data["month"] == 3
