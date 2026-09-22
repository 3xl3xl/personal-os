# ADR-005: Money Representation

Status: Accepted
Date: 2026-09-22

## Context

PERSONAL_OS_SPEC.md §11 requires Revenue, Profit, Take-home, Available Cash, and Net Worth to be treated as distinct fields and calculations, never conflated. Binary floating point must never be used for financial data.

## Decision

- Binary floating point is prohibited anywhere in the money-handling path.
- Stored money is represented as integer minor units in the database.
- Every monetary field is accompanied by a required `currency_code` (ISO 4217).
- Arithmetic requiring precision (percentages, proration, tax computation, and similar) uses Python's `Decimal` type.
- A dedicated `Money` value object encapsulates an integer minor-units amount together with its currency code, and exposes only explicit, safe arithmetic operations.
- Rounding rules are **not** given a Personal-OS-wide global default. Rounding belongs to the specific business/tax/accounting rule that requires it, and every rounding decision must be explicit (the caller specifies the rounding mode) and testable.

## Rationale

- Integer minor units avoid floating-point and decimal-scale ambiguity at the storage layer, and behave identically across SQLite and PostgreSQL.
- `Decimal` avoids binary-float imprecision for calculations that require it.
- Different domains legitimately require different rounding conventions (e.g. a tax rule may require truncation, an invoicing rule may require round-half-up); fixing a single global default would risk silently misapplying the wrong convention to a domain that needs a different one.

## Alternatives Considered

- **Storing money as `DECIMAL`/`NUMERIC` directly in the database**: viable, but integer minor units are simpler to reason about across SQLite/PostgreSQL dialect differences and avoid implicit scale/precision mismatches between the two engines.
- **Fixing a single global rounding mode (e.g. `ROUND_HALF_EVEN`) as a system-wide default**: considered and explicitly rejected. An earlier draft of this decision proposed this; it was reversed in favor of the per-rule, explicit approach described above.

## Consequences

- Every calculation that divides or apportions a `Money` value must explicitly pass a rounding mode; there is no implicit "just round for me" default anywhere in the system.
- TaxRule and other business-rule definitions (ADR-011) are responsible for specifying their own applicable rounding behavior where relevant.

## Constraints

- Binary float is prohibited for money.
- Stored money is always integer minor units.
- `currency_code` is required on every monetary field.
- Precise arithmetic uses `Decimal`.
- A dedicated `Money` value object is the only sanctioned way to perform monetary arithmetic.
- Rounding rules have no Personal-OS-wide global default.
- Rounding is owned by the relevant business/tax/accounting rule.
- Rounding decisions must be explicit and testable.

## Revisit Triggers

- A genuine, demonstrated operational need for a universal default rounding behavior (this ADR anticipates such a need is unlikely, and if it arises it should be explicitly re-justified rather than assumed).
- Python's `Decimal` proving insufficient for a specific calculation domain.
