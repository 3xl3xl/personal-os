"""Real atomic import writes using the canonical temporary SQLite + Alembic
fixture (ADR-014, Phase A)."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from personal_os.database.schema import ExternalTransactionLink, Transaction
from personal_os.domain.external_facts import ImportCandidate, ImportDisposition, RawBankTransaction
from personal_os.domain.ids import new_id
from personal_os.domain.money import CurrencyMismatchError, Money
from personal_os.repository.external_transaction_links import ExternalTransactionLinkRepository
from personal_os.repository.transactions import TransactionRepository
from personal_os.repository.unit_of_work import UnitOfWork
from personal_os.services import import_review
from personal_os.services.write_contract import WriteReferenceError
from tests.services.test_write_contract import ACCOUNT, NOW
from tests.services.test_import_review import raw, ACCOUNT_ID


@pytest.fixture
def seeded(session_factory):
    with UnitOfWork(session_factory) as uow:
        uow.accounts.add(ACCOUNT)
        uow.commit()
    return session_factory


def _stage(session_factory, raw_pairs):
    with UnitOfWork(session_factory) as uow:
        return import_review.stage_import(uow.external_transaction_links, uow.transactions, raw_pairs)


def _approve(session_factory, preview, approved_ids):
    return import_review.approve_import(
        lambda: UnitOfWork(session_factory), preview, approved_ids,
        actor="synthetic operator", model_or_agent="synthetic-agent",
        source="synthetic-test", reason="synthetic freee import", clock=lambda: NOW,
    )


def counts(session_factory):
    with session_factory() as session:
        return (
            len(session.scalars(select(Transaction)).all()),
            len(session.scalars(select(ExternalTransactionLink)).all()),
        )


def test_approved_candidate_persists_transaction_and_link_atomically(seeded):
    preview = _stage(seeded, [(raw(), ACCOUNT_ID)])
    result = _approve(seeded, preview, {preview.candidates[0].candidate_id})
    assert len(result.imported) == 1
    with UnitOfWork(seeded) as uow:
        stored = uow.transactions.get(result.imported[0].transaction_id)
        assert stored.account_id == ACCOUNT_ID
        assert stored.amount == Money(-500, "JPY")
        link = uow.external_transaction_links.find(
            source=raw().source, external_office_id="office-1",
            external_account_id="wallet-1", external_transaction_id="line-1",
        )
        assert link is not None and link.transaction_id == stored.id
        audit = uow.audit_logs.list_all()[0]
        assert audit.tool == "import_freee_transaction"
    assert counts(seeded) == (1, 1)


def test_cancelled_review_persists_nothing(seeded):
    preview = _stage(seeded, [(raw(), ACCOUNT_ID)])
    result = _approve(seeded, preview, set())
    assert result.imported == []
    assert counts(seeded) == (0, 0)


def test_second_sync_of_same_line_is_not_reoffered_or_duplicated(seeded):
    first_preview = _stage(seeded, [(raw(), ACCOUNT_ID)])
    _approve(seeded, first_preview, {first_preview.candidates[0].candidate_id})
    assert counts(seeded) == (1, 1)

    second_preview = _stage(seeded, [(raw(), ACCOUNT_ID)])
    candidate = second_preview.candidates[0]
    assert candidate.disposition is ImportDisposition.ALREADY_IMPORTED_UNCHANGED
    assert second_preview.approvable() == []

    # Even if a caller mistakenly still passes its id as approved, nothing
    # new is written -- import_review skips ALREADY_IMPORTED_UNCHANGED rows.
    result = _approve(seeded, second_preview, {candidate.candidate_id})
    assert result.imported == []
    assert counts(seeded) == (1, 1)


def test_changed_amount_on_resync_is_surfaced_not_silently_applied(seeded):
    first_preview = _stage(seeded, [(raw(), ACCOUNT_ID)])
    _approve(seeded, first_preview, {first_preview.candidates[0].candidate_id})

    changed_preview = _stage(seeded, [(raw(amount=Money(-999, "JPY")), ACCOUNT_ID)])
    candidate = changed_preview.candidates[0]
    assert candidate.disposition is ImportDisposition.ALREADY_IMPORTED_CHANGED
    assert changed_preview.approvable() == [candidate]
    # Surfacing it does not itself write anything -- staging never writes.
    assert counts(seeded) == (1, 1)


@pytest.mark.parametrize("stage", ["transaction", "link"])
def test_real_rollback_after_flushed_writes_leaves_zero_rows(seeded, monkeypatch, stage):
    repo = TransactionRepository if stage == "transaction" else ExternalTransactionLinkRepository
    original = repo.add

    def fail(self, record):
        original(self, record)  # actual INSERT + flush already happened
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(repo, "add", fail)
    preview = _stage(seeded, [(raw(), ACCOUNT_ID)])
    with pytest.raises(RuntimeError, match="synthetic failure"):
        _approve(seeded, preview, {preview.candidates[0].candidate_id})
    assert counts(seeded) == (0, 0)


def test_currency_mismatch_real_db_no_rows(seeded):
    preview = _stage(seeded, [(raw(amount=Money(-500, "USD")), ACCOUNT_ID)])
    with pytest.raises(CurrencyMismatchError):
        _approve(seeded, preview, {preview.candidates[0].candidate_id})
    assert counts(seeded) == (0, 0)


def test_unknown_account_real_db_no_rows(session_factory):
    preview = _stage(session_factory, [(raw(), uuid.uuid4())])
    with pytest.raises(WriteReferenceError):
        _approve(session_factory, preview, {preview.candidates[0].candidate_id})
    assert counts(session_factory) == (0, 0)


def test_db_unique_constraint_is_defense_in_depth_against_app_level_dedup_bypass(seeded):
    """Two independently-staged NEW candidates sharing the same external
    identity (as if the app-level dedup check were somehow bypassed, e.g.
    a race between two concurrent syncs) must still be rejected by the
    external_transaction_links UNIQUE constraint -- not just by the
    stage_import()/find() lookup."""
    same_raw = raw()
    candidate_a = ImportCandidate(new_id(), same_raw, ACCOUNT_ID, ImportDisposition.NEW)
    candidate_b = ImportCandidate(new_id(), same_raw, ACCOUNT_ID, ImportDisposition.NEW)
    from personal_os.domain.external_facts import ImportBatchPreview

    result_a = _approve(seeded, ImportBatchPreview([candidate_a]), {candidate_a.candidate_id})
    assert len(result_a.imported) == 1
    with pytest.raises(IntegrityError):
        _approve(seeded, ImportBatchPreview([candidate_b]), {candidate_b.candidate_id})
    assert counts(seeded) == (1, 1)
