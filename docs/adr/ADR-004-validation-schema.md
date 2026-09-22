# ADR-004: Validation & Schema Strategy

Status: Accepted
Date: 2026-09-22

## Context

Personal OS needs structural validation for MCP tool inputs/outputs and internal domain models, including enforcing required fields on structured data such as TaxRule (ADR-011).

## Decision

Use Pydantic v2 for data validation and schema definition across the Service Layer's input/output boundaries and internal domain models.

## Rationale

- Pydantic is mature, widely used, and integrates naturally with typed Python.
- It structurally enforces required fields and types (e.g. a required `currency_code`, or TaxRule's required fields), catching missing/malformed data early.
- It is heavily represented in AI training data, easing AI-assisted authoring and maintenance of validation schemas.

## Alternatives Considered

- **Hand-written validation functions**: more direct control, but more boilerplate and more room for inconsistent enforcement across the codebase.
- **Other validation libraries (e.g. marshmallow, attrs+cattrs)**: viable, but with less ecosystem momentum and less AI-authoring familiarity than Pydantic v2.

## Consequences

- All MCP tool schemas and internal domain models are defined as Pydantic models.
- Validation errors surface early and consistently at Service Layer boundaries.

## Constraints

- Pydantic validation enforces data *structure* only. It does not, and cannot, prevent a hard-coded literal value (e.g. a tax rate) from being written inside calculation logic. It must never be relied upon as the sole safeguard against tax/rate hard-coding — see ADR-011 for the dedicated principle covering that risk.

## Revisit Triggers

- Pydantic v2 being superseded by a materially better-suited library for this codebase's needs.
- Validation overhead becoming a measurable performance concern (not expected at this scale).
