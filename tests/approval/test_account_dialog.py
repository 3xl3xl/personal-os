import subprocess
from types import SimpleNamespace

import pytest

from personal_os.approval import _account
from tests.services.test_account_write_contract import request, context


@pytest.mark.parametrize("returncode,output,expected", [(0,"APPROVED\n",True),(0,"DENIED",False),(1,"APPROVED",False),(0,"",False)])
def test_dialog_requires_exact_success(monkeypatch, returncode, output, expected):
    monkeypatch.setattr(_account.sys, "platform", "darwin")
    def run(argv, **kwargs):
        assert argv[:2] == ["/usr/bin/osascript", "-e"]
        assert kwargs["timeout"] == 125
        assert "shell" not in kwargs
        assert 'default button "Cancel"' in argv[2]
        assert '"currency_code": "JPY"' in argv[-1]
        assert "\\u666e" in argv[-1]  # 普 (ASCII-escaped, never raw non-ASCII)
        return SimpleNamespace(returncode=returncode, stdout=output)
    monkeypatch.setattr(_account.subprocess, "run", run)
    assert _account.confirm_account(request(), context()) is expected


def test_timeout_and_long_content_fail_closed(monkeypatch):
    monkeypatch.setattr(_account.sys, "platform", "darwin")
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("synthetic", 125)
    monkeypatch.setattr(_account.subprocess, "run", timeout)
    assert not _account.confirm_account(request(), context())
    def forbidden(*args, **kwargs):
        pytest.fail("long content should not show a truncated dialog")
    monkeypatch.setattr(_account.subprocess, "run", forbidden)
    assert not _account.confirm_account(request(name="x" * 4000), context())


def test_other_platform_denies(monkeypatch):
    monkeypatch.setattr(_account.sys, "platform", "linux")
    assert not _account.confirm_account(request(), context())
