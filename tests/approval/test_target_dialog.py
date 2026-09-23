import subprocess
from types import SimpleNamespace

import pytest

from personal_os.approval import _target
from tests.services.test_target_write_contract import financial_request, monthly_request, context


@pytest.mark.parametrize("returncode,output,expected", [(0,"APPROVED\n",True),(0,"DENIED",False),(1,"APPROVED",False),(0,"",False)])
def test_financial_dialog_requires_exact_success(monkeypatch, returncode, output, expected):
    monkeypatch.setattr(_target.sys, "platform", "darwin")
    def run(argv, **kwargs):
        assert argv[:2] == ["/usr/bin/osascript", "-e"]
        assert kwargs["timeout"] == 125
        assert "shell" not in kwargs
        assert len(argv) == 5  # osascript, -e, script, prompt, title
        assert argv[-1] == "Personal OS — local financial target"
        assert 'default button "Cancel"' in argv[2]
        assert '"metric_key": "net_worth_2026_goal"' in argv[-2]
        assert '"amount_minor": 10000000' in argv[-2]
        return SimpleNamespace(returncode=returncode, stdout=output)
    monkeypatch.setattr(_target.subprocess, "run", run)
    assert _target.confirm_financial_target(financial_request(), context()) is expected


@pytest.mark.parametrize("returncode,output,expected", [(0,"APPROVED\n",True),(0,"DENIED",False)])
def test_monthly_dialog_requires_exact_success(monkeypatch, returncode, output, expected):
    monkeypatch.setattr(_target.sys, "platform", "darwin")
    def run(argv, **kwargs):
        assert argv[-1] == "Personal OS — local monthly target"
        assert '"year": 2026' in argv[-2] and '"month": 3' in argv[-2]
        return SimpleNamespace(returncode=returncode, stdout=output)
    monkeypatch.setattr(_target.subprocess, "run", run)
    assert _target.confirm_monthly_target(monthly_request(), context()) is expected


def test_timeout_and_long_content_fail_closed(monkeypatch):
    monkeypatch.setattr(_target.sys, "platform", "darwin")
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("synthetic", 125)
    monkeypatch.setattr(_target.subprocess, "run", timeout)
    assert not _target.confirm_financial_target(financial_request(), context())
    assert not _target.confirm_monthly_target(monthly_request(), context())
    def forbidden(*args, **kwargs):
        pytest.fail("long content should not show a truncated dialog")
    monkeypatch.setattr(_target.subprocess, "run", forbidden)
    assert not _target.confirm_financial_target(financial_request(metric_key="x" * 4000), context())


def test_other_platform_denies(monkeypatch):
    monkeypatch.setattr(_target.sys, "platform", "linux")
    assert not _target.confirm_financial_target(financial_request(), context())
    assert not _target.confirm_monthly_target(monthly_request(), context())


def test_two_dialogs_do_not_share_a_lock_incorrectly(monkeypatch):
    """Sequential calls each acquire and release cleanly (no deadlock from a
    stale lock held by a prior call in the same process)."""
    monkeypatch.setattr(_target.sys, "platform", "darwin")
    monkeypatch.setattr(_target.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="APPROVED"))
    assert _target.confirm_financial_target(financial_request(), context())
    assert _target.confirm_monthly_target(monthly_request(), context())
