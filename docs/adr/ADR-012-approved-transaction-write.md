# ADR-012: Approved NORMAL transaction write

Status: Accepted
Date: 2026-09-23

## Decision

Step 19 introduces only `FinanceWriteContract.add_transaction`, with immutable
vendor-neutral inputs/results in `domain/write_contracts.py` and orchestration
in `services/write_contract.py`. It adds one ACTIVE, single-leg NORMAL ledger
fact. Transfer, opening-balance bootstrap, corrections, voiding, reallocations,
revenue/expense wrappers, goals and opportunities are outside this contract.

This is LOCAL_PERSONAL_DATA_WRITE, never FINANCIAL_EXECUTION. The central
permission boundary receives an explicit strict boolean and runs before opening
any UoW. An omitted approval defaults to false. False rejects the operation with
no Transaction or AuditLog mutation. The caller provides actor and reason as
nonblank strings. Trusted composition must obtain approval for the exact write;
an AI-generated approval argument is not itself evidence of user approval.

The contract accepts a UoW factory typed by a Service-facing Protocol. Concrete
UoW/session composition remains outside Service. Successful execution is:

`permission -> reference/currency checks -> Transaction.add -> AuditLog.add -> commit`

Both adds share one fresh transaction and there is exactly one explicit commit.
Exceptions before successful commit, including constraint/commit rejection,
propagate through the UoW context and roll back both inserts. Existing unrelated
rows remain unchanged; "zero rows on failure" means zero new rows from that
attempt. No result construction or serialization is deferred until after commit.
As with any database, a lost acknowledgement after a durable commit is not proof
of rollback; callers must inspect the supplied transaction ID before retrying an
uncertain outcome. No retry loop or compensation deletion is introduced.

## Contract and validation

`AddTransactionInput` requires UUID `id` and `account_id`, exact `Money`, and an
aware `occurred_at` normalized to UTC. Optional `metric_key` and `memo` preserve
stored fact semantics. Unknown fields are forbidden. Kind and status are fixed
to NORMAL and ACTIVE; correction/transfer identifiers remain null. No balance,
bucket allocation or derived metric is written. Positive, zero and negative
integer amounts retain their exact values and explicit currency.

The account must exist, its currency must match, any supplied metric must exist,
and the transaction ID must be unused. IDs are caller-supplied to detect repeated
attempts; duplicate IDs are rejected rather than silently adding another row.
This is not a full idempotent response-replay framework. No new closed-account or
historical-date policy is invented here. SQLite's existing integer capacity and
constraints remain in effect; an out-of-range integer must fail without mutation,
not be converted to float.

`WriteContext` is separate from the financial fact and includes `actor`, `reason`,
and `approved`. Audit occurrence time and audit UUID are generated through
injected defaults (`utc_now`, UUID4), allowing deterministic synthetic tests.
Malformed context/input and clock failures precede DB mutation. Core permission,
reference, currency and persistence errors propagate; an eventual external
adapter must sanitize infrastructure errors and must call this Service contract,
never Repository/ORM directly. The existing runtime MCP entrypoint stays read-only
in Step 19; exposing a trusted human-approval flow is a separate adapter change.

## Audit status and schema gap

The sole execution status defined now is `EXPLICITLY_APPROVED`. This is not the
permission decision `REQUIRE_APPROVAL`, which describes a gate, not a successful
write. The existing string column remains unchanged; no migration or new approval
framework is added.

All existing audit payload fields are populated as follows (plus its UUID `id`):

| Field | Value |
| --- | --- |
| actor | supplied actor |
| action | `add_transaction` |
| affected_entity_type | `transaction` |
| affected_entity_id | written transaction UUID |
| old_value | null |
| new_value | canonical JSON of the complete written TransactionRecord |
| reason | supplied reason |
| approval_status | `EXPLICITLY_APPROVED` |
| occurred_at | aware UTC audit time |

Spec §22 additionally requires `model_or_agent`, `tool`, and `source`. These are
an explicit outstanding Audit schema revision: Step 4's existing schema has no
such fields. Step 19 neither adds them nor infers/embeds them in reason, actor,
or the financial fact. §22 is not claimed to be fully implemented.

Canonical JSON sorts keys, uses compact separators, retains explicit nulls,
represents enum values and UUIDs as strings, preserves Unicode and integer minor
units, and normalizes timestamps to UTC `Z` with six fractional digits. It has no
clock/UUID generation internally; the same fact always produces the same bytes.

## Verification

Synthetic fake/Protocol tests verify strict approval, permission-before-UoW,
ordering, one commit, metadata, deterministic serialization, money precision,
reference and currency checks, and rollback behavior. SQLite integration uses
the canonical temporary fixture and Alembic head, with concrete composition only
in tests. It exercises post-INSERT failures, actual FK/NOT NULL/unique violations,
commit rejection and fresh-session verification. No private runtime DB is opened
or seeded. Schema, migrations, Finance calculations and repositories are unchanged.
