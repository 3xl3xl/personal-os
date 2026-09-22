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
    results.write_results(
        show_missing=True,
        summary=True,
        coverdir=str(REPORT_DIR),
    )
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
