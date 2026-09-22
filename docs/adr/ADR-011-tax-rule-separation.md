# ADR-011: Tax Rule Separation

Status: Accepted
Date: 2026-09-22

## Context

PERSONAL_OS_SPEC.md §13 requires tax rules to be versioned and assumption-driven, and explicitly prohibits hard-coding a single universal tax percentage. Pydantic validation (ADR-004) enforces the structure of data passed into the system, but it cannot detect or prevent a jurisdiction-specific rate or threshold written as an anonymous literal inside calculation logic itself.

## Decision

Jurisdiction-specific tax rates and thresholds must not appear as anonymous literals inside calculation logic. Tax calculations must receive applicable rules through versioned `TaxRule` data/configuration, passed explicitly into the calculation function — never embedded as a bare number inside it.

`TaxRule` must support, at minimum:

- jurisdiction
- effective_from / tax_year
- rule identifier / version
- source
- last_verified_at
- assumption / status

Tax calculation logic and TaxRule data are kept strictly separate.

## Rationale

- Separating tax-rule data from calculation logic means a tax-law change is handled by adding or updating `TaxRule` data, not by editing and re-verifying calculation code.
- It makes every tax calculation traceable to a specific, dated, sourced rule rather than an opaque constant, directly satisfying spec §13's versioning/assumption-tracking requirement.

## Alternatives Considered

- **Relying solely on Pydantic validation of TaxRule inputs**: rejected as insufficient on its own — validation cannot detect a hard-coded literal written inside a function body; it only validates the shape of data explicitly passed through it.
- **A single global tax-configuration constant**: rejected — PERSONAL_OS_SPEC.md §13 explicitly requires rules to be versioned per jurisdiction and year, which a single constant cannot express.

## Consequences

- Every tax-related calculation function takes a `TaxRule` (or an applicable set of `TaxRule`s) as an explicit parameter.
- Adding lint tooling to detect suspicious bare numeric literals in tax-related modules is identified as a valuable future reinforcement, but is not implemented as part of this decision.

## Constraints

- Pydantic validation alone does not prevent tax hard-coding and must not be relied upon as sufficient on its own.
- Code review (human or AI) is required to enforce this principle until, and unless, a lint rule is built to check it automatically.

## Revisit Triggers

- A lint/static-analysis rule being built to automatically detect hard-coded tax literals (this ADR would then be revised to reference that tooling as an additional enforcement mechanism).
- A jurisdiction's rule structure proving impossible to express with the minimum `TaxRule` fields listed above.
