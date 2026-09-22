# ADR-003: MCP Adapter Implementation

Status: Accepted
Date: 2026-09-22

## Context

Personal OS must remain usable by Claude, ChatGPT, and future AI clients on equal footing (PERSONAL_OS_SPEC.md §2.2: model-agnostic). Personal OS Core (the Service Layer and Repository Layer) must not depend on any single AI vendor's SDK or tooling.

## Decision

Use an MCP protocol-compatible adapter (implemented via the official MCP Python SDK) as one interface into Personal OS's Service Layer. This adapter is a thin protocol-translation layer only, and it lives exclusively in the Adapter layer — never inside Core.

## Rationale

- MCP is a protocol standard, not an AI-vendor integration. Claude currently speaks it natively, but nothing about the protocol itself ties Personal OS to Claude specifically.
- A Python-native MCP SDK keeps the adapter in the same language/runtime as the rest of the system (see ADR-001), avoiding cross-process/cross-language complexity between the adapter and the Service Layer.
- Keeping the adapter thin (translation only, no business logic) means a second adapter (REST, or a different future protocol) can be added later without touching the Service Layer or Repository Layer.

## Alternatives Considered

- **Embedding MCP handling logic directly alongside business logic**: rejected — this would tie Core to MCP-specific data shapes and make adding a REST adapter (e.g. for ChatGPT or another client) significantly harder later.
- **Building a REST API first, before any MCP adapter**: rejected for v0.1 — MCP serves the immediate, demonstrated need (Claude's native tool-calling), and a REST adapter is deferred until an actual client requires it (ARCHITECTURE.md §9).

## Consequences

- Adding a second adapter (REST, or a different protocol) later requires no changes to the Service Layer or Repository Layer — only a new, similarly thin adapter module.
- Personal OS Core has zero import dependency on any AI vendor's SDK.

## Constraints

- MCP is treated as a vendor-neutral protocol adapter, not a Claude-specific integration.
- Personal OS Core does not import the SDK of Claude, ChatGPT, or any future AI client.
- Any MCP SDK dependency exists only within the Adapter layer.

## Revisit Triggers

- MCP ceasing to be a viable, actively maintained cross-vendor standard.
- A future AI client requiring an adapter shape that MCP cannot reasonably express, necessitating a materially different adapter design.
- A breaking change in the MCP SDK that conflicts with the thin-adapter principle above.
