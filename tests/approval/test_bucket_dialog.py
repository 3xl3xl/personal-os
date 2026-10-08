"""The bucket confirmation is fail closed and displays exact immutable input."""
import datetime as dt
import subprocess
import uuid
from types import SimpleNamespace

import pytest

from personal_os.approval import _bucket
from personal_os.domain.bucket_write_contracts import AddCashLinkedAllocationInput
from personal_os.domain.write_contracts import WriteContext


def request():
    return AddCashLinkedAllocationInput(id=uuid.uuid4(), bucket_id=uuid.uuid4(), amount_minor=1000,
        currency_code="JPY", created_at=dt.datetime(2026,10,7,tzinfo=dt.UTC))


def context(reason="synthetic"):
    return WriteContext(actor="synthetic", model_or_agent="synthetic", source="synthetic", reason=reason)


@pytest.mark.parametrize("code,output,expected", [(0,"APPROVED\n",True),(0,"DENIED",False),(1,"APPROVED",False),(0,"",False)])
def test_dialog_exact_success_and_fields(monkeypatch, code, output, expected):
    monkeypatch.setattr(_bucket.sys, "platform", "darwin")
    req = request()
    def run(argv, **kwargs):
        assert str(req.bucket_id) in argv[-1] and str(req.id) in argv[-1]
        assert '"amount_minor": 1000' in argv[-1]
        assert "NEW cash transaction" in argv[-1]
        assert kwargs["timeout"] == 125 and "shell" not in kwargs
        assert 'default button "Cancel"' in argv[2]
        return SimpleNamespace(returncode=code, stdout=output)
    monkeypatch.setattr(_bucket.subprocess, "run", run)
    assert _bucket.confirm_bucket(req, context()) is expected


def test_timeout_platform_busy_and_length_deny(monkeypatch):
    monkeypatch.setattr(_bucket.sys, "platform", "linux")
    assert not _bucket.confirm_bucket(request(), context())
    monkeypatch.setattr(_bucket.sys, "platform", "darwin")
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("synthetic",125)
    monkeypatch.setattr(_bucket.subprocess, "run", timeout)
    assert not _bucket.confirm_bucket(request(), context())
    assert not _bucket.confirm_bucket(request(), context("x" * 4000))
    _bucket._LOCK.acquire()
    try:
        assert not _bucket.confirm_bucket(request(), context())
    finally:
        _bucket._LOCK.release()
