# Personal OS

Personal OS is a long-term, model-agnostic personal operating system — a private, portable foundation for organizing and acting on your own data, usable by any AI client rather than tied to one vendor or tool.

## Core principles

- **Model-agnostic**: Personal OS is not designed around any single AI. It is not Claude-specific or ChatGPT-specific — any AI client can serve as an interface into it.
- **You own the data**: All personal data governed by Personal OS stays under your control, in your own storage. It is never locked into a vendor's platform.
- **AI clients are replaceable**: Claude, ChatGPT, and any future AI client are interchangeable front-ends. None of them is the source of truth for this system.

## Status

**Step 20 — locally approved MCP writes and audit provenance** is implemented.
The default MCP runtime exposes five read tools. `--enable-writes` adds only
`add_transaction`, requiring local macOS confirmation for every write.

Audit records now support `model_or_agent`, `tool`, and `source`. Migration keeps
unknown historical values NULL; new writes supply all three. See
[ADR-013](docs/adr/ADR-013-mcp-write-and-audit-provenance.md) for startup, backup,
approval, and the distinction between database initialization and personal seed.

Tests use synthetic data and temporary SQLite. Run them with `uv run pytest -q`.

## Source of truth

Detailed specifications live in [`PERSONAL_OS_SPEC.md`](./PERSONAL_OS_SPEC.md). That document — not this README — is the source of truth for architecture and design decisions.

See [`SECURITY.md`](./SECURITY.md) for the security and data-handling policy.
