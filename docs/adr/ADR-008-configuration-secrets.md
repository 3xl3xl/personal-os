# ADR-008: Configuration & Secrets Management

Status: Accepted
Date: 2026-09-22

## Context

SECURITY.md requires that secrets be provided via environment variables or a secure secret store, and never hardcoded or committed to the repository. v0.1 has a minimal secret surface (SQLite requires no credentials), but the private data store's location and any future credentials must still be handled safely.

## Decision

Configuration — including the private data store's file path — is provided via environment variables, documented via a checked-in `.env.example` containing variable names only, never real values. A future secure secret store (an OS keychain or a dedicated secrets manager) is the documented path for any credentials introduced by future integrations, such as a bank/card read-only provider.

## Rationale

- This matches SECURITY.md's existing policy directly.
- Environment variables are simple and sufficient for v0.1's near-zero secret surface.
- This keeps the door open to stronger secret storage later without requiring it prematurely, consistent with v0.1's simplicity requirement (PERSONAL_OS_SPEC.md §10).

## Alternatives Considered

- **Hardcoded configuration**: rejected outright — violates SECURITY.md.
- **A local config file with real values checked into the repository**: rejected — carries the same commit-exposure risk as hardcoding.
- **Adopting a full secrets-manager integration now**: rejected as premature; v0.1's actual secret surface is currently empty.

## Consequences

- The private database's location and any other environment-specific settings are read from environment variables at runtime, never hardcoded into source.
- `.env.example` documents required variable names only.

## Constraints

- No real secret or credential value is ever committed to the Git repository. Only `.env.example` may be committed (per `.gitignore`); `.env` itself is excluded.

## Revisit Triggers

- A future integration (e.g. a bank/card read-only provider) introducing actual credentials, which would warrant moving to a proper secret store for defense in depth rather than continuing with plain environment variables alone.
