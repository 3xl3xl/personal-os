"""
Step 6, item 6 -- SQLAlchemy ORM objects must never leak out of the
Repository Layer's public API.

For every repository, a write followed by a read must hand back a
personal_os.domain.records.* dataclass -- never an instance of
personal_os.database.schema.Base (the SQLAlchemy declarative base) or
any of its subclasses.
"""

from __future__ import annotations

import ast
import inspect

from personal_os.database.schema import Base
from personal_os.domain.datetime import utc_now
from personal_os.domain.enums import AccountStatus, AccountType
from personal_os.domain.ids import new_id
from personal_os.domain.records import AccountRecord
from personal_os.repository.accounts import AccountRepository

_REPOSITORY_MODULE_NAMES = (
    "accounts",
    "audit_logs",
    "bucket_allocations",
    "capital_buckets",
    "financial_metrics",
    "financial_targets",
    "monthly_targets",
    "transactions",
)


def test_account_repository_returns_a_record_never_an_orm_instance(session_factory):
    session = session_factory()
    try:
        repo = AccountRepository(session)
        record = AccountRecord(
            id=new_id(),
            name="Test Account",
            account_type=AccountType.CASH,
            currency_code="JPY",
            opened_at=utc_now(),
            status=AccountStatus.ACTIVE,
        )
        repo.add(record)
        session.commit()

        got = repo.get(record.id)
        assert isinstance(got, AccountRecord)
        assert not isinstance(got, Base)

        listed = repo.list_all()
        assert all(isinstance(item, AccountRecord) for item in listed)
        assert all(not isinstance(item, Base) for item in listed)
    finally:
        session.close()


def test_no_repository_module_returns_a_bare_orm_row_or_row_list():
    """Static safety net covering all eight repositories at once: every
    "return" of a query result in these modules must be wrapped by a
    record-conversion call (_to_record(...), or a comprehension over
    it) -- never a bare "return row" / "return rows" that would hand
    back a raw SQLAlchemy ORM instance.
    """
    for name in _REPOSITORY_MODULE_NAMES:
        module = __import__(f"personal_os.repository.{name}", fromlist=["_marker"])
        source = inspect.getsource(module)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Name):
                if node.value.id in {"row", "rows"}:
                    raise AssertionError(
                        f"{name}.py returns a bare '{node.value.id}' -- expected it "
                        "to be wrapped by a record-conversion call"
                    )
