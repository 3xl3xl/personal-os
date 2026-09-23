"""Fail-closed macOS batch-review dialog for external import candidates.

ADR-014 (freee read-only integration), point 2: a human reviews the full
candidate list and selects which lines to approve; an empty selection or
Cancel approves nothing. Separate module from personal_os/approval/macos.py
(the existing single-transaction dialog) so that file -- already built,
tested, and merged in Step 19/20 -- is not touched by this addition.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import uuid

from personal_os.domain.external_facts import ImportCandidate, ImportDisposition

_LOCK = threading.Lock()
_MAX_CANDIDATES = 200
_SCRIPT = '''on run argv
set theResult to choose from list argv with title "Personal OS — import review" with prompt "Select statement lines to record as local facts. Cmd/Shift-click for multiple. Cancel or an empty selection saves nothing." with multiple selections allowed
if theResult is false then return ""
set AppleScript's text item delimiters to linefeed
return theResult as text
end run'''


def _label(index: int, candidate: ImportCandidate) -> str:
    details = json.dumps(
        {
            "amount_minor": candidate.raw.amount.amount_minor,
            "currency_code": candidate.raw.amount.currency_code,
            "occurred_at": candidate.raw.occurred_at.isoformat(),
            "description": candidate.raw.description,
            "external_transaction_id": candidate.raw.external_transaction_id,
            "disposition": candidate.disposition.value,
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    # A numeric prefix guarantees uniqueness even if two rows render
    # identically, since AppleScript list items are matched by string value.
    return f"{index + 1}. {details}"


def confirm_import_batch(candidates: list[ImportCandidate]) -> set[uuid.UUID]:
    """Show the batch dialog; return exactly the approved candidate_ids.

    Returns an empty set (approves nothing) when: not on macOS, there are
    no approvable candidates, the batch exceeds _MAX_CANDIDATES (reviewing
    an unbounded list in one dialog is refused rather than truncated
    silently), the dialog is cancelled, or another confirmation is already
    in progress (fail-closed, same lock discipline as the single-
    transaction dialog in personal_os/approval/macos.py).
    """
    if sys.platform != "darwin":
        return set()
    approvable = [
        c for c in candidates if c.disposition is not ImportDisposition.ALREADY_IMPORTED_UNCHANGED
    ]
    if not approvable or len(approvable) > _MAX_CANDIDATES:
        return set()

    labels = [_label(i, c) for i, c in enumerate(approvable)]
    label_to_id = {label: c.candidate_id for label, c in zip(labels, approvable)}

    if not _LOCK.acquire(blocking=False):
        return set()
    try:
        completed = subprocess.run(
            ["/usr/bin/osascript", "-e", _SCRIPT, *labels],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    finally:
        _LOCK.release()

    if completed.returncode != 0:
        return set()
    selected = completed.stdout.strip()
    if not selected:
        return set()
    return {
        label_to_id[line]
        for line in selected.split("\n")
        if line in label_to_id
    }
