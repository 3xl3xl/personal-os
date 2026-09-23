"""Fail-closed macOS dialog approval for an OPENING_BALANCE transaction.

A new, dedicated dialog rather than a change to approval/macos.py --
confirm_transaction and its existing tests (Step 19/20) are left untouched,
matching the same pattern already used for approval/_account.py.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading

from personal_os.domain.opening_balance_write_contracts import AddOpeningBalanceInput
from personal_os.domain.write_contracts import WriteContext

_LOCK = threading.Lock()
_SCRIPT = '''on run argv
set answer to display dialog (item 1 of argv) with title "Personal OS — local opening balance" buttons {"Cancel", "Approve once"} default button "Cancel" cancel button "Cancel" giving up after 120
if gave up of answer then return "DENIED"
if button returned of answer is "Approve once" then return "APPROVED"
return "DENIED"
end run'''


def confirm_opening_balance(request: AddOpeningBalanceInput, context: WriteContext) -> bool:
    if sys.platform != "darwin":
        return False
    # ASCII escaping prevents embedded line/control/bidi characters from hiding
    # the actual field boundaries. Refuse long content rather than truncate it.
    details = json.dumps({
        "opening_balance": request.model_dump(mode="json"),
        "actor": context.actor, "reason": context.reason,
        "model_or_agent": context.model_or_agent, "source": context.source,
        "tool": "add_opening_balance",
    }, sort_keys=True, ensure_ascii=True, indent=2)
    if len(details) > 3500:
        return False
    prompt = ("Create ONE local OPENING_BALANCE transaction (bootstraps an\n"
              "account's starting balance; no bank/broker link, no funds move).\n"
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
