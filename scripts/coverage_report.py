"""Generate a dependency-free line-coverage report for Personal OS.

Step 9 deliberately avoids adding a coverage dependency. Python's stdlib
trace module runs the existing pytest suite and writes annotated source
coverage outside tracked source files.
"""
from __future__ import annotations

import sys
import trace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".coverage-report"


def main() -> int:
    tracer = trace.Trace(
        count=True,
        trace=False,
        ignoredirs=[sys.prefix, str(ROOT / "tests"), str(ROOT / ".venv")],
    )
    exit_code = tracer.runfunc(pytest.main, ["-q"])
    results = tracer.results()
    REPORT_DIR.mkdir(exist_ok=True)
    # Restrict the report to first-party application modules.  The stdlib
    # trace collector sees dependencies imported by pytest too; reporting those
    # makes the output noisy and obscures Personal OS coverage.
    first_party = {
        filename: counts
        for filename, counts in results.counts.items()
        if str(Path(filename).resolve()).startswith(str((ROOT / "src" / "personal_os").resolve()))
    }
    results.counts = first_party
    results.write_results(
        show_missing=True,
        summary=True,
        coverdir=str(REPORT_DIR),
    )
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
