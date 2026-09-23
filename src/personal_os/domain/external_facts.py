"""Vendor-neutral shapes for importing read-only external bank/card facts.

Source of truth: PERSONAL_OS_SPEC.md Sec.24 (Bank/Card Integration), ADR-014
(freee read-only integration, Phase A). This module has zero dependency on
freee's actual wire format -- that translation belongs entirely to a thin,
separate adapter (personal_os.adapters.freee, not built in this pass; see
ADR-014's Phase A/B split). Everything here is plain, synthetic-data-
testable data: a RawBankTransaction is Personal OS's own minimal,
provider-neutral shape for "one line of an external statement," identified
for dedup by (source, external_office_id, external_account_id,
external_transaction_id) -- ADR-014, point 3.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from personal_os.domain.datetime import to_utc
from personal_os.domain.enums import ExternalSource
from personal_os.domain.money import Money

__all__ = [
    "RawBankTransaction",
    "ImportDisposition",
    "ImportCandidate",
    "ImportBatchPreview",
    "ImportedTransaction",
    "ImportBatchResult",
]


class RawBankTransaction(BaseModel):
    """One externally-reported statement line, before any Personal OS write.

    This module never infers income/expense classification and never sets
    a metric_key -- ADR-014 point 3 keeps that a separate, later decision,
    never automatic on the strength of an incoming-funds sign alone.
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    source: ExternalSource
    external_office_id: Annotated[str, Field(min_length=1)]
    external_account_id: Annotated[str, Field(min_length=1)]
    external_transaction_id: Annotated[str, Field(min_length=1)]
    amount: Money
    occurred_at: dt.datetime
    description: str | None = None

    @field_validator("occurred_at")
    @classmethod
    def aware_utc(cls, value: dt.datetime) -> dt.datetime:
        return to_utc(value)


class ImportDisposition(StrEnum):
    """Why a candidate is, or is not, eligible for approval in this batch."""

    NEW = "NEW"
    ALREADY_IMPORTED_UNCHANGED = "ALREADY_IMPORTED_UNCHANGED"
    ALREADY_IMPORTED_CHANGED = "ALREADY_IMPORTED_CHANGED"


@dataclass(frozen=True, slots=True)
class ImportCandidate:
    """One reviewable row: a RawBankTransaction plus its dedup disposition.

    account_id is the Personal OS Account this line belongs to, resolved by
    the caller (a one-time manual mapping decision -- ADR-014 Rationale --
    never inferred here).
    """

    candidate_id: uuid.UUID
    raw: RawBankTransaction
    account_id: uuid.UUID
    disposition: ImportDisposition
    existing_transaction_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ImportBatchPreview:
    """The full reviewable set for one staged import call. Read-only: no
    write has happened yet at this point."""

    candidates: list[ImportCandidate]

    def approvable(self) -> list[ImportCandidate]:
        """Rows a human may select for approval.

        ALREADY_IMPORTED_UNCHANGED rows are informational only -- offering
        them for re-approval would either silently no-op or (worse) risk a
        second Transaction for a fact already recorded.
        """
        return [
            c
            for c in self.candidates
            if c.disposition is not ImportDisposition.ALREADY_IMPORTED_UNCHANGED
        ]


@dataclass(frozen=True, slots=True)
class ImportedTransaction:
    candidate_id: uuid.UUID
    transaction_id: uuid.UUID
    audit_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ImportBatchResult:
    """What was actually written -- exactly the approved subset, nothing
    more. An empty `imported` list (all candidates in skipped_candidate_ids)
    means the review was cancelled or nothing was selected: zero writes."""

    imported: list[ImportedTransaction]
    skipped_candidate_ids: list[uuid.UUID]
