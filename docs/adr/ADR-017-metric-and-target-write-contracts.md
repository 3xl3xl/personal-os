# ADR-017: FinancialMetric and Target (Q4/Q5) Write Contracts

Status: Accepted
Date: 2026-09-23

## Context

`get_goal_gap` (Q4) and `get_required_revenue` (Q5) are already implemented
and read-tested, but both compare "Derived Actual" against a target value
stored in `financial_targets` / `monthly_targets`. Scoping the project
owner's request to actually use these reads with real data surfaced that no
approved-write path exists to create either row -- the same gap ADR-015
found and fixed for Account, now found one layer deeper.

Both `financial_targets.metric_key` and `monthly_targets.metric_key` carry
a DB-level foreign key to `financial_metrics.key` (see
`database/schema/financial_targets.py` / `monthly_targets.py`), so a target
cannot be written at all until its `FinancialMetric` exists -- and no
approved-write path existed for that either. `repository/financial_metrics.py`,
`repository/financial_targets.py`, and `repository/monthly_targets.py` each
only ever had a bare `add()`; nothing above them enforced permission check
-> write -> audit -> single commit.

## Decision

Two new write contracts, both following `add_transaction`'s and
`add_account`'s exact shape:

1. **`MetricWriteContract.add_metric`** -- registers one `FinancialMetric`
   (`key`, `display_name`). Rejects a duplicate `key` before any write
   (`WriteReferenceError`). This does not set any target value -- it only
   declares that a KPI with this key exists, exactly as
   `database/schema/financial_metrics.py`'s docstring scopes it ("a tracked
   KPI, never a stand-in for revenue source, business category, or
   accounting category").
2. **`TargetWriteContract.add_financial_target`** (Q4) and
   **`.add_monthly_target`** (Q5) -- each appends one new version of a
   target. Both require the referenced `metric_key` to already exist
   (`WriteReferenceError` otherwise) and reject a duplicate
   `(metric_key, effective_from)` / `(metric_key, year, month,
   effective_from)` before any write, matching the append/version-only
   design already fixed by Step 4 (no update or delete method exists at the
   Repository layer; a changed target is a new row with a later
   `effective_from`).

Same invariant as every other write in this project: permission check ->
write -> AuditLog write -> single commit; failure at any stage leaves zero
rows of either kind.

Two new, dedicated native macOS dialogs
(`approval/_metric.py::confirm_metric`,
`approval/_target.py::confirm_financial_target`/`confirm_monthly_target`),
not changes to `approval/macos.py`.

## Rationale

- **Why `TargetWriteContract` holds both Q4 and Q5's write methods instead
  of two separate contract classes:** `FinancialTargetRecord` and
  `MonthlyTargetRecord` are the same append/version-only family (identical
  versioning rule, identical schema docstring reasoning, identical FK to
  `financial_metrics`), and the spec documents Q4/Q5 together. Splitting
  them into two classes would duplicate the metric-exists check and the
  duplicate-`effective_from` check for no isolation benefit -- unlike
  Account vs. Transaction, which are genuinely different entities.
- **Why `MetricWriteContract` is still its own separate contract, not a
  method on `TargetWriteContract`:** a metric can meaningfully exist with
  zero targets (a KPI you track but haven't set a number for yet); folding
  metric creation into the target contract would force every metric
  registration through a target-shaped call.
- **Why neither is a method on `FinanceWriteContract` or
  `AccountWriteContract`:** identical reasoning to ADR-015 -- those classes
  and their tests stay completely unmodified; a new write shape gets a new
  parallel module.
- **Why the duplicate-`effective_from` check reads every existing version
  via `list_by_metric()` / `list_by_metric_year_month()` rather than
  relying solely on the DB's `UniqueConstraint`:** matches this project's
  established defense-in-depth pattern (ADR-014's dedup identity check does
  the same) -- the application-level check produces a clean
  `WriteReferenceError` before any write is attempted, while the DB
  constraint remains as the real guarantee against a race.

## Alternatives Considered

- **Extending `AccountWriteContract` or `FinanceWriteContract` with these
  methods:** rejected -- see Rationale and ADR-015.
- **A single `TargetWriteContract.add_target()` method taking an optional
  `year`/`month`:** rejected -- the two write shapes have different
  required fields and different uniqueness keys; two explicit methods (and
  two explicit MCP tools) keep the input contract precise, matching
  `AddTransactionInput`'s "NORMAL/ACTIVE only, no ambiguous optional shape"
  precedent.
- **Auto-creating a `FinancialMetric` the first time a target references an
  unknown key:** rejected -- would let a typo'd `metric_key` silently
  create a permanent KPI definition with no `display_name` the user chose;
  `WriteReferenceError` makes the missing prerequisite visible instead.

## Consequences

- `get_goal_gap` and `get_required_revenue` can now be exercised with real,
  user-approved target values, on the user's own Mac, through the same
  audited path as every other write.
- Registering a metric and setting its first target are two separate
  approved actions (two dialogs), not one -- consistent with how creating
  an Account and posting a Transaction against it are already separate
  steps.

## Constraints

- `services/metric_write_contract.py`, `domain/metric_write_contracts.py`,
  `services/target_write_contract.py`, and `domain/target_write_contracts.py`
  import nothing from `sqlalchemy`, `sqlite3`, `personal_os.database`, or
  `personal_os.adapters` (covered by the same architecture-boundary test
  pattern as the rest of `personal_os.services`).
- No update, delete, or "supersede a version" write is introduced by this
  ADR -- only append.

## Revisit Triggers

- A future need to deprecate or retire a `FinancialMetric` (it is currently
  permanent once created).
- A future need to delete or correct a mistakenly-created target version --
  today the only recovery is appending a corrected version with a later
  `effective_from`; the mistaken version stays in history.
