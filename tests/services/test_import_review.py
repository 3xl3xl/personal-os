"""Synthetic dedup, batch-approval, and rollback tests for ADR-014 Phase A
(personal_os.services.import_review)."""
from __future__ import annotations

import datetime as dt
import uuid
from types import SimpleNamespace

import pytest

from personal_os.domain.enums import AccountStatus, AccountType, ExternalSource
from personal_os.domain.external_facts import ImportDisposition, RawBankTransaction
from personal_os.domain.money import CurrencyMismatchError, Money
from personal_os.domain.records import AccountRecord, TransactionRecord
from personal_os.domain.enums import TransactionKind, TransactionStatus
from personal_os.services import import_review
from personal_os.services.write_contract import WriteReferenceError

NOW = dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc)
ACCOUNT_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
ACCOUNT = AccountRecord(ACCOUNT_ID, "synthetic", AccountType.CASH, "JPY", NOW, AccountStatus.ACTIVE)


def raw(**changes):
    values = dict(
        source=ExternalSource.FREEE,
        external_office_id="office-1",
        external_account_id="wallet-1",
        external_transaction_id="line-1",
        amount=Money(-500, "JPY"),
        occurred_at=NOW,
        description="synthetic coffee",
    )
    values.update(changes)
    return RawBankTransaction(**values)


class FakeLinks:
    def __init__(self, existing=None):
        self._existing = existing or {}
        self.added = []

    def _key(self, source, external_office_id, external_account_id, external_transaction_id):
        return (source, external_office_id, external_account_id, external_transaction_id)

    def find(self, *, source, external_office_id, external_account_id, external_transaction_id):
        return self._existing.get(self._key(source, external_office_id, external_account_id, external_transaction_id))

    def add(self, record):
        self.added.append(record)


class FakeTransactions:
    def __init__(self, existing=None):
        self._existing = existing or {}
        self.added = []

    def get(self, transaction_id):
        return self._existing.get(transaction_id)

    def add(self, record):
        self.added.append(record)


def _linked_record(transaction_id):
    return SimpleNamespace(transaction_id=transaction_id)


def test_stage_import_classifies_new_line_with_no_prior_link():
    preview = import_review.stage_import(FakeLinks(), FakeTransactions(), [(raw(), ACCOUNT_ID)])
    assert len(preview.candidates) == 1
    candidate = preview.candidates[0]
    assert candidate.disposition is ImportDisposition.NEW
    assert candidate.existing_transaction_id is None
    assert preview.approvable() == [candidate]


def test_stage_import_classifies_unchanged_already_imported_line():
    tx_id = uuid.uuid4()
    existing_tx = TransactionRecord(
        tx_id, ACCOUNT_ID, TransactionKind.NORMAL, Money(-500, "JPY"), NOW, TransactionStatus.ACTIVE
    )
    links = FakeLinks({("FREEE", "office-1", "wallet-1", "line-1"): _linked_record(tx_id)})
    transactions = FakeTransactions({tx_id: existing_tx})
    preview = import_review.stage_import(links, transactions, [(raw(), ACCOUNT_ID)])
    candidate = preview.candidates[0]
    assert candidate.disposition is ImportDisposition.ALREADY_IMPORTED_UNCHANGED
    assert candidate.existing_transaction_id == tx_id
    assert preview.approvable() == []


def test_stage_import_classifies_changed_already_imported_line():
    tx_id = uuid.uuid4()
    existing_tx = TransactionRecord(
        tx_id, ACCOUNT_ID, TransactionKind.NORMAL, Money(-999, "JPY"), NOW, TransactionStatus.ACTIVE
    )
    links = FakeLinks({("FREEE", "office-1", "wallet-1", "line-1"): _linked_record(tx_id)})
    transactions = FakeTransactions({tx_id: existing_tx})
    preview = import_review.stage_import(links, transactions, [(raw(), ACCOUNT_ID)])
    candidate = preview.candidates[0]
    assert candidate.disposition is ImportDisposition.ALREADY_IMPORTED_CHANGED
    assert preview.approvable() == [candidate]


def test_stage_import_never_writes():
    links, transactions = FakeLinks(), FakeTransactions()
    import_review.stage_import(links, transactions, [(raw(), ACCOUNT_ID)])
    assert links.added == [] and transactions.added == []


class FakeImportUow:
    def __init__(self, failure=None):
        self.events = []
        self.failure = failure
        self.saved_tx, self.saved_audit, self.saved_links = [], [], []
        self._staged_tx, self._staged_audit, self._staged_links = [], [], []
        self.accounts = SimpleNamespace(get=lambda _: ACCOUNT)
        self.transactions = SimpleNamespace(add=self._add_tx)
        self.audit_logs = SimpleNamespace(add=self._add_audit)
        self.external_transaction_links = SimpleNamespace(add=self._add_link)

    def __enter__(self):
        self.events.append("enter")
        return self

    def __exit__(self, kind, error, tb):
        if kind:
            self.events.append("rollback")
        self._staged_tx.clear()
        self._staged_audit.clear()
        self._staged_links.clear()
        self.events.append("exit")

    def _fail(self, phase):
        if self.failure == phase:
            raise RuntimeError(phase)

    def _add_tx(self, record):
        self.events.append("transaction")
        self._staged_tx.append(record)
        self._fail("transaction")

    def _add_audit(self, record):
        self.events.append("audit")
        self._staged_audit.append(record)
        self._fail("audit")

    def _add_link(self, record):
        self.events.append("link")
        self._staged_links.append(record)
        self._fail("link")

    def commit(self):
        self.events.append("commit")
        self._fail("commit")
        self.saved_tx.extend(self._staged_tx)
        self.saved_audit.extend(self._staged_audit)
        self.saved_links.extend(self._staged_links)


def _approve(uow, preview, approved_ids):
    return import_review.approve_import(
        lambda: uow, preview, approved_ids,
        actor="synthetic operator", model_or_agent="synthetic-agent",
        source="synthetic-test", reason="synthetic import",
        clock=lambda: NOW, audit_id_factory=lambda: uuid.UUID("00000000-0000-4000-8000-000000000099"),
    )


def test_empty_selection_persists_nothing():
    preview = import_review.stage_import(FakeLinks(), FakeTransactions(), [(raw(), ACCOUNT_ID)])
    uow = FakeImportUow()
    result = _approve(uow, preview, set())
    assert result.imported == []
    assert result.skipped_candidate_ids == [c.candidate_id for c in preview.candidates]
    assert uow.events == []
    assert uow.saved_tx == uow.saved_audit == uow.saved_links == []


def test_approved_subset_persists_exactly_and_matches_candidate():
    preview = import_review.stage_import(
        FakeLinks(), FakeTransactions(),
        [(raw(external_transaction_id="line-1"), ACCOUNT_ID), (raw(external_transaction_id="line-2"), ACCOUNT_ID)],
    )
    approve_only = {preview.candidates[0].candidate_id}
    uow = FakeImportUow()
    result = _approve(uow, preview, approve_only)
    assert len(result.imported) == 1
    assert result.imported[0].candidate_id == preview.candidates[0].candidate_id
    assert result.skipped_candidate_ids == [preview.candidates[1].candidate_id]
    assert len(uow.saved_tx) == 1 and len(uow.saved_audit) == 1 and len(uow.saved_links) == 1
    assert uow.saved_tx[0].account_id == ACCOUNT_ID
    assert uow.saved_tx[0].transaction_type is TransactionKind.NORMAL
    assert uow.saved_links[0].transaction_id == uow.saved_tx[0].id
    assert uow.saved_links[0].external_transaction_id == "line-1"
    assert uow.saved_audit[0].tool == "import_freee_transaction"
    assert uow.saved_audit[0].approval_status == "EXPLICITLY_APPROVED"


def test_already_imported_unchanged_is_never_written_even_if_listed_as_approved():
    tx_id = uuid.uuid4()
    existing_tx = TransactionRecord(
        tx_id, ACCOUNT_ID, TransactionKind.NORMAL, Money(-500, "JPY"), NOW, TransactionStatus.ACTIVE
    )
    links_repo = FakeLinks({("FREEE", "office-1", "wallet-1", "line-1"): _linked_record(tx_id)})
    preview = import_review.stage_import(links_repo, FakeTransactions({tx_id: existing_tx}), [(raw(), ACCOUNT_ID)])
    uow = FakeImportUow()
    result = _approve(uow, preview, {preview.candidates[0].candidate_id})
    assert result.imported == []
    assert result.skipped_candidate_ids == [preview.candidates[0].candidate_id]
    assert uow.events == []


def test_unknown_candidate_id_is_skipped_not_written():
    preview = import_review.stage_import(FakeLinks(), FakeTransactions(), [])
    uow = FakeImportUow()
    bogus = uuid.uuid4()
    result = _approve(uow, preview, {bogus})
    assert result.imported == []
    assert result.skipped_candidate_ids == [bogus]
    assert uow.events == []


def test_unapproved_real_candidate_is_reported_as_skipped_too():
    preview = import_review.stage_import(FakeLinks(), FakeTransactions(), [(raw(), ACCOUNT_ID)])
    uow = FakeImportUow()
    result = _approve(uow, preview, set())
    assert result.imported == []
    assert result.skipped_candidate_ids == [preview.candidates[0].candidate_id]
    assert uow.events == []


@pytest.mark.parametrize("phase", ["transaction", "audit", "link", "commit"])
def test_failure_at_any_phase_leaves_zero_transaction_and_zero_link(phase):
    preview = import_review.stage_import(FakeLinks(), FakeTransactions(), [(raw(), ACCOUNT_ID)])
    uow = FakeImportUow(phase)
    with pytest.raises(RuntimeError, match=phase):
        _approve(uow, preview, {preview.candidates[0].candidate_id})
    assert uow.saved_tx == uow.saved_audit == uow.saved_links == []
    assert "rollback" in uow.events


def test_currency_mismatch_between_account_and_raw_amount_is_rejected():
    preview = import_review.stage_import(
        FakeLinks(), FakeTransactions(), [(raw(amount=Money(-500, "USD")), ACCOUNT_ID)]
    )
    uow = FakeImportUow()
    with pytest.raises(CurrencyMismatchError):
        _approve(uow, preview, {preview.candidates[0].candidate_id})
    assert uow.saved_tx == uow.saved_audit == uow.saved_links == []


def test_unknown_account_is_rejected():
    preview = import_review.stage_import(FakeLinks(), FakeTransactions(), [(raw(), ACCOUNT_ID)])
    uow = FakeImportUow()
    uow.accounts.get = lambda _: None
    with pytest.raises(WriteReferenceError):
        _approve(uow, preview, {preview.candidates[0].candidate_id})
    assert uow.saved_tx == uow.saved_audit == uow.saved_links == []


def test_import_review_and_external_facts_have_no_orm_or_adapter_imports():
    import ast
    from pathlib import Path
    root = Path(__file__).parents[2] / "src/personal_os"
    for relative in ("services/import_review.py", "domain/external_facts.py"):
        tree = ast.parse((root / relative).read_text())
        for node in ast.walk(tree):
            names = (
                [a.name for a in node.names] if isinstance(node, ast.Import)
                else [node.module or ""] if isinstance(node, ast.ImportFrom)
                else []
            )
            assert not any(
                n.startswith(("sqlalchemy", "sqlite3", "personal_os.database", "personal_os.adapters", "mcp"))
                for n in names
            ), (relative, names)
