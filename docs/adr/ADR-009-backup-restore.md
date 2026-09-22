# ADR-009: Backup & Restore Strategy

Status: Accepted
Date: 2026-09-22

## Context

ARCHITECTURE.md §10 fixes backup requirements (a backup mechanism must exist before real data is stored; backups must remain outside Git; the destination must support encryption in the future; backups must be versioned; the restore procedure must be tested; database consistency must be preserved) without fixing a specific implementation mechanism. This ADR records the narrowed candidate set considered so far. It is not a final implementation decision, and its status reflects that.

## Decision

Personal OS v0.1 uses the SQLite Online Backup API through Python's standard-library sqlite3.Connection.backup() for both backup and restore.

The implementation accepts explicit source, backup-directory, and restore-destination paths. It has no implicit fallback to the private runtime database. Each snapshot receives a UTC timestamp plus a collision-resistant suffix, so previous snapshots are not overwritten.

Every completed backup and restore is checked with PRAGMA integrity_check. A corrupt or missing backup fails closed.

Encryption is a property of the destination/storage layer, not implemented by the SQLite backup primitive itself. The local backup mechanism remains compatible with an encrypted filesystem or volume without coupling database code to a specific encryption provider.

## Rationale

- Naively copying a live SQLite database file cannot guarantee consistency: a write may be mid-transaction, or the WAL file may not yet be checkpointed.
- Both candidate mechanisms avoid this risk natively, without adding a third-party dependency.

## Alternatives Considered

- **Naive file copy**: rejected — no consistency guarantee.
- **Manual WAL checkpoint followed by file copy**: viable, but more manual and more error-prone than either leading candidate.
- **Third-party backup tooling**: not evaluated in depth, since SQLite's own built-in mechanisms already satisfy the consistency requirement without an added dependency.

## Consequences

- Backup/restore is SQLite-specific persistence infrastructure.
- Versioned snapshots are retained until a future explicit retention policy removes them; Step 12 does not silently delete historical backups.
- Backup encryption is not performed in application code. Production deployment must place the backup directory on an encryption-capable destination before real data is seeded.
- Permission policy remains outside this module. A future caller that restores over a real runtime database must pass through the appropriate explicit-approval boundary.

## Constraints

Fixed now, regardless of which candidate is ultimately chosen:

- database consistency must be preserved at the moment of backup
- backups must remain outside Git
- backups must be versioned
- the backup destination must support encryption in the future
- the restore procedure must be tested, not merely assumed to work

## Revisit Triggers

- This ADR is revisited, and its Status updated to Accepted, when the backup-implementation phase begins and a final mechanism is chosen.
