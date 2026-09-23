"""Synthetic service-level permission, validation, ordering and rollback tests."""
import datetime as dt
import json
import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from personal_os.domain.account_write_contracts import (
    AddAccountInput, canonical_account,
)
from personal_os.domain.enums import AccountStatus, AccountType
from personal_os.domain.write_contracts import ApprovalStatus, WriteContext
from personal_os.services import account_write_contract as writes
from personal_os.services.permissions import PermissionDeniedError, OperationClass

NOW = dt.datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=dt.timezone.utc)
ACCOUNT_ID = uuid.UUID("00000000-0000-4000-8000-0000000000a1")
AUDIT_ID = uuid.UUID("00000000-0000-4000-8000-0000000000a2")


def request(**changes):
    values = dict(id=ACCOUNT_ID, name="SMBC 普通口座", account_type=AccountType.CASH,
                  currency_code="JPY", opened_at=NOW)
    values.update(changes)
    return AddAccountInput(**values)


def context(**changes):
    return WriteContext(**(dict(actor="synthetic operator", reason="synthetic fact", approved=True, model_or_agent="synthetic-agent", source="synthetic-test") | changes))


class FakeUow:
    def __init__(self, failure=None):
        self.events = []
        self.failure = failure
        self.staged_account, self.staged_audit = [], []
        self.saved_account, self.saved_audit = [], []
        self.accounts = SimpleNamespace(get=lambda _: None, add=self.add_account)
        self.audit_logs = SimpleNamespace(add=self.add_audit)

    def __enter__(self):
        self.events.append("enter")
        return self

    def __exit__(self, kind, error, tb):
        if kind:
            self.events.append("rollback")
        self.staged_account.clear()
        self.staged_audit.clear()
        self.events.append("exit")

    def fail(self, phase):
        if self.failure == phase:
            raise RuntimeError(phase)

    def add_account(self, record):
        self.events.append("account")
        self.staged_account.append(record)
        self.fail("account")

    def add_audit(self, record):
        self.events.append("audit")
        self.staged_audit.append(record)
        self.fail("audit")

    def commit(self):
        self.events.append("commit")
        self.fail("commit")
        self.saved_account.extend(self.staged_account)
        self.saved_audit.extend(self.staged_audit)


def contract(uow, **kwargs):
    return writes.AccountWriteContract(lambda: uow, clock=lambda: NOW, audit_id_factory=lambda: AUDIT_ID, **kwargs)


def test_success_order_full_audit(monkeypatch):
    uow = FakeUow()
    real_permission = writes.require_permission
    def permission(operation, *, user_approved):
        assert operation is OperationClass.LOCAL_PERSONAL_DATA_WRITE
        assert user_approved is True
        uow.events.append("permission")
        return real_permission(operation, user_approved=user_approved)
    monkeypatch.setattr(writes, "require_permission", permission)
    result = contract(uow).add_account(request(), context=context())
    assert uow.events == ["permission", "enter", "account", "audit", "commit", "exit"]
    assert uow.saved_account == [result.account]
    assert result.account.status is AccountStatus.ACTIVE
    assert result.account.account_type is AccountType.CASH
    audit = uow.saved_audit[0]
    assert (audit.id, audit.actor, audit.action, audit.affected_entity_type) == (AUDIT_ID, "synthetic operator", "add_account", "account")
    assert audit.affected_entity_id == ACCOUNT_ID
    assert audit.old_value is None
    assert audit.new_value == canonical_account(result.account)
    assert audit.reason == "synthetic fact"
    assert audit.approval_status == "EXPLICITLY_APPROVED"
    assert result.approval_status is ApprovalStatus.EXPLICITLY_APPROVED
    assert audit.occurred_at == NOW and audit.occurred_at.tzinfo is dt.timezone.utc
    assert (audit.model_or_agent, audit.tool, audit.source) == ("synthetic-agent", "add_account", "synthetic-test")


def test_unapproved_stops_before_factory_or_clock():
    def forbidden():
        pytest.fail("unapproved write reached dependencies")
    service = writes.AccountWriteContract(forbidden, clock=forbidden, audit_id_factory=forbidden)
    with pytest.raises(PermissionDeniedError):
        service.add_account(request(), context=context(approved=False))


@pytest.mark.parametrize("phase", ["account", "audit", "commit"])
def test_failures_leave_no_partial_fact_or_audit(phase):
    uow = FakeUow(phase)
    with pytest.raises(RuntimeError, match=phase):
        contract(uow).add_account(request(), context=context())
    assert uow.saved_account == uow.saved_audit == []
    assert uow.staged_account == uow.staged_audit == []
    assert "rollback" in uow.events


def test_duplicate_account_id_precedes_mutation():
    uow = FakeUow()
    uow.accounts.get = lambda _: object()
    with pytest.raises(writes.WriteReferenceError):
        contract(uow).add_account(request(), context=context())
    assert "account" not in uow.events and "commit" not in uow.events
    assert not uow.saved_account and not uow.saved_audit


@pytest.mark.parametrize("field", ["status"])
def test_out_of_scope_input_fields_rejected(field):
    with pytest.raises(ValidationError):
        request(**{field: "anything"})


@pytest.mark.parametrize("field,value", [("name", ""), ("name", "  "), ("currency_code", "")])
def test_blank_fields_rejected(field, value):
    with pytest.raises(ValidationError):
        request(**{field: value})


def test_naive_time_rejected_and_offset_canonicalized():
    with pytest.raises(ValidationError):
        request(opened_at=NOW.replace(tzinfo=None))
    offset = NOW.astimezone(dt.timezone(dt.timedelta(hours=9)))
    uow = FakeUow()
    result = contract(uow).add_account(request(opened_at=offset), context=context())
    assert result.account.opened_at == NOW
    assert result.account.opened_at.tzinfo is dt.timezone.utc
    canonical = canonical_account(result.account)
    assert '"opened_at":"2026-01-02T03:04:05.123456Z"' in canonical
    data = json.loads(canonical)
    assert set(data) == {"id", "name", "account_type", "currency_code", "opened_at", "status"}
    assert data["status"] == "ACTIVE"
    assert canonical == json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def test_revalidate_copy_before_uow():
    uow = FakeUow()
    with pytest.raises(ValidationError):
        contract(uow).add_account(request().model_copy(update={"opened_at": NOW.replace(tzinfo=None)}), context=context())
    assert not uow.events


def test_clock_failure_before_any_write():
    uow = FakeUow()
    service = writes.AccountWriteContract(lambda: uow, clock=lambda: NOW.replace(tzinfo=None))
    with pytest.raises(ValueError):
        service.add_account(request(), context=context())
    assert not uow.events


def test_service_and_domain_have_no_orm_or_adapter_imports():
    import ast
    from pathlib import Path
    root = Path(__file__).parents[2] / "src/personal_os"
    for relative in ("services/account_write_contract.py", "domain/account_write_contracts.py"):
        for node in ast.walk(ast.parse((root / relative).read_text())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            assert not any(n.startswith(("sqlalchemy", "sqlite3", "personal_os.database", "personal_os.adapters", "mcp")) for n in names)
            assert all(n in ("personal_os.repository.protocols",) for n in names if n.startswith("personal_os.repository"))


@pytest.mark.parametrize("field", ["model_or_agent", "source"])
def test_audit_provenance_is_required(field):
    values = context().model_dump()
    del values[field]
    with pytest.raises(ValidationError):
        WriteContext(**values)
