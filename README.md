# Personal OS

Personal OS is a long-term, model-agnostic personal operating system — a private, portable foundation for organizing and acting on your own data, usable by any AI client rather than tied to one vendor or tool.

## Core principles

- **Model-agnostic**: Personal OS is not designed around any single AI. It is not Claude-specific or ChatGPT-specific — any AI client can serve as an interface into it.
- **You own the data**: All personal data governed by Personal OS stays under your control, in your own storage. It is never locked into a vendor's platform.
- **AI clients are replaceable**: Claude, ChatGPT, and any future AI client are interchangeable front-ends. None of them is the source of truth for this system.

## Status

**Local Finance v0.1 reads and approval-gated writes are implemented,
including the follow-ups to Step 20.** This does not mean the full
Personal OS v0.1 specification or real-data onboarding is complete.

### Implemented

The default stdio MCP runtime exposes five read tools:

- `get_net_worth`
- `get_available_capital`
- `get_tax_reserve`
- `get_goal_gap`
- `get_required_revenue`

These implement the Finance Q1–Q5 calculations in
[PERSONAL_OS_SPEC.md §32.1](PERSONAL_OS_SPEC.md).
Tax reserve means existing TAX_RESERVE bucket allocations, not a tax
liability estimate. Required revenue means the remaining current-month
self-generated revenue target, not a long-term forecast.

Starting the runtime with `--enable-writes` additionally exposes:

- `add_account`
- `add_transaction` — a single ACTIVE NORMAL transaction
- `add_opening_balance` — a single ACTIVE OPENING_BALANCE transaction,
  with at most one opening balance per account
- `add_metric`
- `add_financial_target`
- `add_monthly_target`
- `import_bank_transactions`
- `add_capital_bucket`
- `add_cash_linked_allocation` (new transaction + full allocation, atomic)
- `reallocate_capital` (append-only same-account pair)

Writes require request-bound local macOS human confirmation; an
AI-client-supplied approval boolean is not proof of consent. Target writes
append versions rather than modifying existing history. Each individual
fact and its audit record are committed together.

Bank transaction import supports normalized external records, duplicate
review, local batch selection, and audited persistence. “Read-only”
describes access to the external provider: importing still writes to the
local Personal OS database and requires approval. Import atomicity is
**per line, not per batch**; earlier committed lines remain if a later
line fails.

The freee integration uses an AI client connected to both freee's official
MCP server and Personal OS. The client maps provider data into Personal
OS's vendor-neutral import shape. ADR-016 supersedes ADR-014's custom
OAuth/HTTP Phase B plan; Personal OS does not implement that client or
unattended synchronization.

Audit provenance includes `model_or_agent`, `tool`, and `source`.
Unknown historical provenance remains NULL rather than being invented.

Claude Desktop MCPB packaging is available in
[`packaging/mcpb/`](packaging/mcpb/README.md). It is a macOS thin launcher
for the user's local checkout via `uv`, with writes enabled and still
subject to local approval. It does not bundle Personal OS application
code, dependencies, or personal data, and does not change the
model-agnostic architecture.

See:
[ADR-013](docs/adr/ADR-013-mcp-write-and-audit-provenance.md),
[ADR-014](docs/adr/ADR-014-freee-read-integration.md),
[ADR-015](docs/adr/ADR-015-account-write-contract.md),
[ADR-016](docs/adr/ADR-016-freee-mcp-mediated-import.md),
[ADR-017](docs/adr/ADR-017-metric-and-target-write-contracts.md), and
[ADR-018](docs/adr/ADR-018-opening-balance-write-contract.md).

### Not yet implemented / outside the current runtime

The runtime does not expose the full tool list proposed in the
specification. General Goal/Opportunity writes, Account updates or
closure, transaction corrections/voiding/transfers, and CapitalBucket
or allocation writes are not exposed by the current MCP runtime.

The current tool surface also does not provide the full business
pipeline, deal-count calculation, forecasting, or weekly/monthly review
loop described in the specification.

Headless bank synchronization is not implemented. Bank writes, payments,
investment execution, autonomous scheduling, email sending, and a complex
UI remain outside the initial v0.1 scope.

### Next verification

Follow the ordered [live connection verification runbook](docs/LIVE_CONNECTION_VERIFICATION.md)
for commands, acceptance criteria, authentication boundaries, and recovery steps.

Before treating the system as ready for real-data use:

1. Verify a private backup and restore procedure before runtime migration.
   Startup upgrades the selected database to Alembic head; database
   initialization is not proof of a complete personal-data seed.
2. Verify Claude Desktop MCPB build/install/startup against the intended
   checkout and database, including tool registration and real macOS
   approval, cancellation, and timeout behavior.
3. Reconcile an approved Account and opening balance with source records,
   then validate Q1–Q5 using approved transactions, metrics, target
   versions, and the required bucket allocations. Check currency and
   business-timezone boundaries and avoid counting pre-opening activity
   twice.
4. Validate a small freee-mcp-mediated import against source records:
   account mapping, amount/sign, currency, timestamps, duplicate and
   changed-record handling, audit provenance, and partial-failure recovery.
   Provider records must not be treated automatically as self-generated
   revenue without verified metric classification.

Tests use synthetic data and temporary SQLite:

`uv run pytest -q`

Synthetic tests and committed packaging sources do not establish that
live freee ingestion, Desktop installation, or a complete private
financial profile has been verified.

## Source of truth

Detailed specifications live in [`PERSONAL_OS_SPEC.md`](./PERSONAL_OS_SPEC.md). That document — not this README — is the source of truth for architecture and design decisions.

See [`SECURITY.md`](./SECURITY.md) for the security and data-handling policy.

Bucket writes follow [ADR-019](docs/adr/ADR-019-capital-bucket-write-contract.md).
Cash-linked allocation creates a NEW transaction; it must not be used to allocate
existing opening balances/imported transactions. Synthetic Q2/Q3 verification is
documented in [the verification procedure](docs/LIVE_CONNECTION_VERIFICATION.md#33-q2q3を合成データだけで検証する).
