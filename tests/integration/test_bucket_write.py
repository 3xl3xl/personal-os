"""Synthetic-only approved public write paths; no direct DB seeding."""
import datetime as dt
import uuid
from dataclasses import replace

import pytest
from mcp import Client
from sqlalchemy import event

from personal_os.adapters.mcp.bucket_tools import register_bucket_tools
from personal_os.adapters.mcp.server import create_server
from personal_os.domain.account_write_contracts import AddAccountInput
from personal_os.domain.bucket_write_contracts import AddCapitalBucketInput, AddCashLinkedAllocationInput, ReallocateCapitalInput
from personal_os.domain.enums import AccountType, BucketRole, AccountStatus, CapitalBucketStatus
from personal_os.domain.write_contracts import WriteContext
from personal_os.repository.unit_of_work import UnitOfWork
from personal_os.repository.audit_logs import AuditLogRepository
from personal_os.repository.bucket_allocations import BucketAllocationRepository
from personal_os.repository.transactions import TransactionRepository
from personal_os.services.account_write_contract import AccountWriteContract
from personal_os.services.bucket_write_contract import ApprovedBucketWrite, BucketWriteContract
from personal_os.services.finance import available_capital, tax_reserved, net_worth
from personal_os.services.permissions import PermissionDeniedError
from personal_os.services.write_contract import WriteReferenceError

NOW = dt.datetime(2026, 10, 7, tzinfo=dt.UTC)
LATER = NOW + dt.timedelta(days=1)
CONTEXT = WriteContext(actor="synthetic-user", reason="synthetic test", model_or_agent="synthetic-agent", source="synthetic-mcp", approved=True)


@pytest.fixture
def setup(session_factory):
    factory = lambda: UnitOfWork(session_factory)
    account_id = uuid.uuid4()
    AccountWriteContract(factory).add_account(AddAccountInput(id=account_id, name="synthetic", account_type=AccountType.CASH,
        currency_code="JPY", opened_at=NOW), context=CONTEXT)
    contract = BucketWriteContract(factory)
    general = AddCapitalBucketInput(id=uuid.uuid4(), account_id=account_id, name="not tax", bucket_role=BucketRole.GENERAL,
        is_protected=False, created_at=NOW)
    tax = general.model_copy(update=dict(id=uuid.uuid4(), name="arbitrary name", bucket_role=BucketRole.TAX_RESERVE, is_protected=True))
    for request in (general, tax):
        contract.execute(request, context=CONTEXT)
    return factory, contract, general, tax


def cash(bucket, **kwargs):
    return AddCashLinkedAllocationInput(id=uuid.uuid4(), bucket_id=bucket.id, amount_minor=100000,
        currency_code="JPY", created_at=NOW, **kwargs)


def values(factory, when=NOW):
    with factory() as u:
        return (net_worth(u.accounts, u.transactions, evaluation_time=when).value.amount_minor,
            available_capital(u.accounts, u.capital_buckets, u.bucket_allocations, evaluation_time=when).value.amount_minor,
            tax_reserved(u.accounts, u.capital_buckets, u.bucket_allocations, evaluation_time=when).value.amount_minor)


def counts(factory, bucket):
    with factory() as u:
        return (len(u.transactions.list_by_account(bucket.account_id)),
                sum(len(u.bucket_allocations.list_by_bucket(b.id)) for b in u.capital_buckets.list_by_account(bucket.account_id)),
                len(u.audit_logs.list_all()))


def test_cash_reallocate_reverse_history_as_of_and_retry(setup):
    factory, write, general, tax = setup
    request = cash(general)
    receipt = write.execute(request, context=CONTEXT)
    assert values(factory) == (100000, 100000, 0)
    assert write.execute(request, context=CONTEXT) == receipt | {"replayed": True}
    assert counts(factory, general) == (1, 1, 4)
    move = ReallocateCapitalInput(id=uuid.uuid4(), from_bucket_id=general.id, to_bucket_id=tax.id,
        amount_minor=30000, currency_code="JPY", created_at=LATER)
    write.execute(move, context=CONTEXT)
    assert values(factory) == (100000, 100000, 0)
    assert values(factory, LATER) == (100000, 70000, 30000)
    write.execute(move, context=CONTEXT)
    reverse = move.model_copy(update=dict(id=uuid.uuid4(), from_bucket_id=tax.id, to_bucket_id=general.id))
    write.execute(reverse, context=CONTEXT)
    assert values(factory, LATER) == (100000, 100000, 0)
    assert counts(factory, general) == (1, 5, 6)
    with factory() as u:
        audit = u.audit_logs.list_all()[-1]
        assert (audit.actor, audit.model_or_agent, audit.source, audit.tool) == (
            "synthetic-user", "synthetic-agent", "synthetic-mcp", "reallocate_capital")
        assert audit.old_value is None and audit.approval_status == "EXPLICITLY_APPROVED"
        legs = [a for b in (general, tax) for a in u.bucket_allocations.list_by_bucket(b.id) if a.reallocation_group_id == move.id]
        assert len(legs) == 2 and sum(a.amount.amount_minor for a in legs) == 0


@pytest.mark.parametrize("decision", [False, None, 1, "true"])
def test_denial_never_opens_uow(setup, decision):
    _, _, general, _ = setup
    def forbidden():
        pytest.fail("opened UOW without approval")
    approved = ApprovedBucketWrite(BucketWriteContract(forbidden), lambda *_: decision,
        actor="synthetic", model_or_agent="synthetic", source="synthetic")
    with pytest.raises(PermissionDeniedError):
        approved.execute(cash(general), reason="synthetic")


@pytest.mark.parametrize("field,value", [("amount_minor", 123), ("currency_code", "USD"), ("created_at", LATER)])
def test_changed_retry_rejected(setup, field, value):
    factory, write, general, _ = setup
    request = cash(general)
    write.execute(request, context=CONTEXT)
    with pytest.raises(WriteReferenceError):
        write.execute(request.model_copy(update={field: value}), context=CONTEXT)
    assert counts(factory, general) == (1, 1, 4)


@pytest.mark.parametrize("change", [dict(bucket_id=uuid.uuid4()), dict(currency_code="USD"), dict(amount_minor=0), dict(created_at=NOW-dt.timedelta(days=1))])
def test_constraints_no_partial_write(setup, change):
    factory, write, general, _ = setup
    with pytest.raises(WriteReferenceError):
        write.execute(cash(general).model_copy(update=change), context=CONTEXT)
    assert counts(factory, general) == (0, 0, 3)


@pytest.mark.parametrize("stage", ["transaction", "allocation", "audit", "commit"])
def test_atomic_failure_and_safe_retry(setup, monkeypatch, stage):
    factory, write, general, _ = setup
    request = cash(general)
    with monkeypatch.context() as patch:
        if stage != "commit":
            repo = {"transaction": TransactionRepository, "allocation": BucketAllocationRepository, "audit": AuditLogRepository}[stage]
            original = repo.add
            def fail(self, record):
                original(self, record)
                raise RuntimeError("synthetic failure after flush")
            patch.setattr(repo, "add", fail)
        else:
            original = UnitOfWork.commit
            def fail(self):
                event.listen(self.session, "before_commit", lambda *_: (_ for _ in ()).throw(RuntimeError("synthetic failure")))
                original(self)
            patch.setattr(UnitOfWork, "commit", fail)
        with pytest.raises(RuntimeError):
            write.execute(request, context=CONTEXT)
    assert counts(factory, general) == (0, 0, 3)
    write.execute(request, context=CONTEXT)
    assert counts(factory, general) == (1, 1, 4)


def test_second_reallocation_leg_failure_rolls_back_first(setup, monkeypatch):
    factory, write, general, tax = setup
    original = BucketAllocationRepository.add
    calls = []
    def fail(self, record):
        original(self, record)
        calls.append(record)
        if len(calls) == 2:
            raise RuntimeError("synthetic second leg")
    monkeypatch.setattr(BucketAllocationRepository, "add", fail)
    move = ReallocateCapitalInput(id=uuid.uuid4(), from_bucket_id=general.id, to_bucket_id=tax.id,
        amount_minor=10, currency_code="JPY", created_at=NOW)
    with pytest.raises(RuntimeError):
        write.execute(move, context=CONTEXT)
    assert counts(factory, general) == (0, 0, 3)


@pytest.mark.anyio
async def test_mcp_bound_approval_and_read_results(setup):
    factory, write, general, tax = setup
    seen = []
    def approve(request, context):
        seen.append((request, context))
        return True
    service = ApprovedBucketWrite(write, approve, actor=CONTEXT.actor, model_or_agent=CONTEXT.model_or_agent, source=CONTEXT.source)
    server = create_server(factory)
    register_bucket_tools(server, service)
    request = cash(general)
    async with Client(server, raise_exceptions=True) as client:
        listed = await client.list_tools()
        for tool in listed.tools:
            if tool.name in {"add_capital_bucket", "add_cash_linked_allocation", "reallocate_capital"}:
                assert not {"approved", "actor", "source", "model_or_agent"} & tool.input_schema["properties"].keys()
        args = request.model_dump(mode="json") | {"reason": CONTEXT.reason}
        result = await client.call_tool("add_cash_linked_allocation", args)
        assert result.structured_content["replayed"] is False
        assert (await client.call_tool("add_cash_linked_allocation", args)).structured_content["replayed"] is True
        move = ReallocateCapitalInput(id=uuid.uuid4(), from_bucket_id=general.id, to_bucket_id=tax.id,
            amount_minor=30000, currency_code="JPY", created_at=NOW)
        result = await client.call_tool("reallocate_capital", move.model_dump(mode="json") | {"reason": CONTEXT.reason})
        assert "error" not in result.structured_content
        for tool in ("get_available_capital", "get_tax_reserve"):
            result = await client.call_tool(tool, {"evaluation_time": NOW.isoformat()})
            assert not result.is_error
    assert len(seen) == 3 and all(context.approved is False for _, context in seen)
    assert values(factory) == (100000, 70000, 30000)


@pytest.mark.parametrize("target,change", [
    ("account", dict(status=AccountStatus.CLOSED)),
    ("account", dict(account_type=AccountType.INVESTMENT)),
    ("account", dict(account_type=AccountType.LIABILITY)),
    ("bucket", dict(status=CapitalBucketStatus.ARCHIVED)),
])
def test_inactive_or_non_cash_references_rejected(setup, monkeypatch, target, change):
    from personal_os.repository.accounts import AccountRepository
    from personal_os.repository.capital_buckets import CapitalBucketRepository
    factory, write, general, _ = setup
    repo = AccountRepository if target == "account" else CapitalBucketRepository
    original = repo.get
    monkeypatch.setattr(repo, "get", lambda self, identity: replace(original(self, identity), **change))
    with pytest.raises(WriteReferenceError):
        write.execute(cash(general), context=CONTEXT)
    assert counts(factory, general) == (0, 0, 3)


def test_cross_account_and_same_bucket_reallocation_rejected(setup):
    factory, write, general, tax = setup
    other_id = uuid.uuid4()
    AccountWriteContract(factory).add_account(AddAccountInput(id=other_id, name="synthetic other", account_type=AccountType.CASH,
        currency_code="JPY", opened_at=NOW), context=CONTEXT)
    other = general.model_copy(update=dict(id=uuid.uuid4(), account_id=other_id))
    write.execute(other, context=CONTEXT)
    for destination in (general.id, other.id):
        move = ReallocateCapitalInput(id=uuid.uuid4(), from_bucket_id=general.id, to_bucket_id=destination,
            amount_minor=10, currency_code="JPY", created_at=NOW)
        with pytest.raises(WriteReferenceError):
            write.execute(move, context=CONTEXT)
    assert values(factory) == (0, 0, 0)


@pytest.mark.parametrize("change", [dict(amount_minor=True), dict(amount_minor=1.5), dict(currency_code="jpy"),
    dict(amount_minor=2**63), dict(created_at=dt.datetime(2026,10,7))])
def test_bypassed_input_validation_rechecked_before_write(setup, change):
    factory, write, general, _ = setup
    with pytest.raises((ValueError, TypeError)):
        write.execute(cash(general).model_copy(update=change), context=CONTEXT)
    assert counts(factory, general) == (0, 0, 3)


def test_negative_cash_correction_preserves_history(setup):
    factory, write, general, _ = setup
    request = cash(general)
    write.execute(request, context=CONTEXT)
    write.execute(request.model_copy(update=dict(id=uuid.uuid4(), amount_minor=-100000)), context=CONTEXT)
    assert values(factory) == (0, 0, 0)
    assert counts(factory, general) == (2, 2, 5)


@pytest.mark.anyio
async def test_mcp_bucket_creation_denial_and_error_sanitization(setup, monkeypatch):
    factory, write, general, _ = setup
    server = create_server(factory)
    service = ApprovedBucketWrite(write, lambda *_: False, actor="synthetic", model_or_agent="synthetic", source="synthetic")
    register_bucket_tools(server, service)
    async with Client(server, raise_exceptions=False) as client:
        args = general.model_copy(update=dict(id=uuid.uuid4())).model_dump(mode="json") | {"reason": "synthetic"}
        result = await client.call_tool("add_capital_bucket", args)
        assert result.structured_content["error"]["code"] == "APPROVAL_REQUIRED"
        args["created_at"] = "invalid"
        result = await client.call_tool("add_capital_bucket", args)
        assert result.structured_content["error"]["code"] == "INVALID_INPUT"
        def fail(*args, **kwargs):
            raise RuntimeError("PRIVATE_SYNTHETIC_SECRET")
        monkeypatch.setattr(service, "execute", fail)
        result = await client.call_tool("add_cash_linked_allocation", cash(general).model_dump(mode="json") | {"reason": "synthetic"})
        assert result.structured_content["error"]["code"] == "WRITE_FAILED"
        assert "PRIVATE_SYNTHETIC_SECRET" not in str(result)
    assert counts(factory, general) == (0, 0, 3)


def test_concurrent_exact_retry_never_double_counts(setup, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    factory, write, general, _ = setup
    request = cash(general)
    barrier = Barrier(2)
    original = AuditLogRepository.list_all
    def synchronize(self):
        result = original(self)
        barrier.wait(timeout=10)
        return result
    with monkeypatch.context() as patch:
        patch.setattr(AuditLogRepository, "list_all", synchronize)
        def attempt():
            try:
                return write.execute(request, context=CONTEXT)
            except Exception as error:
                return error
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempt(), range(2)))
    assert sum(isinstance(r, dict) for r in results) == 1
    assert counts(factory, general) == (1, 1, 4)
    assert write.execute(request, context=CONTEXT)["replayed"] is True
    assert values(factory) == (100000,100000,0)


def test_multiple_tax_roles_and_protection_use_metadata_not_names(setup):
    factory, write, general, tax = setup
    second = tax.model_copy(update=dict(id=uuid.uuid4(), name="GENERAL", is_protected=False))
    write.execute(second, context=CONTEXT)
    write.execute(cash(tax), context=CONTEXT)
    write.execute(cash(second), context=CONTEXT)
    assert values(factory) == (200000,100000,200000)


def test_bucket_retry_provenance_and_approval_still_required(setup):
    factory, write, general, _ = setup
    assert write.execute(general, context=CONTEXT)["replayed"] is True
    for context in (CONTEXT.model_copy(update=dict(actor="other")), CONTEXT.model_copy(update=dict(reason="other"))):
        with pytest.raises(WriteReferenceError):
            write.execute(general, context=context)
    with pytest.raises(PermissionDeniedError):
        write.execute(general, context=CONTEXT.model_copy(update=dict(approved=False)))
    assert counts(factory, general) == (0,0,3)
