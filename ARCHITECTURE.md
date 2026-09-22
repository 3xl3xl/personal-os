# Personal OS — Architecture (v0.1)

This document describes the v0.1 architecture for Personal OS. It follows [`PERSONAL_OS_SPEC.md`](./PERSONAL_OS_SPEC.md) (the master specification) and [`SECURITY.md`](./SECURITY.md) (the security policy). Where this document discusses implementation shape, PERSONAL_OS_SPEC.md remains the source of truth for *what* Personal OS must do; this document is about *how* v0.1 is structured to do it.

Nothing described here has been implemented yet. This document defines the architecture only.

## 1. Recommended Architecture

```
AI Client (Claude / ChatGPT / future AI)
        ↓  tool calls
MCP Server  (+ thin REST adapter, added only when a client needs it)
        ↓  plain function calls
Application / Service Layer   ← permission enforcement (single point) + calculations + audit logging
        ↓  plain function calls
Repository / Data Access Layer  ← the only architectural layer that knows the persistence implementation
        ↓
SQLite file, outside the Git repository
```

The Repository / Data Access Layer is a layer, not a single file. It may be split into multiple modules (e.g. one per domain: finance, goals, revenue) as the system grows. What matters architecturally is the boundary: everything above this layer (Service Layer, MCP/REST adapters, AI clients) never knows whether the underlying store is SQLite, PostgreSQL, or anything else.

## 2. Alternatives Considered

### A. Private Data Store

| Option | Verdict for v0.1 | Why |
|---|---|---|
| **SQLite, local (recommended)** | Selected | No server process, no credentials to manage, a single file that is trivial to reason about and back up, sufficient ACID guarantees for single-user data at this scale, and can be wrapped by an ORM/query layer that also supports PostgreSQL later. |
| PostgreSQL, local | Rejected for v0.1 | Requires a running server process and credential management for no benefit a single user needs today. Revisit if/when multi-device concurrent access is needed. |
| Cloud PostgreSQL | Rejected for v0.1 | Adds a network dependency, hosting cost, and a new trust boundary (data leaving the local machine) before the system has even been used with real data. Section 24 of the master specification explicitly treats bank/cloud integration as future scope. |
| Flat files (JSON/CSV) | Rejected | No transactional integrity; not suitable for the finance calculations in spec §11–13. |

### B. AI Access Layer

| Option | Verdict | Why |
|---|---|---|
| **MCP + internal Service Layer (recommended)** | Selected | MCP is the interface Claude speaks natively today. Keeping all business logic in a separate Service Layer underneath MCP (rather than inside MCP tool handlers) means MCP remains a swappable protocol adapter, per spec §2.2 (model-agnostic). |
| MCP only, no separate service layer | Rejected | Would embed permission policy (§4) and calculations (§11–13) inside MCP tool handlers, which would need to be untangled the moment a second adapter (e.g. REST for ChatGPT) is added. |
| REST API only | Rejected for v0.1 | Claude's tool-calling story is built around MCP today; building REST first would mean building a Claude-facing MCP adapter later regardless. |

Note on future AI client integration: the exact mechanism a given future AI client (e.g. ChatGPT) will use to connect — native MCP support, a REST-based action/plugin interface, or something else — is not fixed by this architecture and is not assumed here. Whatever adapter is eventually needed talks to the same Service Layer, so this is an additive change, not a rewrite.

### C. Data Access Architecture

See the diagram in §1. Only the Repository/Data Access Layer contains persistence-specific code. The Service Layer works exclusively with plain domain objects.

## 3. Tradeoffs

- SQLite trades multi-device concurrent write support for zero operational overhead — appropriate for a single user on one machine; would need revisiting before supporting concurrent writers.
- Building MCP first (no REST yet) trades "a non-MCP client can connect today" for "no unused interface is built speculatively."
- Storing the private database in a plain sibling directory (`~/PersonalOS-data/`) rather than an OS-idiomatic hidden path trades a small amount of platform convention for something that is simple to locate, inspect, and back up by hand — consistent with the v0.1 simplicity requirement (spec §10).
- Starting all local-data writes behind an explicit-approval gate (§6 below) trades some day-to-day convenience (every write needs confirmation) for safety: no code path exists in v0.1 by which an AI client can silently alter financial records. Autonomy can be extended later as a deliberate policy change, not as a default.
- Keeping the Repository/Data Access Layer strictly the only layer aware of the persistence implementation adds a small amount of interface boilerplate, in exchange for a SQLite → PostgreSQL migration that does not require rewriting the Service Layer, MCP/REST adapters, or any AI client integration.

## 4. Directory Structure

Inside the Git repository (code, schema definitions, policy, and documentation only):

```
personal-os/
  README.md
  PERSONAL_OS_SPEC.md
  SECURITY.md
  ARCHITECTURE.md
  .gitignore
  core/
  database/
    schema/                ← table/entity definitions (structure only, never data)
    migrations/             ← versioned migration scripts
  mcp/
    server.*                ← MCP tool adapter (thin)
  modules/
    finance/
    goals/
    revenue/
    time/
  policies/
    permissions.yaml
  tests/
  docs/
```

Outside the Git repository, on the local machine (never committed):

```
~/PersonalOS-data/
  personal_os.db            ← the only place real personal data lives
  backups/                  ← see §10, Backup Architecture
```

This directory tree is a target, not something to be generated wholesale now. Per spec §29, components are created only when needed.

## 5. Data Flow

**Read example** — "What is my current financial state?" (spec §32):

```
AI Client (get_financial_state)
  → MCP/REST adapter → Service Layer → Repository Layer → SQLite
  ← result tagged ACTUAL / TARGET / FORECAST / ASSUMPTION (per spec §32)
```

Reads are automatic; no approval step, though writes to the audit log are not required for reads.

**Write example** — `add_expense`, reflecting the v0.1 permission model (§6):

```
AI Client (add_expense tool call)
  → MCP/REST adapter → Service Layer
  → Service Layer classifies the operation as LOCAL PERSONAL DATA WRITE
  → Service Layer requests explicit user approval before proceeding
       (the AI proposes; it does not commit the change itself)
  → only once the user approves:
       → Repository Layer writes to SQLite
       → an entry is recorded in audit_logs (actor, old_value, new_value, reason, approval_status)
```

Writes to external systems and any attempted financial execution follow the same single decision point in the Service Layer (§6); no permission logic exists in the MCP or REST handlers themselves.

## 6. Trust Boundaries

1. **AI Client ↔ MCP/REST adapter** — tool-call arguments are treated as untrusted input and validated before use, regardless of which AI client issued them.
2. **MCP/REST ↔ Service Layer — the single enforcement point for permission policy.** Every operation is classified into exactly one of:
   - `READ` → automatic
   - `LOCAL PERSONAL DATA WRITE` → explicit user approval required
   - `EXTERNAL WRITE` → explicit user approval required
   - `FINANCIAL EXECUTION` → blocked (no implementation exists for this category in v0.1)
3. **Service Layer ↔ Repository Layer** — internal only; no permission logic here, purely data access.
4. **Repository/process ↔ filesystem** — protected by OS file permissions (directory `700`, database file `600`) plus whole-disk encryption (e.g. FileVault) as the baseline.
5. **(Future) Provider Adapter ↔ external bank/card API** — strictly read-only; any such credentials never enter the AI client's request context.

## 7. Migration Path

```
2026 — v0.1
SQLite file on the local machine, accessed through an ORM/query layer
that also supports PostgreSQL
        ↓ (when multi-device access, cloud hosting, or bank integration requires it)
2027+ — PostgreSQL (local or cloud)
```

The guarantee this architecture makes is scoped honestly:

- The Service Layer, domain logic, and MCP/REST adapters are expected to require no changes, or minimal changes, when migrating from SQLite to PostgreSQL.
- The Repository implementation, migration scripts, SQL-dialect-specific behavior (type handling, date/time handling, locking semantics), and connection configuration may require adaptation. SQLite and PostgreSQL are not behaviorally identical, and this document does not claim the migration is purely a configuration change.
- This is mitigated, not eliminated, by adopting an ORM/query builder that supports both engines from v0.1 onward and writing migrations in that tool's format. The specific tool is a technology-selection decision, made separately from this document.

## 8. v0.1 Scope

- SQLite schema covering: Core (users, goals, goal_metrics, audit_logs) and Finance/minimal Business entities needed to answer the success-test questions in spec §32.
- A minimal Repository Layer.
- A minimal Service Layer implementing:
  - the read-only calculations needed for spec §32 (net worth, goal gap, required revenue, etc.) — automatic;
  - local-data write operations (e.g. `add_transaction`, `add_revenue`, `add_expense`, `add_opportunity`) — implemented, but every call passes through the explicit-approval gate described in §6; no write commits without it.
  - no code path for financial execution.
- An MCP server exposing the read-only tools listed in spec §23, plus the approval-gated write tools above.

## 9. What NOT to Build Yet

- No REST API (added only when an actual client requires it).
- No PostgreSQL, no cloud infrastructure.
- No bank/card integration — not even the adapter's implementation, only the interface boundary described conceptually in spec §24.
- No RE:WORD integration — RE:WORD remains an independent project; only an unused placeholder namespace (`modules/learning/reword`) exists in the directory tree.
- No encryption-at-rest mechanism beyond whole-disk encryption (e.g. SQLCipher is a possible future hardening layer, not built now).
- No web UI, no multi-user support, no fully automated review-loop scheduling (spec §25).
- No automatic ("AUTO-tier") writes to personal data — see §6; this is deferred to a future, deliberate policy change.

## 10. Backup Architecture

Primary data location:

```
~/PersonalOS-data/personal_os.db
```

The following are fixed as requirements now. The specific backup implementation mechanism (how a consistent SQLite backup is taken — for example via the SQLite online backup API, `VACUUM INTO`, or a WAL-checkpoint-then-copy sequence — is a technology-selection decision, made later, and is deliberately not fixed by this document. In particular, naively copying the database file while it may be mid-write is not an acceptable implementation, which is why database consistency is listed as an explicit requirement below rather than assumed.)

- A backup mechanism must exist and be verified working before any production (real) personal data is stored in the database.
- Backups must remain outside Git, without exception.
- The backup destination must support encryption; this may be a local encrypted volume or, in the future, an encrypted remote destination. Cloud backup is not implemented in v0.1.
- Backups must be versioned — multiple historical snapshots must be retained, not only the most recent one.
- The restore procedure must be tested, not merely assumed to work.
- The backup implementation must preserve database consistency at the moment of backup.

## Summary

This architecture keeps Claude, ChatGPT, and any future AI client as replaceable front-ends over a single Service Layer that owns all business logic, permission enforcement, and audit logging. The only component aware of the underlying storage engine is the Repository/Data Access Layer, which is what allows SQLite (v0.1) to be replaced by PostgreSQL later without rewriting the rest of the system. No personal data, of any kind, is stored in this Git repository at any point in this architecture.
