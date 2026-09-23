"""Fail-closed macOS dialog approvals for FinancialTarget/MonthlyTarget
version writes (Q4/Q5). Two dedicated dialogs, not a change to
approval/macos.py, matching the pattern already used for Account and batch
import.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading

from personal_os.domain.target_write_contracts import AddFinancialTargetInput, AddMonthlyTargetInput
from personal_os.domain.write_contracts import WriteContext

_LOCK = threading.Lock()
_SCRIPT = '''on run argv
set answer to display dialog (item 1 of argv) with title (item 2 of argv) buttons {"Cancel", "Approve once"} default button "Cancel" cancel button "Cancel" giving up after 120
if gave up of answer then return "DENIED"
if button returned of answer is "Approve once" then return "APPROVED"
return "DENIED"
end run'''


def _confirm(details_payload: dict, tool: str, title: str, banner: str) -> bool:
    if sys.platform != "darwin":
        return False
    details = json.dumps(
        {**details_payload, "tool": tool},
        sort_keys=True, ensure_ascii=True, indent=2,
    )
    if len(details) > 3500:
        return False
    prompt = banner + "\nReview every field. Cancel if unexpected.\n\n" + details
    if not _LOCK.acquire(blocking=False):
        return False
    try:
        completed = subprocess.run(
            ["/usr/bin/osascript", "-e", _SCRIPT, prompt, title],
            capture_output=True, text=True, timeout=125, check=False,
        )
        return completed.returncode == 0 and completed.stdout.strip() == "APPROVED"
    except (OSError, subprocess.TimeoutExpired):
        return False
    finally:
        _LOCK.release()


def confirm_financial_target(request: AddFinancialTargetInput, context: WriteContext) -> bool:
    return _confirm(
        {"financial_target": request.model_dump(mode="json"), "actor": context.actor,
         "reason": context.reason, "model_or_agent": context.model_or_agent, "source": context.source},
        "add_financial_target", "Personal OS — local financial target",
        "Set ONE new version of an overall target (no prior version is deleted).",
    )


def confirm_monthly_target(request: AddMonthlyTargetInput, context: WriteContext) -> bool:
    return _confirm(
        {"monthly_target": request.model_dump(mode="json"), "actor": context.actor,
         "reason": context.reason, "model_or_agent": context.model_or_agent, "source": context.source},
        "add_monthly_target", "Personal OS — local monthly target",
        "Set ONE new version of a monthly target (no prior version is deleted).",
    )
