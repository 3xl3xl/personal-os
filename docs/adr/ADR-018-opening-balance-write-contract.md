# ADR-018: Opening balance transaction write contract

Status: Accepted
Date: 2026-09-26

## Context

`domain/enums.py::TransactionKind` has defined `OPENING_BALANCE` since the
initial Finance v0.1 schema ("synthetic transaction used to bootstrap a
pre-existing account balance") but no write path for it has ever existed.
ADR-012, which introduced the single approved `add_transaction` write,
explicitly scoped this out: "Transfer, opening-balance bootstrap,
corrections, voiding, reallocations, revenue/expense wrappers, goals and
opportunities are outside this contract."

This gap surfaced when moving Personal OS from synthetic/test data to the
user's real accounts (per the decision to defer a Work/Time domain and
instead validate Finance with real data). A first real Account was created
via ADR-015's `add_account`, but `net_worth()` correctly raises
`NoFinancialDataError` for an account with zero transactions -- there is no
existing fact from which to derive a currency-bearing balance. To bootstrap
the real starting balance as of 2026-01-01 and accumulate real transactions
from there (rather than back-filling every historical transaction), an
approved `OPENING_BALANCE` write is required.

## Decision

Add one new write: a single `ACTIVE`, `OPENING_BALANCE` Transaction.
Mirrors `add_transaction`'s shape closely, with two differences:

- Input: `id`, `account_id`, `amount`, `occurred_at`, `memo`. No
  `metric_key` -- an opening balance is a bootstrap fact about the account,
  not an observation tied to a tracked metric. `transaction_type` and
  `status` are not accepted as input; they are fixed to `OPENING_BALANCE`
  and `ACTIVE` respectively, same rationale as `add_transaction` fixing
  them to `NORMAL`/`ACTIVE`.
- Invariant: permission check (`OperationClass.LOCAL_PERSONAL_DATA_WRITE`,
  requires explicit human approval) -> reference/currency checks ->
  Transaction write -> AuditLog write -> single commit. Failure at any
  stage leaves zero new Transaction rows and zero new AuditLog rows.
- Reference checks, in order: the account must exist; the transaction
  currency must match the account currency; the transaction ID must be
  unused; **the account must not already have an `OPENING_BALANCE`
  transaction.** This last check is new -- `add_transaction` has no
  equivalent, since NORMAL transactions are never singular per account.
  It is read via `TransactionRepositoryProtocol.list_by_account` (already
  used by `services/finance.py::net_worth`), filtered in the Service layer
  for an existing `OPENING_BALANCE` row; no new repository method or
  schema constraint is added.
- Approval: a new, dedicated native macOS dialog
  (`approval/_opening_balance.py::confirm_opening_balance`), not a change
  to `approval/macos.py::confirm_transaction`.

## Rationale

- **Why a new `OpeningBalanceWriteContract` instead of a method on
  `FinanceWriteContract`, or a relaxed `AddTransactionInput`:**
  `services/write_contract.py` and `domain/write_contracts.py` are the
  exact Step 19/20 files ADR-012 describes as closed to this scope; this
  project's established pattern (ADR-014, ADR-015) is additive parallel
  modules for a new write shape, never edits to an already-tested one.
  `canonical_transaction` is reused as-is from `domain/write_contracts.py`
  (imported, not duplicated) since it already serializes `transaction_type`
  generically for any `TransactionKind`.
- **Why "at most one `OPENING_BALANCE` per account" and nothing stronger:**
  the domain enum's own docstring describes bootstrapping *a* balance,
  singular, and every Finance v0.1 calculation that exists today
  (`net_worth`, etc.) sums all `ACTIVE` transactions regardless of type or
  order -- so no chronological-ordering rule (e.g. "must precede every
  NORMAL transaction") is invented here. Matches ADR-012's own restraint:
  "No new closed-account or historical-date policy is invented here."
- **Why no `metric_key`:** kept minimal, matching `add_account`'s
  precedent of accepting only what has an immediate real use; can be added
  later without breaking this contract if a real need appears.
- **Why a new dialog instead of reusing `confirm_transaction`:** same
  precedent as ADR-015 -- a separate, equally fail-closed dialog keeps
  `approval/macos.py` untouched.

## Alternatives Considered

- **Extending `AddTransactionInput`/`FinanceWriteContract` with an optional
  `transaction_type`:** rejected -- reopens an already-merged, already-tested
  file that ADR-012 deliberately closed off, and would let a caller pass
  `TRANSFER` too, which is explicitly out of scope everywhere.
- **Back-filling one NORMAL transaction per historical event instead of a
  single opening balance:** rejected by the user -- the real goal is a
  single 2026-01-01 starting fact, with real transactions (including a
  future freee import) accumulating forward from it.
- **Enforcing that the opening balance's `occurred_at` precede every
  existing NORMAL transaction on the account:** rejected -- no current
  calculation needs this ordering, and the account in question has zero
  existing transactions; inventing the rule now would be speculative.

## Consequences

- A real Account can now be bootstrapped with its actual 2026-01-01
  balance through the same audited, human-approved path as any other
  write, via a new `add_opening_balance` MCP tool.
- `get_net_worth` and other Finance v0.1 reads can return a real value
  for an account that has this one fact, instead of raising
  `NoFinancialDataError`.

## Constraints

- `services/opening_balance_write_contract.py` and
  `domain/opening_balance_write_contracts.py` import nothing from
  `sqlalchemy`, `sqlite3`, `personal_os.database`, or
  `personal_os.adapters` (covered by the same architecture-boundary test
  pattern as the rest of `personal_os.services`).
- No correction, void, or update path for an existing `OPENING_BALANCE`
  transaction is introduced by this ADR.

## Revisit Triggers

- A future need to correct or replace an existing opening balance (e.g. it
  was entered wrong) -- a separate write contract, not an extension of this
  one's input shape.
- A future Finance calculation that needs to treat `OPENING_BALANCE`
  differently from `NORMAL` (e.g. excluding it from a "monthly activity"
  view) -- this ADR does not add that distinction anywhere in `finance.py`.
