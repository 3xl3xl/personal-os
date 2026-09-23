import subprocess
from types import SimpleNamespace

import pytest

from personal_os.approval import _metric
from tests.services.test_metric_write_contract import request, context


@pytest.mark.parametrize("returncode,output,expected", [(0,"APPROVED\n",True),(0,"DENIED",False),(1,"APPROVED",False),(0,"",False)])
def test_dialog_requires_exact_success(monkeypatch, returncode, output, expected):
    monkeypatch.setattr(_metric.sys, "platform", "darwin")
    def run(argv, **kwargs):
        assert argv[:2] == ["/usr/bin/osascript", "-e"]
        assert kwargs["timeout"] == 125
        assert "shell" not in kwargs
        assert len(argv) == 4  # osascript, -e, script, prompt (title is baked into the script)
        assert 'default button "Cancel"' in argv[2]
        assert '"key": "net_worth_2026_goal"' in argv[-1]
        return SimpleNamespace(returncode=returncode, stdout=output)
    monkeypatch.setattr(_metric.subprocess, "run", run)
    assert _metric.confirm_metric(request(), context()) is expected


def test_ascii_escapes_non_ascii_field_content(monkeypatch):
    monkeypatch.setattr(_metric.sys, "platform", "darwin")
    def run(argv, **kwargs):
        assert "\\u30e8" in argv[-1]  # ヨ (ASCII-escaped, never raw non-ASCII)
        return SimpleNamespace(returncode=0, stdout="APPROVED")
    monkeypatch.setattr(_metric.subprocess, "run", run)
    assert _metric.confirm_metric(request(), context())


def test_timeout_and_long_content_fail_closed(monkeypatch):
    monkeypatch.setattr(_metric.sys, "platform", "darwin")
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("synthetic", 125)
    monkeypatch.setattr(_metric.subprocess, "run", timeout)
    assert not _metric.confirm_metric(request(), context())
    def forbidden(*args, **kwargs):
        pytest.fail("long content should not show a truncated dialog")
    monkeypatch.setattr(_metric.subprocess, "run", forbidden)
    assert not _metric.confirm_metric(request(display_name="x" * 4000), context())


def test_other_platform_denies(monkeypatch):
    monkeypatch.setattr(_metric.sys, "platform", "linux")
    assert not _metric.confirm_metric(request(), context())
