# ADR-013: Local human approval for MCP writes and audit provenance

Status: Accepted
Date: 2026-09-23

## Scope

Add only `add_transaction` to an explicitly write-enabled runtime MCP server.
The default runtime remains read-only. No financial execution, seed/import,
transfer, correction, goal write, or public HTTP service is added.

## Approval boundary

The tool has no `approved`, actor, model, or source input. Its adapter constructs
strict `AddTransactionInput` and calls `ApprovedTransactionWrite`. The service
validates an immutable request/context, invokes its injected trusted approval
callback, and passes literal True only after approval to `FinanceWriteContract`.
Each request prompts separately. It stores no reusable approval token and has
no automatic retry. Duplicate IDs remain errors.

The macOS runtime callback displays the full request and audit metadata in a
local OS dialog. Cancel is the default; cancellation, timeout, unavailable GUI,
non-macOS platforms, concurrent prompts, and excessively long content deny the
write. Nothing is truncated into an apparently complete approval. JSON escaping
makes control characters visible. The AppleScript is fixed and data travels as
an argv value, never shell code. The dialog expires at 120 seconds, with a
subprocess timeout of 125 seconds. An LLM-controlled tool argument is never
accepted as proof of human consent. This protects against tool callers, not a
compromised local desktop with permission to automate the OS UI.

The SDK adapter accesses no Repository/ORM. Concrete UoW composition remains in
the runtime root. Invalid input, denied approval, and failures return a structured
`error` object with a fixed code/message; success returns transaction/audit IDs.
Consumers must check `error`, not just protocol transport success. Infrastructure
exception text is never returned. Uncertain commit outcomes must be checked by
transaction ID before any user-approved retry.

## Provenance migration

`audit_provenance_v1` adds nullable `model_or_agent`, `tool`, and `source` columns.
Historical rows retain all their existing payloads and NULL for unknown fields;
no provenance is fabricated. New `WriteContext` requires nonblank model_or_agent
and source, and the Service fixes tool to `add_transaction`.

Runtime values are factual composition metadata: actor is the local OS user,
model_or_agent is `personal-os-mcp` (the executing agent, NOT a claim about the
caller's LLM), source is `mcp:stdio`, and tool is `add_transaction`. They appear in
the human confirmation alongside the fact. Other trusted callers must supply
their own actual provenance. This is an intentional tightening of the internal
write-context API; historical DTO/repository readers remain compatible.

Upgrade is additive and preserves existing rows. Downgrade removes the three
new columns and therefore loses their provenance; it is tested only on synthetic
history here and must not be used as a data-preserving runtime recovery. Keep a
verified private backup before runtime migration. Step 19's atomic Transaction +
AuditLog UoW, exact Money, UTC timestamps and permission class are unchanged.

## Running and verification

From the checkout containing this change:

```sh
uv run python -m personal_os.adapters.mcp.runtime_server --enable-writes
```

Configure the MCP client to launch that command (stdio); this is not an HTTP URL.
Omit `--enable-writes` for the existing five read tools. `--database-path` provides
an explicit alternative path. Startup upgrades the selected database to Alembic
head, so back it up before the first start after a schema change.

Tests cover a real SDK client with synthetic SQLite, successful and denied writes,
spoofed approval/provenance, exact money input, sanitized errors, all three persisted
provenance fields, historical migration preservation/downgrade, dialog cancellation
and timeout, and a real stdio child registering the sixth tool. OS dialog decisions
are mocked; tests never ask for or perform a real personal-data write.

## Seed verification boundary

Runtime seed status is checked using read-only SQLite and existence checks on the
Finance tables, without reading/displaying personal values. An empty database is
not seeded. Mere presence of rows is not proof that a full personal profile is
complete; that requires a user-defined inventory and private source data. No seed
status or personal contents are committed as project data, and no personal values
are inferred from conversation or tests.
