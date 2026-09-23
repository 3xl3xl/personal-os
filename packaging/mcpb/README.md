# Personal OS MCPB packaging

Source for the `.mcpb` Claude Desktop extension that launches the local
Personal OS MCP server (`--enable-writes`).

This is a thin launcher only: `server/launch.py` execs
`uv --directory <repo> run python -m personal_os.adapters.mcp.runtime_server --enable-writes`
against the checkout at the hardcoded `PERSONAL_OS_REPO` path. No Personal OS
application code, dependencies, or personal data are bundled into the
extension itself.

## Rebuilding after changes here

```sh
npm install -g @anthropic-ai/mcpb   # once
cd packaging/mcpb
mcpb validate manifest.json
mcpb pack . ../../personal-os.mcpb
```

Reinstall the resulting `.mcpb` in Claude Desktop (Settings > Extensions >
Advanced settings > Install Extension..., or drag-and-drop) after rebuilding.
You do NOT need to rebuild after ordinary Personal OS source changes --
only if this packaging directory itself changes (e.g. the repo moves and
`PERSONAL_OS_REPO` needs updating).
