# Personal OS

Personal OS is a long-term, model-agnostic personal operating system — a private, portable foundation for organizing and acting on your own data, usable by any AI client rather than tied to one vendor or tool.

## Core principles

- **Model-agnostic**: Personal OS is not designed around any single AI. It is not Claude-specific or ChatGPT-specific — any AI client can serve as an interface into it.
- **You own the data**: All personal data governed by Personal OS stays under your control, in your own storage. It is never locked into a vendor's platform.
- **AI clients are replaceable**: Claude, ChatGPT, and any future AI client are interchangeable front-ends. None of them is the source of truth for this system.

## Status

**Step 19 — approved local transaction write** adds a vendor-neutral Service
contract for one NORMAL ledger fact and its atomic audit record. Core Finance,
repositories, migrations, backup/restore, and the read-only runtime MCP entrypoint
are implemented. See [ADR-012](docs/adr/ADR-012-approved-transaction-write.md) for
approval, composition, scope, and the outstanding Audit schema fields.

The runtime MCP tool surface remains read-only. Step 19 tests use synthetic data
and temporary SQLite only; this change does not seed personal data.

Run the regression suite with `uv run pytest -q`.

## Source of truth

Detailed specifications live in [`PERSONAL_OS_SPEC.md`](./PERSONAL_OS_SPEC.md). That document — not this README — is the source of truth for architecture and design decisions.

See [`SECURITY.md`](./SECURITY.md) for the security and data-handling policy.
