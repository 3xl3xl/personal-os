# ADR-007: Identifier Strategy

Status: Accepted
Date: 2026-09-22

## Context

Personal OS may eventually ingest data from multiple sources — manual entry, a future read-only bank/card provider, and potentially multiple devices. Identifiers must avoid collisions across these sources without requiring central coordination.

## Decision

UUID v4 is used as the primary key type for all entities.

## Rationale

- UUIDs are globally unique without coordination, which matters once data may originate from more than one source.
- UUID is natively supported as a column type in PostgreSQL and is easily stored as `TEXT` in SQLite, keeping the migration path (ADR-002) simple.
- Using a single ID convention everywhere in v0.1 avoids the added complexity of mixing schemes.

## Alternatives Considered

- **Auto-incrementing integers**: simplest and smallest, but risk collisions when merging data from multiple future sources, and do not migrate cleanly to a multi-instance or multi-device future.
- **ULID**: offers creation-time sortability, but would introduce a second ID convention alongside UUID for no clear v0.1 benefit. Time-ordering needs are instead met with an explicit `created_at` column.

## Consequences

- Every table uses a UUID primary key column.
- Sortable listings (e.g. audit logs) rely on a `created_at` timestamp column rather than ID ordering.

## Constraints

- No table uses an auto-incrementing integer as its primary identifier in v0.1.

## Revisit Triggers

- A demonstrated need for ID-embedded creation-order sorting that `created_at` cannot satisfy.
- UUID storage overhead becoming a measurable concern (not expected at this data scale).
