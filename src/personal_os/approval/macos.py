"""Fail-closed macOS dialog approval. Never invoke a shell with financial data."""
from __future__ import annotations

import json
import subprocess
import sys
import threading

from personal_os.domain.write_contracts import AddTransactionInput, WriteContext

_LOCK = threading.Lock()
_SCRIPT = '''on run argv
set answer to display dialog (item 1 of argv) with title "Personal OS — local transaction" buttons {"Cancel", "Approve once"} default button "Cancel" cancel button "Cancel" giving up after 120
if gave up of answer then return "DENIED"
if button returned of answer is "Approve once" then return "APPROVED"
return "DENIED"
end run'''


def confirm_transaction(request: AddTransactionInput, context: WriteContext) -> bool:
    if sys.platform != "darwin":
        return False
    # ASCII escaping prevents embedded line/control/bidi characters from hiding
    # the actual field boundaries. Refuse long content rather than truncate it.
    details = json.dumps({
        "transaction": request.model_dump(mode="json"),
        "actor": context.actor, "reason": context.reason,
        "model_or_agent": context.model_or_agent, "source": context.source,
        "tool": "add_transaction",
    }, sort_keys=True, ensure_ascii=True, indent=2)
    if len(details) > 3500:
        return False
    prompt = "Record ONE local finance fact (no bank transfer).\nAmount is in integer MINOR units.\nReview every field. Cancel if unexpected.\n\n" + details
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
