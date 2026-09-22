# ADR-001: Core Language & Runtime

Status: Accepted
Date: 2026-09-22

## Context

Personal OS is intended to be owned and maintained by a single person for five or more years, with AI clients (Claude, ChatGPT, and future AI clients) rotating as the acting implementer/maintainer over that time. The language choice must serve human maintainability, AI maintainability across multiple AI vendors, financial-calculation reliability, and long-term stability, without over-engineering v0.1 (PERSONAL_OS_SPEC.md §10).

## Decision

Python (3.12+) is the core implementation language for Personal OS's Service Layer, Repository Layer, and Adapter layer.

## Rationale

- The standard library includes an arbitrary-precision `Decimal` type, directly supporting the money-handling requirements in ADR-005.
- Python is heavily represented in the training and tool-use ability of multiple AI systems, supporting the goal that any AI client can read, write, and maintain this codebase (spec §2.2).
- The SQLite/PostgreSQL ORM ecosystem for Python (SQLAlchemy + Alembic, see ADR-002) is mature and directly serves the migration path in ARCHITECTURE.md §7.
- Python favors readability, which matters for a single human maintainer returning to the codebase after long gaps.
- A mature, actively maintained MCP SDK is available for Python (see ADR-003).

## Alternatives Considered

- **TypeScript**: stronger compile-time type safety, but no built-in arbitrary-precision decimal type (would require an external library), and faster churn in surrounding tooling/frameworks than Python's core ecosystem.
- **Go / Rust**: strong long-term stability and security properties, but weaker representation in AI-assisted code generation/maintenance and higher verbosity for a solo maintainer's day-to-day work.

## Consequences

- All Core and Adapter code is written in Python.
- Dependency management follows Python tooling conventions (see ADR-008).
- Any future human contributor or AI agent works within a single-language codebase, reducing cross-language coordination overhead.

## Constraints

- Core code must not depend on any AI vendor's SDK or tooling (see ADR-003); the language choice does not exempt Core from that separation.

## Revisit Triggers

- A significant, sustained shift in AI maintainability toward a different language across major AI providers.
- Python's `Decimal`/typing ecosystem proving insufficient for a specific, demonstrated need.
- Concurrency or performance requirements emerging that a straightforward Python process cannot reasonably meet.
