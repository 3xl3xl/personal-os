# ADR-015: Local Account Write Contract

Status: Accepted
Date: 2026-09-23

## Context

Step 19/20 built the single, approval-gated `add_transaction` write path
(`services/write_contract.py`'s `FinanceWriteContract`), but every
Transaction requires an existing `account_id`. No approved-write path for
*creating* an Account has ever existed: `repository/accounts.py` has a bare
`AccountRepository.add()`, but nothing above it enforces permission check ->
write -> audit -> single commit the way every other local write does.

This gap surfaced while scoping the freee read-only import (ADR-014): before
any real bank statement line can be imported, a real Personal OS Account
must exist for it to post against, and there was no sanctioned way to create
one. Writing directly through `AccountRepository.add()` from outside a
Service would bypass this project's standing invariant that every write
passes through permission -> write -> audit -> single commit, so that path
was rejected outright rather than used as a shortcut.

## Decision

Add one new write: creating a single new, `ACTIVE` Account. Mirrors
`add_transaction`'s shape exactly:

- Input: `id`, `name`, `account_type`, `currency_code`, `opened_at`. No
  `status` field is accepted — a newly created Account is always `ACTIVE`;
  closing, renaming, or otherwise transitioning an existing Account is out
  of scope for this ADR.
- Invariant: permission check (`OperationClass.LOCAL_PERSONAL_DATA_WRITE`,
  requires explicit human approval) -> Account write -> AuditLog write ->
  single commit. Failure at any stage leaves zero Account rows and zero
  AuditLog rows (same rollback guarantee as `add_transaction`).
- A duplicate `id` is rejected (`WriteReferenceError`) before any write,
  exactly like `add_transaction`'s duplicate-transaction-ID check.
- Approval: a new, dedicated native macOS dialog
  (`approval/_account.py::confirm_account`), not a change to
  `approval/macos.py::confirm_transaction`.

## Rationale

- **Why a new `AccountWriteContract` instead of a method on the existing
  `FinanceWriteContract`:** that class and its Step 19/20 tests are left
  completely unmodified, matching this project's established pattern of
  adding parallel modules for new write shapes rather than editing
  already-tested ones (see ADR-014's identical reasoning for
  `services/import_review.py`).
- **Why a new dialog instead of reusing `confirm_transaction`:** the
  existing dialog's prompt, title, and JSON shape are written specifically
  for a Transaction; a separate, equally fail-closed dialog keeps
  `approval/macos.py` untouched, matching the precedent already set by
  `approval/_batch_import.py`.
- **Why `status` is not an input field:** there is no Account-close or
  Account-update write path yet. Accepting a `status` value that has no
  corresponding transition logic would let a caller silently create a
  `CLOSED` account with no history explaining why, which contradicts
  Fact != Inference (spec 2.4) as much as an invented value would.

## Alternatives Considered

- **Extending `FinanceWriteContract` with an `add_account` method:**
  rejected — see Rationale; keeps an already-merged, already-tested file
  untouched.
- **Accepting `status` as an optional input:** rejected — no legitimate
  reason exists yet to create an Account in any state other than `ACTIVE`;
  this can be revisited once a close/reopen write path is designed.
- **Skipping this ADR and writing directly via `AccountRepository.add()`
  from the freee import composition:** rejected outright — bypasses the
  permission/audit invariant every other write in this project honors.

## Consequences

- A real Account (e.g. an SMBC-linked wallet) can now be created through the
  same audited, human-approved path as a Transaction, on the user's own
  Mac, via a new `add_account` MCP tool.
- The freee import work (ADR-014, and its Option 2 follow-up) can rely on a
  real target `account_id` existing before any real import is attempted.

## Constraints

- `services/account_write_contract.py` and
  `domain/account_write_contracts.py` import nothing from `sqlalchemy`,
  `sqlite3`, `personal_os.database`, or `personal_os.adapters` (covered by
  the same architecture-boundary test pattern as the rest of
  `personal_os.services`).
- No Account update, close, or delete path is introduced by this ADR.

## Revisit Triggers

- A future need to close, reopen, or rename an existing Account -- a
  separate write contract, not an extension of this one's input shape.
- A future need to create more than one Account per approval (e.g. bulk
  onboarding), which is deliberately out of scope here (one Account, one
  dialog, same as `add_transaction`).
