# ADR-006: Date/Time & Jurisdiction Handling

Status: Accepted
Date: 2026-09-22

## Context

Personal OS is architected to potentially support multiple countries/timezones over its multi-year lifetime. Tax year boundaries and other jurisdiction-specific rules (PERSONAL_OS_SPEC.md §13, §14) depend on correct local-time evaluation.

## Decision

All datetimes are timezone-aware. The database stores all datetimes in UTC. Local-time evaluation (e.g. for tax-year boundaries or other jurisdiction-specific rules) happens only at the point of business-rule evaluation, using Python's standard library `zoneinfo`.

## Rationale

- Naive (timezone-unaware) datetimes are a well-known source of subtle bugs in any system that may span multiple timezones or jurisdictions.
- Centralizing storage in UTC, with explicit local-time conversion only where a rule requires it, keeps ambiguity out of the persistence layer.

## Alternatives Considered

- **Storing local time directly**: rejected — ambiguous across daylight-saving transitions and unworkable for multi-jurisdiction use.
- **Storing both UTC and local time redundantly**: rejected for v0.1 — adds complexity without a demonstrated need.

## Consequences

- Any code evaluating a jurisdiction-specific rule (e.g. a tax-year cutoff) must explicitly convert from UTC to the relevant local timezone, using the jurisdiction recorded in the relevant TaxRule (ADR-011) or other jurisdiction data — never an assumed, fixed timezone.

## Constraints

- Naive (timezone-unaware) datetime values are disallowed anywhere in the codebase.

## Revisit Triggers

- Multi-region operation revealing jurisdiction/time complexity not covered by UTC-storage-plus-local-evaluation (e.g. needing historical timezone-rule data for a jurisdiction whose offset rules have changed over time).
