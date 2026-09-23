import subprocess
from types import SimpleNamespace

import pytest

from personal_os.approval import _batch_import as batch_import
from personal_os.domain.external_facts import ImportCandidate, ImportDisposition
from personal_os.domain.ids import new_id
from tests.services.test_import_review import ACCOUNT_ID, raw


def _candidates(n=1, disposition=ImportDisposition.NEW):
    return [ImportCandidate(new_id(), raw(external_transaction_id=f"line-{i}"), ACCOUNT_ID, disposition) for i in range(n)]


def test_other_platform_denies_without_calling_subprocess(monkeypatch):
    monkeypatch.setattr(batch_import.sys, "platform", "linux")

    def forbidden(*a, **k):
        pytest.fail("must not invoke osascript on a non-darwin platform")

    monkeypatch.setattr(batch_import.subprocess, "run", forbidden)
    assert batch_import.confirm_import_batch(_candidates()) == set()


def test_no_approvable_candidates_denies_without_calling_subprocess(monkeypatch):
    monkeypatch.setattr(batch_import.sys, "platform", "darwin")

    def forbidden(*a, **k):
        pytest.fail("must not invoke osascript with nothing approvable")

    monkeypatch.setattr(batch_import.subprocess, "run", forbidden)
    unchanged = _candidates(3, ImportDisposition.ALREADY_IMPORTED_UNCHANGED)
    assert batch_import.confirm_import_batch(unchanged) == set()


def test_batch_over_max_size_denies_without_calling_subprocess(monkeypatch):
    monkeypatch.setattr(batch_import.sys, "platform", "darwin")

    def forbidden(*a, **k):
        pytest.fail("must not invoke osascript over the documented batch size cap")

    monkeypatch.setattr(batch_import.subprocess, "run", forbidden)
    too_many = _candidates(batch_import._MAX_CANDIDATES + 1)
    assert batch_import.confirm_import_batch(too_many) == set()


def test_selected_subset_maps_back_to_exact_candidate_ids(monkeypatch):
    monkeypatch.setattr(batch_import.sys, "platform", "darwin")
    candidates = _candidates(3)

    def run(argv, **kwargs):
        assert argv[:2] == ["/usr/bin/osascript", "-e"]
        assert kwargs["timeout"] == 300
        assert "shell" not in kwargs
        labels = argv[3:]
        assert len(labels) == 3
        # Approve only the first and third rendered rows.
        return SimpleNamespace(returncode=0, stdout=f"{labels[0]}\n{labels[2]}")

    monkeypatch.setattr(batch_import.subprocess, "run", run)
    approved = batch_import.confirm_import_batch(candidates)
    assert approved == {candidates[0].candidate_id, candidates[2].candidate_id}


def test_cancelled_dialog_denies(monkeypatch):
    monkeypatch.setattr(batch_import.sys, "platform", "darwin")
    monkeypatch.setattr(batch_import.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=""))
    assert batch_import.confirm_import_batch(_candidates(2)) == set()


def test_nonzero_returncode_denies(monkeypatch):
    monkeypatch.setattr(batch_import.sys, "platform", "darwin")
    monkeypatch.setattr(batch_import.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout="anything"))
    assert batch_import.confirm_import_batch(_candidates(2)) == set()


def test_timeout_denies(monkeypatch):
    monkeypatch.setattr(batch_import.sys, "platform", "darwin")

    def timeout(*a, **k):
        raise subprocess.TimeoutExpired("synthetic", 300)

    monkeypatch.setattr(batch_import.subprocess, "run", timeout)
    assert batch_import.confirm_import_batch(_candidates(2)) == set()


def test_concurrent_confirmation_in_progress_denies(monkeypatch):
    monkeypatch.setattr(batch_import.sys, "platform", "darwin")

    def forbidden(*a, **k):
        pytest.fail("must not invoke osascript while another confirmation holds the lock")

    monkeypatch.setattr(batch_import.subprocess, "run", forbidden)
    assert batch_import._LOCK.acquire(blocking=False)
    try:
        assert batch_import.confirm_import_batch(_candidates()) == set()
    finally:
        batch_import._LOCK.release()


def test_unrecognized_returned_line_is_ignored_not_mapped(monkeypatch):
    monkeypatch.setattr(batch_import.sys, "platform", "darwin")
    candidates = _candidates(1)
    monkeypatch.setattr(
        batch_import.subprocess, "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="some unrelated line that was never offered"),
    )
    assert batch_import.confirm_import_batch(candidates) == set()
