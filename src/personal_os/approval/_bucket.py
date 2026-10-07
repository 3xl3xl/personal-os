"""Fail-closed, request-bound local approval for append-only bucket writes."""
from __future__ import annotations

import json
import subprocess
import sys
import threading

from personal_os.domain.bucket_write_contracts import BucketWriteInput
from personal_os.domain.write_contracts import WriteContext

_LOCK = threading.Lock()
_SCRIPT = '''on run argv
set answer to display dialog (item 1 of argv) with title "Personal OS — local bucket write" buttons {"Cancel", "Approve once"} default button "Cancel" cancel button "Cancel" giving up after 120
if gave up of answer then return "DENIED"
if button returned of answer is "Approve once" then return "APPROVED"
return "DENIED"
end run'''


def confirm_bucket(request: BucketWriteInput, context: WriteContext) -> bool:
    if sys.platform != "darwin":
        return False
    # ASCII escaping prevents embedded line/control/bidi characters from hiding
    # the actual field boundaries. Refuse long content rather than truncate it.
    details = json.dumps({
        "bucket_operation": request.model_dump(mode="json"),
        "actor": context.actor, "reason": context.reason,
        "model_or_agent": context.model_or_agent, "source": context.source,
        "request_type": type(request).__name__,
    }, sort_keys=True, ensure_ascii=True, indent=2)
    if len(details) > 3500:
        return False
    prompt = ("Append local bucket ledger facts. Cash-linked writes ALSO create a NEW cash transaction.\n"
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
