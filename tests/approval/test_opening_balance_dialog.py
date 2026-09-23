import subprocess
from types import SimpleNamespace

import pytest

from personal_os.approval import _opening_balance
from tests.services.test_opening_balance_write_contract import request, context


@pytest.mark.parametrize("returncode,output,expected", [(0,"APPROVED\n",True),(0,"DENIED",False),(1,"APPROVED",False),(0,"",False)])
def test_dialog_requires_exact_success(monkeypatch, returncode, output, expected):
    monkeypatch.setattr(_opening_balance.sys, "platform", "darwin")
    def run(argv, **kwargs):
        assert argv[:2] == ["/usr/bin/osascript", "-e"]
        assert kwargs["timeout"] == 125
        assert "shell" not in kwargs
        assert 'default button "Cancel"' in argv[2]
        assert '"amount_minor": 50000000' in argv[-1]
        return SimpleNamespace(returncode=returncode, stdout=output)
    monkeypatch.setattr(_opening_balance.subprocess, "run", run)
    assert _opening_balance.confirm_opening_balance(request(), context()) is expected


def test_timeout_and_long_content_fail_closed(monkeypatch):
    monkeypatch.setattr(_opening_balance.sys, "platform", "darwin")
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("synthetic", 125)
    monkeypatch.setattr(_opening_balance.subprocess, "run", timeout)
    assert not _opening_balance.confirm_opening_balance(request(), context())
    def forbidden(*args, **kwargs):
        pytest.fail("long content should not show a truncated dialog")
    monkeypatch.setattr(_opening_balance.subprocess, "run", forbidden)
    assert not _opening_balance.confirm_opening_balance(request(memo="x" * 4000), context())


def test_other_platform_denies(monkeypatch):
    monkeypatch.setattr(_opening_balance.sys, "platform", "linux")
    assert not _opening_balance.confirm_opening_balance(request(), context())
