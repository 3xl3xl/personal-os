# ADR-014: freee Read-Only Integration (Bank/Card Normalization, Phase A)

Status: Accepted (Phase A scope only; Phase B — live freee HTTP/OAuth client — deferred, see Consequences)
Date: 2026-09-23

## Context

PERSONAL_OS_SPEC.md §24 fixes the target shape for any bank/card integration:

    BANK / CARD / BROKERAGE -> AUTHORIZED DATA PROVIDER -> NORMALIZATION LAYER
    -> PERSONAL DATABASE -> MCP -> AI CLIENT

freee is the first AUTHORIZED DATA PROVIDER: SMBC does not issue personal API
keys directly, but the account is already synced into freee accounting, and
freee publishes a read-only OAuth2 API. Step 19/20 already built the single,
approval-gated `add_transaction` write path (a native macOS dialog approves
each fact; no AI-client-supplied boolean is ever accepted). This ADR defines
how freee-sourced facts reach that same write path, not a new write path.

An exposed OAuth Client Secret (created and then shared outside this
repository, before this ADR) was rotated by creating a new freee application
and deleting the old one, per SECURITY.md's incident response policy. No
freee credential, client ID, or secret has ever been committed to this
repository or referenced by a real value anywhere in it (verified by
`git grep` across all tracked files as part of this ADR).

## Decision

Five points, fixed by the project owner for this integration:

1. **Execution boundary.** OAuth consent, freee API calls, and real-data
   writes happen entirely on the user's own machine, never through this
   repository's CI, never through a cloud sandbox. Credentials live in a
   local, access-restricted file outside version control (see Constraints),
   never in Git, never in chat.
2. **Approval granularity.** A new batch-review-then-approve mechanism is
   added on top of (not replacing) the existing single-transaction
   `add_transaction` approval flow. A human reviews the full candidate list
   and selects which lines to approve; only the approved subset is written.
   Cancelling the review writes nothing.
3. **Normalization / dedup.** Import candidates are identified by
   `(source, external_office_id, external_account_id, external_transaction_id)`.
   A line already imported and unchanged is never re-offered as approvable.
   A line already imported but now reporting a different amount/date is
   surfaced for re-review, never silently re-written or silently ignored.
   Amount sign, currency, and date handling follow Money/ADR-005 and
   ADR-006 exactly (integer minor units, explicit currency, UTC-aware).
   Incoming funds are never auto-classified as revenue — `metric_key` is
   left unset by this integration; classification is a separate, later
   decision.
4. **Direction.** Read-only from freee. Personal OS never writes back to
   freee or to the bank; no transfer, payment, or freee-side mutation
   exists anywhere in this integration.
5. **Design record.** This ADR, plus synthetic-data tests covering
   normalization, dedup (new / unchanged / changed), batch approval
   (approved subset persists, cancelled batch persists nothing), and
   rollback (a failure mid-write leaves neither a Transaction nor its
   ExternalTransactionLink).

### Phase A vs. Phase B

This ADR's Phase A (implemented alongside it) is the vendor-neutral core:
`RawBankTransaction` (Personal OS's own minimal external-fact shape, not
freee's wire format), dedup classification, the batch-approval macOS dialog,
and the atomic per-line write (Transaction + AuditLog +
ExternalTransactionLink in one commit). All of it is exercised only with
synthetic `RawBankTransaction` instances — no live freee call exists yet.

Phase B (a thin `personal_os.adapters.freee` module: OAuth token exchange/
refresh, the actual walletable/deal-fetch HTTP calls, and the mapping from
freee's real JSON response into `RawBankTransaction`) is deliberately not
built in this pass. freee's exact transaction-endpoint field names could not
be confirmed with certainty from public documentation alone during this
work; inventing them would violate this project's standing rule against
guessing an unconfirmed external fact. Phase B must be verified against a
real freee sandbox response by the project owner before being trusted, and
is scoped as a small, isolated follow-up specifically because Phase A's
design keeps it that small: Phase B's only job is producing correctly-typed
`RawBankTransaction` values plus the caller-resolved Personal OS `account_id`
each one belongs to (see Rationale).

## Rationale

- **Why a new ExternalTransactionLink table instead of reusing
  `transactions.metric_key` or `memo` for dedup:** those fields are free-text
  / business-meaning fields, not reliable, indexable identity. A dedicated
  append-only table with a UNIQUE constraint on the four-part identity tuple
  makes duplicate import a DB-enforced impossibility, not just an
  application-level check (same reasoning as ADR-007's UUID PKs and the
  existing FK-based invariants).
- **Why the per-line write does not reuse `FinanceWriteContract.add_transaction`
  internally:** that method opens its own UnitOfWork and commits before
  returning (by design, unchanged from Step 19/20). Adding the
  ExternalTransactionLink write *after* that commit would leave a real gap
  where a Transaction could exist without its dedup link (e.g. a crash
  between the two commits), which would defeat point 3 (no duplicate
  import) the very first time a sync is retried after a partial failure.
  The import path therefore implements its own atomic write, duplicating
  `add_transaction`'s validation (account exists, currency match) rather
  than composing two separate commits. `FinanceWriteContract` itself is
  unmodified — the existing single-item approval method is kept exactly as
  built.
- **Why account mapping (which freee walletable -> which Personal OS
  Account) is the caller's responsibility, not this module's:** it is a
  one-time manual configuration decision, not a runtime inference. Baking
  it into the normalization/dedup service would be exactly the kind of
  "business calculation creeping into a lower layer" this project
  consistently avoids; it belongs in the (not-yet-built) Phase B adapter or
  a small local config file the user maintains.
- **Why a native macOS "choose from list, multiple selections" dialog for
  batch review, rather than a new bespoke UI:** it is fail-closed (an empty
  selection or Cancel approves nothing), request-bound (the exact rows
  shown are the exact rows that can be approved), and requires no new
  dependency — consistent with the existing single-transaction dialog's
  design in `personal_os/approval/macos.py`.

## Alternatives Considered

- **Reusing `FinanceWriteContract.add_transaction` as-is, writing the
  ExternalTransactionLink in a second, separate commit right after:**
  rejected — see Rationale; breaks the no-duplicate-import guarantee under
  a crash between the two commits.
- **Modifying `FinanceWriteContract` to optionally accept a "linked record"
  to write in the same commit:** rejected for this pass — it would change
  an already-implemented, already-tested, already-merged file for a need
  only this one caller has; the small duplication in the dedicated import
  writer is the more conservative change.
- **Inferring freee's transaction JSON shape from SDK/community sources and
  shipping a live client now:** rejected — the sources found during this
  work did not agree on exact field names for the transaction-list endpoint
  specifically; shipping an unverified mapping against real bank data risks
  silently mis-importing real financial facts.
- **Auto-classifying incoming funds as revenue during import:** rejected —
  explicitly excluded by point 3; classification is a distinct, separate
  decision from the fact of a transaction existing.

## Consequences

- Real freee data can only ever reach Personal OS through: OAuth consent on
  the user's machine -> Phase B's (not-yet-built) mapping into
  `RawBankTransaction` -> `stage_import` (dedup, no writes) -> a native
  macOS multi-select approval dialog -> `approve_import` (one atomic commit
  per approved line).
- A second sync of the same statement period is safe: already-imported,
  unchanged lines are never re-offered; changed lines are surfaced, never
  silently overwritten or silently dropped.
- Phase B remains a small, isolated, clearly-scoped follow-up; nothing in
  Phase A needs to change once freee's real response shape is confirmed.

## Constraints

- No freee credential (client ID, client secret, access token, refresh
  token) is ever committed to this repository, placed in chat, or handled
  by any cloud-side tool. Phase B must read them from a local file outside
  version control (e.g. under the private runtime data directory,
  permissions restricted the same way `runtime.py` already restricts the
  database file), never from `.env` alone for the rotating refresh token.
- `personal_os.services.import_review` and `personal_os.domain.external_facts`
  import nothing from `sqlalchemy`, `sqlite3`, `personal_os.database`, or
  `personal_os.adapters` (same architecture-boundary tests that already
  cover the rest of `personal_os.services` cover these automatically).
- No write to freee, SMBC, or any other external system exists anywhere in
  this integration.

## Revisit Triggers

- Phase B's implementation, once freee's real transaction-list response is
  confirmed against a sandbox call — at that point this ADR should be
  amended (not replaced) with the confirmed field mapping.
- A second AUTHORIZED DATA PROVIDER being added (a different bank/card
  aggregator), which should reuse `RawBankTransaction` and
  `ExternalTransactionLink` rather than introduce a parallel shape.
- A future need to auto-classify imported facts (revenue/expense/business
  segment), which is explicitly out of scope here.
