# ADR-019 — Approved append-only CapitalBucket and allocation writes

Status: Accepted

## Context

Q2/Q3 reads exist, but the MCP cannot create their source facts. Synthetic
verification must use approved writes, not direct database seeding. §22 requires
request-bound human approval, audit provenance, and practical reversibility.

## Decision

Add three opt-in write tools, using a parallel service/domain/approval module:

- `add_capital_bucket`: create an ACTIVE bucket on an ACTIVE CASH account.
  Its name, role, protection and creation time are immutable in this scope.
- `add_cash_linked_allocation`: create a **new NORMAL transaction** and its full
  signed allocation together. This changes Q1 and may change Q2/Q3. It does not
  allocate a previously recorded transaction or opening balance. Never use it
  for an already imported/recorded cash movement. Existing unallocated cash
  remains unsupported; do not manufacture another transaction to fill that gap.
- `reallocate_capital`: append two opposite signed legs under one operation /
  reallocation group ID, between distinct ACTIVE buckets on the same CASH account.
  No cash movement. Protected buckets require the same explicit approval; their
  protection excludes them from Q2, not from all approved relabeling operations.

Currency must exactly match the account. Integer amounts fit signed 64-bit
storage and permit negation; floats/bools, naive timestamps, zero cash writes,
nonpositive reallocation amounts, missing/inactive references, cross-account
moves and writes predating the bucket/account are rejected. No additional
nonnegative-balance rule is invented for the existing signed ledger.

Each operation uses one UOW and one commit for all facts and one audit receipt.
A receipt's canonical JSON includes every input field; entity IDs are completely
recoverable: bucket ID = operation ID; cash allocation ID = operation ID,
transaction ID = UUIDv5(operation ID, `transaction`); reallocation leg IDs =
UUIDv5(operation ID, `debit`/`credit`). Audit ID = UUIDv5(operation ID, tool +
`:audit`). Each request is revalidated at the approval and write boundaries.
Actor/model/source are bound by runtime, never accepted from MCP arguments.
Audit time uses the trusted clock; effective fact time is the approved request.

Approval is required before any UOW, including retries. Cancel, timeout, another
platform, busy dialog or anything other than literal True writes nothing.
Exact retries compare the receipt's payload, tool and provenance including
reason, then return the original audit ID without another mutation. Changed
requests/provenance under that tool's operation ID are rejected. Primary keys
on generated entity and receipt IDs enforce safety for concurrent retries;
a racing loser may fail and must retry the exact request after checking outcome.
No receipt is committed without its facts, including when commit fails.
No schema migration or weakening of existing constraints is required.

## Reversibility and limits

History is never updated/deleted. Reverse a reallocation using a new operation
ID, swapped buckets and an explanatory reason referencing the earlier ID.
Reverse a mistaken NEW cash-linked write with a new opposite signed cash-linked
write and an explanatory reason. These preserve original and compensating facts,
not erase historical as-of values. Arbitrary transaction correction/void,
bucket metadata edits/archive and allocation of pre-existing transactions are
out of scope. An empty wrongly named bucket remains recorded; do not repurpose
its role/protection silently. Report these limits rather than direct DB writes.

## Verification

Synthetic-only tests exercise public account and bucket write contracts, real
Alembic temporary SQLite, MCP translation, exact local approval, atomic rollback
after flush/second leg/commit, stable retries, constraint rejection, provenance,
signed compensation, as-of Q1/Q2/Q3 and unchanged net worth on reallocations.
The native macOS dialog and a real Desktop MCP session remain manual checks.
