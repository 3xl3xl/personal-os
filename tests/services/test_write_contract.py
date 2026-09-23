"""Synthetic service-level permission, validation, ordering and rollback tests."""
import datetime as dt
import json
import uuid
from dataclasses import replace
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from personal_os.domain.enums import AccountStatus, AccountType, TransactionKind, TransactionStatus
from personal_os.domain.money import Money, CurrencyMismatchError
from personal_os.domain.records import AccountRecord
from personal_os.domain.write_contracts import (
    AddTransactionInput, ApprovalStatus, WriteContext, canonical_transaction,
)
from personal_os.services import write_contract as writes
from personal_os.services.permissions import PermissionDeniedError, OperationClass

NOW = dt.datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=dt.timezone.utc)
ACCOUNT_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
TX_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
AUDIT_ID = uuid.UUID("00000000-0000-4000-8000-000000000003")
ACCOUNT = AccountRecord(ACCOUNT_ID, "Synthetic account", AccountType.CASH, "JPY", NOW, AccountStatus.ACTIVE)


def request(**changes):
    values = dict(id=TX_ID, account_id=ACCOUNT_ID, amount=Money(-123, "JPY"), occurred_at=NOW, memo="synthetic 日本語")
    values.update(changes)
    return AddTransactionInput(**values)


def context(**changes):
    return WriteContext(**(dict(actor="synthetic operator", reason="synthetic fact", approved=True, model_or_agent="synthetic-agent", source="synthetic-test") | changes))


class FakeUow:
    def __init__(self, failure=None):
        self.events = []
        self.failure = failure
        self.staged_tx, self.staged_audit = [], []
        self.saved_tx, self.saved_audit = [], []
        self.accounts = SimpleNamespace(get=lambda _: ACCOUNT)
        self.transactions = SimpleNamespace(get=lambda _: None, add=self.add_tx)
        self.audit_logs = SimpleNamespace(add=self.add_audit)
        self.financial_metrics = SimpleNamespace(get_by_key=lambda key: object())

    def __enter__(self):
        self.events.append("enter")
        return self

    def __exit__(self, kind, error, tb):
        if kind:
            self.events.append("rollback")
        self.staged_tx.clear()
        self.staged_audit.clear()
        self.events.append("exit")

    def fail(self, phase):
        if self.failure == phase:
            raise RuntimeError(phase)

    def add_tx(self, record):
        self.events.append("transaction")
        self.staged_tx.append(record)
        self.fail("transaction")

    def add_audit(self, record):
        self.events.append("audit")
        self.staged_audit.append(record)
        self.fail("audit")

    def commit(self):
        self.events.append("commit")
        self.fail("commit")
        self.saved_tx.extend(self.staged_tx)
        self.saved_audit.extend(self.staged_audit)


def contract(uow, **kwargs):
    return writes.FinanceWriteContract(lambda: uow, clock=lambda: NOW, audit_id_factory=lambda: AUDIT_ID, **kwargs)


def test_success_order_full_audit_and_no_balance_mutation(monkeypatch):
    uow = FakeUow()
    real_permission = writes.require_permission
    def permission(operation, *, user_approved):
        assert operation is OperationClass.LOCAL_PERSONAL_DATA_WRITE
        assert user_approved is True
        uow.events.append("permission")
        return real_permission(operation, user_approved=user_approved)
    monkeypatch.setattr(writes, "require_permission", permission)
    result = contract(uow).add_transaction(request(), context=context())
    assert uow.events == ["permission", "enter", "transaction", "audit", "commit", "exit"]
    assert uow.saved_tx == [result.transaction]
    assert result.transaction.transaction_type is TransactionKind.NORMAL
    assert result.transaction.status is TransactionStatus.ACTIVE
    assert result.transaction.amount == Money(-123, "JPY")
    audit = uow.saved_audit[0]
    assert (audit.id, audit.actor, audit.action, audit.affected_entity_type) == (AUDIT_ID, "synthetic operator", "add_transaction", "transaction")
    assert audit.affected_entity_id == TX_ID
    assert audit.old_value is None
    assert audit.new_value == canonical_transaction(result.transaction)
    assert audit.reason == "synthetic fact"
    assert audit.approval_status == "EXPLICITLY_APPROVED"
    assert result.approval_status is ApprovalStatus.EXPLICITLY_APPROVED
    assert audit.occurred_at == NOW and audit.occurred_at.tzinfo is dt.timezone.utc
    assert not hasattr(ACCOUNT, "balance")


def test_unapproved_stops_before_factory_or_clock():
    def forbidden():
        pytest.fail("unapproved write reached dependencies")
    service = writes.FinanceWriteContract(forbidden, clock=forbidden, audit_id_factory=forbidden)
    with pytest.raises(PermissionDeniedError):
        service.add_transaction(request(), context=context(approved=False))
    assert WriteContext(actor="synthetic", reason="synthetic", model_or_agent="synthetic-agent", source="synthetic-test").approved is False


@pytest.mark.parametrize("phase", ["transaction", "audit", "commit"])
def test_failures_leave_no_partial_fact_or_audit(phase):
    uow = FakeUow(phase)
    with pytest.raises(RuntimeError, match=phase):
        contract(uow).add_transaction(request(), context=context())
    assert uow.saved_tx == uow.saved_audit == []
    assert uow.staged_tx == uow.staged_audit == []
    assert "rollback" in uow.events


@pytest.mark.parametrize("approved", [1, 0, "true", "false", None])
def test_approval_is_strict_boolean(approved):
    with pytest.raises(ValidationError):
        context(approved=approved)


@pytest.mark.parametrize("field", ["transaction_type", "status", "correction_of", "transfer_group_id", "balance", "net_worth", "approval_status"])
def test_out_of_scope_input_fields_rejected(field):
    with pytest.raises(ValidationError):
        request(**{field: "anything"})


@pytest.mark.parametrize("field,value", [("actor", ""), ("reason", "  "), ("actor", 1)])
def test_audit_metadata_required(field, value):
    with pytest.raises(ValidationError):
        context(**{field: value})


def test_naive_time_rejected_and_offset_canonicalized():
    with pytest.raises(ValidationError):
        request(occurred_at=NOW.replace(tzinfo=None))
    offset = NOW.astimezone(dt.timezone(dt.timedelta(hours=9)))
    uow = FakeUow()
    result = contract(uow).add_transaction(request(occurred_at=offset), context=context())
    assert result.transaction.occurred_at == NOW
    assert result.transaction.occurred_at.tzinfo is dt.timezone.utc
    canonical = canonical_transaction(result.transaction)
    assert canonical == canonical_transaction(replace(result.transaction, occurred_at=offset))
    assert '"occurred_at":"2026-01-02T03:04:05.123456Z"' in canonical
    data = json.loads(canonical)
    assert set(data) == {"id", "account_id", "transaction_type", "amount", "occurred_at", "status", "correction_of", "metric_key", "transfer_group_id", "memo"}
    assert data["amount"] == {"amount_minor": -123, "currency_code": "JPY"}
    assert data["correction_of"] is data["transfer_group_id"] is None
    assert canonical == json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@pytest.mark.parametrize("scenario", ["account", "metric", "duplicate", "currency"])
def test_invalid_references_and_currency_precede_mutation(scenario):
    uow = FakeUow()
    if scenario == "account": uow.accounts.get = lambda _: None
    if scenario == "metric": uow.financial_metrics.get_by_key = lambda _: None
    if scenario == "duplicate": uow.transactions.get = lambda _: object()
    req = request(amount=Money(1, "USD")) if scenario == "currency" else request(metric_key="synthetic_revenue")
    with pytest.raises((writes.WriteReferenceError, CurrencyMismatchError)):
        contract(uow).add_transaction(req, context=context())
    assert "transaction" not in uow.events and "commit" not in uow.events
    assert not uow.saved_tx and not uow.saved_audit


def test_revalidate_copy_before_uow():
    uow = FakeUow()
    with pytest.raises(ValidationError):
        contract(uow).add_transaction(request().model_copy(update={"occurred_at": NOW.replace(tzinfo=None)}), context=context())
    assert not uow.events


def test_clock_failure_before_any_write():
    uow = FakeUow()
    service = writes.FinanceWriteContract(lambda: uow, clock=lambda: NOW.replace(tzinfo=None))
    with pytest.raises(ValueError):
        service.add_transaction(request(), context=context())
    assert not uow.events


def test_money_precision_preserved_in_audit():
    uow = FakeUow()
    amount = 2**60 + 1
    result = contract(uow).add_transaction(request(amount=Money(amount, "JPY")), context=context())
    assert json.loads(uow.saved_audit[0].new_value)["amount"]["amount_minor"] == amount
    assert result.transaction.amount.amount_minor == amount


def test_service_and_domain_have_no_orm_or_adapter_imports():
    import ast
    from pathlib import Path
    root = Path(__file__).parents[2] / "src/personal_os"
    for relative in ("services/write_contract.py", "domain/write_contracts.py"):
        for node in ast.walk(ast.parse((root / relative).read_text())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            assert not any(n.startswith(("sqlalchemy", "sqlite3", "personal_os.database", "personal_os.adapters", "mcp")) for n in names)
            assert all(n == "personal_os.repository.protocols" for n in names if n.startswith("personal_os.repository"))


@pytest.mark.parametrize("value", [True, 1.1, "123"])
def test_money_coercion_rejected(value):
    with pytest.raises((ValueError, ValidationError)):
        request(amount=Money(value, "JPY"))


@pytest.mark.parametrize("field", ["model_or_agent", "source"])
def test_new_audit_provenance_is_required(field):
    values = context().model_dump()
    del values[field]
    with pytest.raises(ValidationError):
        WriteContext(**values)
    with pytest.raises(ValidationError):
        context(**{field: " "})


def test_new_audit_provenance_is_separate_from_reason():
    uow = FakeUow()
    contract(uow).add_transaction(request(), context=context())
    audit = uow.saved_audit[0]
    assert (audit.model_or_agent, audit.tool, audit.source) == ("synthetic-agent", "add_transaction", "synthetic-test")
    assert audit.reason == "synthetic fact"
