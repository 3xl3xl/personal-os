"""Step 17 local-private runtime composition tests."""
from __future__ import annotations

import os
import stat
import subprocess
import sys

from sqlalchemy import inspect, text

from personal_os.runtime import initialize_runtime, sqlite_url

EXPECTED_TABLES={
    "accounts","audit_logs","financial_metrics","capital_buckets",
    "financial_targets","monthly_targets","transactions","bucket_allocations",
    "external_transaction_links","alembic_version",
}


def test_import_has_no_runtime_database_side_effect(tmp_path):
    fake_home=tmp_path/"home"
    fake_home.mkdir()
    code="import personal_os.runtime"
    result=subprocess.run(
        [sys.executable,"-c",code],
        env={**os.environ,"HOME":str(fake_home)},
        capture_output=True,text=True,
    )
    assert result.returncode==0,result.stderr
    assert not (fake_home/"PersonalOS-data").exists()


def test_explicit_runtime_initializes_and_migrates_explicit_temp_path(tmp_path):
    path=tmp_path/"private"/"personal_os.db"
    runtime=initialize_runtime(path)
    try:
        assert runtime.database_path==path.resolve()
        assert path.is_file()
        assert EXPECTED_TABLES==set(inspect(runtime.engine).get_table_names())
        with runtime.engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one()==1
            assert connection.execute(text("PRAGMA integrity_check")).scalar_one()=="ok"
    finally:
        runtime.engine.dispose()


def test_runtime_storage_permissions_are_private(tmp_path):
    path=tmp_path/"private"/"personal_os.db"
    runtime=initialize_runtime(path)
    runtime.engine.dispose()
    assert stat.S_IMODE(path.parent.stat().st_mode)==0o700
    assert stat.S_IMODE(path.stat().st_mode)==0o600


def test_runtime_reasserts_private_permissions_for_existing_storage(tmp_path):
    directory=tmp_path/"private"
    directory.mkdir(mode=0o755)
    path=directory/"personal_os.db"
    path.touch(mode=0o644)
    initialize_runtime(path).engine.dispose()
    assert stat.S_IMODE(directory.stat().st_mode)==0o700
    assert stat.S_IMODE(path.stat().st_mode)==0o600


def test_runtime_session_factory_is_usable(tmp_path):
    runtime=initialize_runtime(tmp_path/"personal_os.db")
    try:
        with runtime.session_factory() as session:
            assert session.execute(text("SELECT 1")).scalar_one()==1
    finally:
        runtime.engine.dispose()


def test_sqlite_url_is_explicit_and_absolute(tmp_path):
    path=tmp_path/"x.db"
    assert sqlite_url(path)==f"sqlite:///{path.resolve()}"
