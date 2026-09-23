"""Synthetic orchestration tests for ADR-016 (stage -> batch dialog -> approve wiring).

Dedup classification and per-line atomic write are already fully covered by
tests/services/test_import_review.py; these tests only cover the new
ApprovedImportWrite wiring itself.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from personal_os.domain.external_facts import ImportDisposition
from personal_os.services.approved_import_write import ApprovedImportWrite
from tests.services.test_import_review import ACCOUNT, ACCOUNT_ID, raw


class FakeUow:
    def __init__(self, existing_links=None):
        self.events = []
        self.saved_tx, self.saved_audit, self.saved_links = [], [], []
        self.accounts = SimpleNamespace(get=lambda _: ACCOUNT)
        self.transactions = SimpleNamespace(get=lambda _: None, add=self._add_tx)
        self.audit_logs = SimpleNamespace(add=self._add_audit)
        self.external_transaction_links = SimpleNamespace(
            find=lambda **kwargs: (existing_links or {}).get(
                (kwargs["source"], kwargs["external_office_id"],
                 kwargs["external_account_id"], kwargs["external_transaction_id"])
            ),
            add=self._add_link,
        )

    def __enter__(self):
        self.events.append("enter")
        return self

    def __exit__(self, kind, error, tb):
        self.events.append("exit")

    def _add_tx(self, record):
        self.saved_tx.append(record)

    def _add_audit(self, record):
        self.saved_audit.append(record)

    def _add_link(self, record):
        self.saved_links.append(record)

    def commit(self):
        self.events.append("commit")


def service(uow, confirm):
    return ApprovedImportWrite(
        lambda: uow, confirm, actor="synthetic operator",
        model_or_agent="synthetic-agent", source="synthetic-test",
    )


def test_dialog_never_opens_for_empty_batch():
    uow = FakeUow()
    def forbidden(candidates):
        pytest.fail("dialog opened for an empty batch")
    result_preview, result = service(uow, forbidden).import_batch([], reason="synthetic")
    assert result_preview.candidates == []
    assert result.imported == [] and result.skipped_candidate_ids == []
    assert not uow.saved_tx and not uow.saved_audit and not uow.saved_links


def test_dialog_never_opens_when_nothing_is_approvable():
    from personal_os.domain.records import TransactionRecord
    from personal_os.domain.enums import TransactionKind, TransactionStatus
    from personal_os.domain.money import Money
    tx_id = uuid.uuid4()
    existing = TransactionRecord(tx_id, ACCOUNT_ID, TransactionKind.NORMAL, Money(-500, "JPY"), raw().occurred_at, TransactionStatus.ACTIVE)
    uow = FakeUow(existing_links={("FREEE", "office-1", "wallet-1", "line-1"): SimpleNamespace(transaction_id=tx_id)})
    uow.transactions = SimpleNamespace(get=lambda _id: existing if _id == tx_id else None, add=uow._add_tx)
    def forbidden(candidates):
        pytest.fail("dialog opened with nothing approvable")
    preview, result = service(uow, forbidden).import_batch([(raw(), ACCOUNT_ID)], reason="synthetic")
    assert preview.candidates[0].disposition is ImportDisposition.ALREADY_IMPORTED_UNCHANGED
    assert result.imported == []


def test_dialog_receives_exactly_the_approvable_candidates():
    uow = FakeUow()
    seen = []
    def confirm(candidates):
        seen.append(candidates)
        return set()
    lines = [(raw(external_transaction_id="line-1"), ACCOUNT_ID), (raw(external_transaction_id="line-2"), ACCOUNT_ID)]
    preview, result = service(uow, confirm).import_batch(lines, reason="synthetic")
    assert len(seen) == 1 and seen[0] == preview.approvable() and len(seen[0]) == 2
    assert result.imported == []
    assert set(result.skipped_candidate_ids) == {c.candidate_id for c in preview.candidates}


def test_only_dialog_selected_candidates_are_written():
    uow = FakeUow()
    lines = [(raw(external_transaction_id="line-1"), ACCOUNT_ID), (raw(external_transaction_id="line-2"), ACCOUNT_ID)]
    def confirm(candidates):
        return {candidates[0].candidate_id}
    preview, result = service(uow, confirm).import_batch(lines, reason="synthetic")
    assert len(result.imported) == 1
    assert len(uow.saved_tx) == len(uow.saved_audit) == len(uow.saved_links) == 1
    assert result.imported[0].candidate_id == preview.candidates[0].candidate_id


def test_cancelled_dialog_writes_nothing():
    uow = FakeUow()
    lines = [(raw(), ACCOUNT_ID)]
    result_preview, result = service(uow, lambda candidates: set()).import_batch(lines, reason="synthetic")
    assert result.imported == []
    assert not uow.saved_tx and not uow.saved_audit and not uow.saved_links


def test_service_has_no_orm_or_adapter_imports():
    import ast
    from pathlib import Path
    root = Path(__file__).parents[2] / "src/personal_os"
    for node in ast.walk(ast.parse((root / "services/approved_import_write.py").read_text())):
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
        assert not any(n.startswith(("sqlalchemy", "sqlite3", "personal_os.database", "personal_os.adapters", "mcp")) for n in names)
