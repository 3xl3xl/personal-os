# ADR-016: freee Ingestion via freee's Official MCP Server (Supersedes ADR-014 Phase B Plan)

Status: Accepted
Date: 2026-09-23

## Context

ADR-014 built the vendor-neutral core of the freee read-only import
(`RawBankTransaction`, dedup, batch approval, atomic write) as Phase A, and
deliberately deferred Phase B -- a `personal_os.adapters.freee` module doing
its own OAuth token exchange/refresh and raw HTTP calls against freee's
accounting API -- because freee's exact transaction-endpoint JSON field
names could not be confirmed with certainty from public documentation.

Since ADR-014, research found that freee itself publishes an official MCP
server (`freee/freee-mcp`, MIT licensed): OAuth 2.0 + PKCE against the same
freee application already registered ("Personal OS v2"), exposing
HTTP-method-shaped tools (`freee_api_get`, `freee_api_post`, ...) across
freee's accounting, HR, invoicing and other products, plus "Agent Skills"
that inject the correct API reference into the calling AI's context. It can
run as a hosted remote MCP (`https://mcp.freee.co.jp/mcp`) or locally.

PERSONAL_OS_SPEC.md 2.2 (MODEL AGNOSTIC) already states a preference for
"可能な限りMCPなど標準化されたInterfaceを使用する". Building and maintaining
a custom OAuth/HTTP client duplicates work freee already does for its own
MCP server, and re-introduces exactly the "guess an unconfirmed external
JSON shape" risk ADR-014 refused to take.

## Decision

Personal OS will not build the Phase B client described in ADR-014. Instead:

1. freee-mediated data enters Personal OS only through an AI client (this
   session, or the user's local Claude) that has **both** freee's official
   MCP server and Personal OS's own MCP server connected at once.
2. The AI calls freee-mcp to fetch bank/wallet transaction data, using
   freee-mcp's own skill-injected knowledge of freee's real API shape --
   Personal OS never hardcodes or guesses freee's JSON field names.
3. The AI maps freee's response into Personal OS's existing vendor-neutral
   `RawBankTransaction` shape (unchanged from ADR-014) and calls one new
   Personal OS MCP tool, `import_bank_transactions`
   (`adapters/mcp/import_tools.py`, backed by a new
   `services/approved_import_write.py::ApprovedImportWrite`), which runs the
   already-built `stage_import` -> native macOS batch-approval dialog
   (`approval/_batch_import.py::confirm_import_batch`) -> `approve_import`
   pipeline exactly as ADR-014 designed it. None of `import_review.py`,
   `_batch_import.py`, or the `ExternalTransactionLink` schema changes.
4. `import_bank_transactions`'s input contract is exactly the
   `RawBankTransaction` fields (`source`, `external_office_id`,
   `external_account_id`, `external_transaction_id`, `amount_minor`,
   `currency_code`, `occurred_at`, `description`) plus the target Personal
   OS `account_id` per line -- never a freee-shaped payload. This keeps
   Personal OS's own code permanently free of freee-specific JSON knowledge,
   so a future change to freee's API shape needs no change here at all.

## Rationale

- **Why not build the custom client anyway, now that freee-mcp exists as a
  cross-check:** freee-mcp already solves exactly the problem Phase B
  existed to solve (correct, current API calls against freee), and
  duplicating it would mean Personal OS maintaining its own copy of
  freee's API-shape knowledge indefinitely, in addition to OAuth token
  refresh logic freee already handles.
- **Why the AI does the mapping instead of a Phase-B-style Python function:**
  the mapping step is the one place freee's real field names matter. Asking
  the AI to map at call time (using freee-mcp's own injected schema
  knowledge) means Personal OS's own source code never needs to encode
  freee's JSON shape, so it can never drift out of date with freee's API.
- **Why one new MCP tool rather than exposing `stage_import`/
  `confirm_import_batch`/`approve_import` as three separate tools:** an
  AI-mediated batch import is a single logical operation from the human's
  point of view (paste in this month's statement, review, approve/cancel);
  splitting it into three round-trips would let a caller invoke
  `approve_import` against a preview it never actually re-validated,
  reopening exactly the kind of MCP-write trust gap Step 20's audit
  provenance work closed for `add_transaction`.

## Alternatives Considered

- **Keep ADR-014's original Phase B plan (self-built OAuth/HTTP client):**
  rejected for now -- still blocked on confirmed field names, and now
  redundant with freee's own official offering.
- **Personal OS itself acting as an MCP client of freee-mcp** (i.e. Personal
  OS's own server process calls out to freee-mcp directly, with no AI in
  the loop): rejected -- Personal OS is designed as an MCP *server*
  throughout this project (ARCHITECTURE.md's 5-layer model); turning it
  into an MCP client as well is a materially larger architecture change for
  a capability (headless/unattended sync) nobody has asked for yet, and it
  reintroduces the very OAuth-token-lifecycle-management burden this ADR
  avoids by construction.
- **Exposing `stage_import`/`confirm_import_batch`/`approve_import` as three
  separate MCP tools:** rejected -- see Rationale.

## Consequences

- ADR-014's Phase A (Rationale, dedup identity, atomic-write design,
  `RawBankTransaction`, `ExternalTransactionLink`) is unchanged and remains
  the authoritative record for that part of the design; only its stated
  Phase B plan is superseded by this ADR.
- Real freee data can only reach Personal OS while an AI session has both
  MCP servers connected; there is no headless/cron-only sync path today.
  Nothing here prevents adding one later (see Revisit Triggers).
- Personal OS's own source code never contains freee-specific field names,
  endpoint paths, or OAuth logic.
- This work depends on ADR-015 (Local Account Write Contract): a real
  target `account_id` must already exist before any real freee data is
  imported.
- Atomicity remains per-line, not per-batch (unchanged from ADR-014): each
  approved candidate is its own commit, so if one candidate in a batch fails
  validation (e.g. a bad `account_id`), candidates already written earlier
  in the same `import_bank_transactions` call stay committed. The MCP tool
  surfaces this honestly (it never claims nothing was written on a
  mid-batch failure) rather than papering over it with a false
  all-or-nothing guarantee `approve_import` was never built to provide.

## Constraints

- `adapters/mcp/import_tools.py`'s tool signature accepts only
  `RawBankTransaction`-shaped fields and a Personal OS `account_id` -- never
  a freee-specific payload, raw or otherwise.
- `services/approved_import_write.py` imports nothing from `sqlalchemy`,
  `sqlite3`, `personal_os.database`, or `personal_os.adapters`, and does not
  modify `services/import_review.py`, `approval/_batch_import.py`, or
  `services/write_contract.py`.
- No freee credential, OAuth token, or API response is ever stored, logged,
  or handled by this repository's code or CI; freee-mcp's own credential
  handling is entirely outside this repository (ADR-014's Constraints
  already establish this for Phase A).

## Revisit Triggers

- A future need for headless/unattended sync (no AI session mediating each
  import) -- would require reviving a Phase-B-style client of Personal OS's
  own, at which point freee's real field names must be independently
  reconfirmed against a live sandbox response, not assumed from this ADR.
- freee-mcp being deprecated, materially changed, or found unreliable --
  would require reopening this decision.
- A second AUTHORIZED DATA PROVIDER being added that has no equivalent
  official MCP server -- Phase B's original self-built-client approach
  would then apply to that provider specifically, not to freee.
