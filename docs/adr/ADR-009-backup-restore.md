# ADR-009: Backup & Restore Strategy

Status: Proposed
Date: 2026-09-22

## Context

ARCHITECTURE.md §10 fixes backup requirements (a backup mechanism must exist before real data is stored; backups must remain outside Git; the destination must support encryption in the future; backups must be versioned; the restore procedure must be tested; database consistency must be preserved) without fixing a specific implementation mechanism. This ADR records the narrowed candidate set considered so far. It is not a final implementation decision, and its status reflects that.

## Decision

Not yet finalized. The leading candidate mechanisms for taking a consistent SQLite backup are:

- the SQLite Online Backup API, and
- SQLite's `VACUUM INTO` statement.

Both provide built-in consistency guarantees without requiring an external dependency. The final choice between them, along with the versioning/retention policy and any encryption wrapper, is deferred to the dedicated backup-implementation phase.

## Rationale

- Naively copying a live SQLite database file cannot guarantee consistency: a write may be mid-transaction, or the WAL file may not yet be checkpointed.
- Both candidate mechanisms avoid this risk natively, without adding a third-party dependency.

## Alternatives Considered

- **Naive file copy**: rejected — no consistency guarantee.
- **Manual WAL checkpoint followed by file copy**: viable, but more manual and more error-prone than either leading candidate.
- **Third-party backup tooling**: not evaluated in depth, since SQLite's own built-in mechanisms already satisfy the consistency requirement without an added dependency.

## Consequences

- No backup mechanism is implemented yet. This ADR records the narrowed candidate set and the fixed requirements it must satisfy, pending a final decision in the backup-implementation phase.

## Constraints

Fixed now, regardless of which candidate is ultimately chosen:

- database consistency must be preserved at the moment of backup
- backups must remain outside Git
- backups must be versioned
- the backup destination must support encryption in the future
- the restore procedure must be tested, not merely assumed to work

## Revisit Triggers

- This ADR is revisited, and its Status updated to Accepted, when the backup-implementation phase begins and a final mechanism is chosen.
