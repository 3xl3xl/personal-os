"""Obtain a trusted, request-bound batch decision before invoking the import pipeline.

Wires personal_os.services.import_review's already-built, already-tested
functions (stage_import / approve_import) together with the batch approval
dialog (approval/_batch_import.py::confirm_import_batch) into one call
(ADR-016). Neither import_review.py nor _batch_import.py is modified by
this addition.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable

from personal_os.domain.external_facts import (
    ImportBatchPreview, ImportBatchResult, ImportCandidate, RawBankTransaction,
)
from personal_os.services.import_review import (
    ImportUnitOfWorkFactory, approve_import, stage_import,
)


class ApprovedImportWrite:
    def __init__(
        self, uow_factory: ImportUnitOfWorkFactory,
        confirm: Callable[[list[ImportCandidate]], set[uuid.UUID]],
        *, actor: str, model_or_agent: str, source: str,
    ) -> None:
        self._uow_factory = uow_factory
        self._confirm = confirm
        self._actor = actor
        self._agent = model_or_agent
        self._source = source

    def import_batch(
        self, raw_transactions: list[tuple[RawBankTransaction, uuid.UUID]], *, reason: str,
    ) -> tuple[ImportBatchPreview, ImportBatchResult]:
        """Stage (read-only) -> human batch-review dialog -> write approved subset.

        An empty `raw_transactions` list, or a preview with nothing
        approvable, never opens the dialog and writes nothing.
        """
        with self._uow_factory() as uow:
            preview = stage_import(uow.external_transaction_links, uow.transactions, raw_transactions)
        approvable = preview.approvable()
        approved_ids = self._confirm(approvable) if approvable else set()
        result = approve_import(
            self._uow_factory, preview, approved_ids,
            actor=self._actor, model_or_agent=self._agent,
            source=self._source, reason=reason,
        )
        return preview, result
