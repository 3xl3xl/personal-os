"""Fail-closed macOS dialog approval for FinancialMetric registration.

A new, dedicated dialog rather than a change to approval/macos.py, matching
the pattern already used for Account (approval/_account.py) and batch
import (approval/_batch_import.py).
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading

from personal_os.domain.metric_write_contracts import AddMetricInput
from personal_os.domain.write_contracts import WriteContext

_LOCK = threading.Lock()
_SCRIPT = '''on run argv
set answer to display dialog (item 1 of argv) with title "Personal OS — local metric" buttons {"Cancel", "Approve once"} default button "Cancel" cancel button "Cancel" giving up after 120
if gave up of answer then return "DENIED"
if button returned of answer is "Approve once" then return "APPROVED"
return "DENIED"
end run'''


def confirm_metric(request: AddMetricInput, context: WriteContext) -> bool:
    if sys.platform != "darwin":
        return False
    details = json.dumps({
        "metric": request.model_dump(mode="json"),
        "actor": context.actor, "reason": context.reason,
        "model_or_agent": context.model_or_agent, "source": context.source,
        "tool": "add_metric",
    }, sort_keys=True, ensure_ascii=True, indent=2)
    if len(details) > 3500:
        return False
    prompt = ("Register ONE local tracked KPI definition (no target value yet).\n"
              "Review every field. Cancel if unexpected.\n\n" + details)
    if not _LOCK.acquire(blocking=False):
        return False
    try:
        completed = subprocess.run(
            ["/usr/bin/osascript", "-e", _SCRIPT, prompt],
            capture_output=True, text=True, timeout=125, check=False,
        )
        return completed.returncode == 0 and completed.stdout.strip() == "APPROVED"
    except (OSError, subprocess.TimeoutExpired):
        return False
    finally:
        _LOCK.release()
