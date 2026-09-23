"""Thin launcher for the Personal OS MCP server.

This file is the only thing bundled into the .mcpb extension. It intentionally
contains no Personal OS application code, dependencies, or data -- it just
execs into the user's own personal-os git checkout via `uv`, so the extension
always runs whatever code is currently checked out there (no stale copy
baked into the extension that would need rebuilding after every `git pull`).

Absolute paths are used throughout (both here and in manifest.json's
mcp_config.command) because Claude Desktop launches extensions with a
minimal PATH that does not include a login shell's PATH additions (e.g.
~/.local/bin, where `uv` is commonly installed) -- a bare "uv" lookup via
PATH search fails silently as a disconnected server with no traceback.

PERSONAL_OS_REPO is derived from the home directory rather than hardcoded,
so this file does not embed the local macOS username. It resolves to
~/personal-os for whichever user runs this launcher. UV_CANDIDATES is
checked in order; the first one that exists is used, so this keeps working
if uv is reinstalled to a different one of these common locations without
editing this file.
"""
import os
import sys

PERSONAL_OS_REPO = os.path.expanduser("~/personal-os")

UV_CANDIDATES = [
    os.path.expanduser("~/.local/bin/uv"),
    "/opt/homebrew/bin/uv",
    "/usr/local/bin/uv",
    os.path.expanduser("~/.cargo/bin/uv"),
]

if not os.path.isdir(PERSONAL_OS_REPO):
    sys.stderr.write(
        f"personal-os checkout not found at {PERSONAL_OS_REPO}. "
        "Edit PERSONAL_OS_REPO in this launcher if the repo moved.\n"
    )
    raise SystemExit(1)

uv_path = next((p for p in UV_CANDIDATES if os.path.isfile(p)), None)
if uv_path is None:
    sys.stderr.write(
        "Could not find a `uv` executable in any known location: "
        + ", ".join(UV_CANDIDATES)
        + ". Run `which uv` in a terminal and add that path to UV_CANDIDATES "
        "in this launcher.\n"
    )
    raise SystemExit(1)

os.execv(
    uv_path,
    [
        uv_path, "--directory", PERSONAL_OS_REPO,
        "run", "python", "-m", "personal_os.adapters.mcp.runtime_server",
        "--enable-writes",
    ],
)
