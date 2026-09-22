# ADR-010: Testing Strategy

Status: Accepted
Date: 2026-09-22

## Context

PERSONAL_OS_SPEC.md §21 and §34 require automated tests verifying core calculations. Financial-calculation correctness is the highest-stakes correctness requirement in this system.

## Decision

Use pytest as the testing framework for all Python code, with particular emphasis on parametrized tests covering financial-calculation edge cases: rounding boundaries, currency handling, timezone/date boundaries, and permission-policy enforcement.

## Rationale

- pytest is the de facto standard Python testing framework, with minimal boilerplate and strong parametrization support well suited to exhaustively testing numeric/financial edge cases.
- It is well represented in AI training data, easing AI-assisted test authoring and maintenance across AI clients.

## Alternatives Considered

- **unittest (standard library)**: viable, but more boilerplate and less ergonomic parametrization than pytest.
- **Other frameworks (e.g. nose2)**: less active ecosystem momentum.

## Consequences

- All Repository/Service Layer logic — especially `Money` arithmetic (ADR-005) and TaxRule-driven calculations (ADR-011) — requires test coverage before being considered complete.
- Permission-policy boundaries (READ / LOCAL PERSONAL DATA WRITE / EXTERNAL WRITE / FINANCIAL EXECUTION, per ARCHITECTURE.md §6) must have explicit tests confirming enforcement.

## Constraints

- No financial calculation logic is considered complete without accompanying tests.
- Rounding-mode-dependent code (ADR-005) must be tested for the specific rounding behavior it declares, since no global default exists to fall back on.

## Revisit Triggers

- A material change in pytest's maintenance status.
- A demonstrated testing gap (e.g. a need for property-based testing of financial edge cases) suggesting a complementary tool (e.g. Hypothesis) be added — additive, not a replacement of this decision.
