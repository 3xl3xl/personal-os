"""Stage and approve read-only external bank/card imports (ADR-014, Phase A).

Two-phase flow, mirroring the project's existing approval discipline:

  stage_import()   -- pure dedup classification against already-imported
                       facts. No writes, no approval, no side effects.
  approve_import() -- writes exactly the caller-approved subset. Each
                       approved candidate is its own atomic
                       Transaction + AuditLog + ExternalTransactionLink
                       commit (see module docstring below for why this
                       does not call personal_os.services.write_contract.
                       FinanceWriteContract.add_transaction directly).

Architecture boundary: this module imports only personal_os.domain and
Repository Protocols -- never sqlalchemy, sqlite3, personal_os.database,
or personal_os.adapters (covered automatically by the existing
tests/repository/test_architecture_boundaries.py rglob over
personal_os.services).
"""
from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Callable
from typing import Any, Protocol

from personal_os.domain.datetime import to_utc, utc_now
from personal_os.domain.enums import TransactionKind, TransactionStatus
from personal_os.domain.external_facts import (
    ImportBatchPreview,
    ImportBatchResult,
    ImportCandidate,
    ImportDisposition,
    ImportedTransaction,
    RawBankTransaction,
)
from personal_os.domain.ids import new_id
from personal_os.domain.money import CurrencyMismatchError
from personal_os.domain.records import (
    AuditLogRecord,
    ExternalTransactionLinkRecord,
    TransactionRecord,
)
from personal_os.domain.write_contracts import ApprovalStatus, canonical_transaction
from personal_os.repository.protocols import (
    AccountRepositoryProtocol,
    ExternalTransactionLinkRepositoryProtocol,
    TransactionRepositoryProtocol,
)
from personal_os.services.permissions import OperationClass, require_permission
from personal_os.services.write_contract import WriteReferenceError


def _disposition(
    links: ExternalTransactionLinkRepositoryProtocol,
    transactions: TransactionRepositoryProtocol,
    raw: RawBankTransaction,
) -> tuple[ImportDisposition, uuid.UUID | None]:
    existing = links.find(
        source=raw.source,
        external_office_id=raw.external_office_id,
        external_account_id=raw.external_account_id,
        external_transaction_id=raw.external_transaction_id,
    )
    if existing is None:
        return ImportDisposition.NEW, None
    linked = transactions.get(existing.transaction_id)
    unchanged = (
        linked is not None
        and linked.amount == raw.amount
        and to_utc(linked.occurred_at) == to_utc(raw.occurred_at)
    )
    disposition = (
        ImportDisposition.ALREADY_IMPORTED_UNCHANGED
        if unchanged
        else ImportDisposition.ALREADY_IMPORTED_CHANGED
    )
    return disposition, existing.transaction_id


def stage_import(
    links: ExternalTransactionLinkRepositoryProtocol,
    transactions: TransactionRepositoryProtocol,
    raw_transactions: list[tuple[RawBankTransaction, uuid.UUID]],
) -> ImportBatchPreview:
    """Classify each raw line against already-imported facts. No writes.

    `raw_transactions` pairs each RawBankTransaction with the Personal OS
    Account it belongs to -- that mapping is the caller's responsibility
    (ADR-014 Rationale), never inferred here.
    """
    candidates = [
        ImportCandidate(
            candidate_id=new_id(),
            raw=raw,
            account_id=account_id,
            disposition=(disposition := _disposition(links, transactions, raw))[0],
            existing_transaction_id=disposition[1],
        )
        for raw, account_id in raw_transactions
    ]
    return ImportBatchPreview(candidates=candidates)


class ImportUnitOfWork(Protocol):
    accounts: AccountRepositoryProtocol
    transactions: TransactionRepositoryProtocol
    audit_logs: Any
    external_transaction_links: ExternalTransactionLinkRepositoryProtocol

    def __enter__(self) -> "ImportUnitOfWork": ...
    def __exit__(self, exc_type, exc, tb) -> None: ...
    def commit(self) -> None: ...


ImportUnitOfWorkFactory = Callable[[], ImportUnitOfWork]


def _write_approved_candidate(
    uow_factory: ImportUnitOfWorkFactory,
    candidate: ImportCandidate,
    *,
    actor: str,
    model_or_agent: str,
    source: str,
    reason: str,
    clock: Callable[[], dt.datetime],
    audit_id_factory: Callable[[], uuid.UUID],
) -> ImportedTransaction:
    """Write one already-approved candidate: Transaction + AuditLog +
    ExternalTransactionLink, in a single commit.

    This does not call FinanceWriteContract.add_transaction (services/
    write_contract.py) -- that method opens its own UnitOfWork and commits
    before returning, which would leave a real gap where a Transaction
    could exist without its dedup link (e.g. a crash between two separate
    commits). That gap would defeat the no-duplicate-import guarantee the
    very first time a sync was retried after a partial failure. This
    function therefore duplicates add_transaction's two validation checks
    (account exists, currency matches) rather than composing two commits.
    FinanceWriteContract itself is unmodified; the existing single-item
    approval method is unaffected by this addition (ADR-014).
    """
    require_permission(OperationClass.LOCAL_PERSONAL_DATA_WRITE, user_approved=True)
    transaction = TransactionRecord(
        id=new_id(),
        account_id=candidate.account_id,
        transaction_type=TransactionKind.NORMAL,
        amount=candidate.raw.amount,
        occurred_at=candidate.raw.occurred_at,
        status=TransactionStatus.ACTIVE,
        metric_key=None,
        memo=candidate.raw.description,
    )
    recorded_at = to_utc(clock())
    audit = AuditLogRecord(
        id=audit_id_factory(),
        actor=actor,
        action="add_transaction",
        affected_entity_type="transaction",
        affected_entity_id=transaction.id,
        old_value=None,
        new_value=canonical_transaction(transaction),
        reason=reason,
        approval_status=ApprovalStatus.EXPLICITLY_APPROVED.value,
        occurred_at=recorded_at,
        model_or_agent=model_or_agent,
        tool="import_freee_transaction",
        source=source,
    )
    link = ExternalTransactionLinkRecord(
        id=new_id(),
        source=candidate.raw.source,
        external_office_id=candidate.raw.external_office_id,
        external_account_id=candidate.raw.external_account_id,
        external_transaction_id=candidate.raw.external_transaction_id,
        transaction_id=transaction.id,
        imported_at=recorded_at,
    )
    with uow_factory() as uow:
        account = uow.accounts.get(transaction.account_id)
        if account is None:
            raise WriteReferenceError("account not found")
        if account.currency_code != transaction.amount.currency_code:
            raise CurrencyMismatchError(
                "transaction currency must match account currency"
            )
        uow.transactions.add(transaction)
        uow.audit_logs.add(audit)
        uow.external_transaction_links.add(link)
        uow.commit()
    return ImportedTransaction(
        candidate_id=candidate.candidate_id,
        transaction_id=transaction.id,
        audit_id=audit.id,
    )


def approve_import(
    uow_factory: ImportUnitOfWorkFactory,
    preview: ImportBatchPreview,
    approved_candidate_ids: set[uuid.UUID],
    *,
    actor: str,
    model_or_agent: str,
    source: str,
    reason: str,
    clock: Callable[[], dt.datetime] = utc_now,
    audit_id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
) -> ImportBatchResult:
    """Write exactly the approved subset. An empty approved_candidate_ids
    set (a cancelled or empty-selection review) writes nothing at all --
    the loop below simply never runs.

    A candidate not present in `preview`, or one whose disposition is
    ALREADY_IMPORTED_UNCHANGED, is never written even if its id is passed
    in `approved_candidate_ids` -- it is recorded as skipped instead.
    """
    by_id = {c.candidate_id: c for c in preview.candidates}
    imported: list[ImportedTransaction] = []
    skipped: list[uuid.UUID] = []
    for candidate_id in approved_candidate_ids:
        candidate = by_id.get(candidate_id)
        if candidate is None or candidate.disposition is ImportDisposition.ALREADY_IMPORTED_UNCHANGED:
            skipped.append(candidate_id)
            continue
        imported.append(
            _write_approved_candidate(
                uow_factory,
                candidate,
                actor=actor,
                model_or_agent=model_or_agent,
                source=source,
                reason=reason,
                clock=clock,
                audit_id_factory=audit_id_factory,
            )
        )
    skipped.extend(
        candidate_id
        for candidate_id in by_id
        if candidate_id not in approved_candidate_ids
    )
    return ImportBatchResult(imported=imported, skipped_candidate_ids=skipped)
