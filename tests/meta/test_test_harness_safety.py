"""Step 9 test-harness safety checks.

These checks guard the test suite itself. They intentionally use generic
credential signatures and repository/runtime boundaries rather than any
real user's Personal Data.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]
TEST_ROOT = REPO_ROOT / "tests"

# Generic credential formats only. Never place real credentials in this list.
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
)


def _test_sources() -> list[Path]:
    return sorted(TEST_ROOT.rglob("*.py"))


def test_test_suite_contains_no_private_runtime_database_path():
    private_dir = "Personal" + "OS-data"
    forbidden = ("~/" + private_dir, private_dir + "/personal_os.db")
    for path in _test_sources():
        text = path.read_text()
        assert not any(value in text for value in forbidden), path


def test_test_suite_contains_no_obvious_live_credentials():
    for path in _test_sources():
        text = path.read_text()
        for pattern in SECRET_PATTERNS:
            assert pattern.search(text) is None, (path, pattern.pattern)


def test_test_suite_has_no_committed_database_artifacts():
    artifacts = [
        path
        for path in REPO_ROOT.rglob("*")
        if path.is_file()
        and (
            path.suffix in {".db", ".sqlite", ".sqlite3"}
            or ".sqlite-" in path.name
        )
        and ".venv" not in path.parts
        and "_to_delete" not in path.parts
    ]
    assert artifacts == []
