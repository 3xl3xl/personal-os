"""Verifies transfer_group_id representability and target versioning fields."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from personal_os.database.schema import (
    Account,
    Base,
    FinancialMetric,
    FinancialTarget,
    MonthlyTarget,
    Transaction,
)
from personal_os.domain.enums import AccountType, TransactionKind


def _engine_with_schema():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_transfer_group_id_column_exists_and_is_nullable() -> None:
    col = Base.metadata.tables["transactions"].columns["transfer_group_id"]
    assert col.nullable is True


def test_transfer_legs_are_representable_as_transaction_rows() -> None:
    engine = _engine_with_schema()
    with Session(engine) as session:
        account_a = Account(
            name="Checking", account_type=AccountType.CASH, currency_code="USD",
            opened_at=dt.datetime.now(dt.timezone.utc), status="ACTIVE",
        )
        account_b = Account(
            name="Savings", account_type=AccountType.CASH, currency_code="USD",
            opened_at=dt.datetime.now(dt.timezone.utc), status="ACTIVE",
        )
        session.add_all([account_a, account_b])
        session.flush()

        transfer_group_id = uuid.uuid4()
        leg_out = Transaction(
            account_id=account_a.id, transaction_type=TransactionKind.TRANSFER,
            amount_minor=-5000, currency_code="USD",
            occurred_at=dt.datetime.now(dt.timezone.utc),
            transfer_group_id=transfer_group_id,
        )
        leg_in = Transaction(
            account_id=account_b.id, transaction_type=TransactionKind.TRANSFER,
            amount_minor=5000, currency_code="USD",
            occurred_at=dt.datetime.now(dt.timezone.utc),
            transfer_group_id=transfer_group_id,
        )
        session.add_all([leg_out, leg_in])
        session.commit()  # schema itself does not verify sum(legs)==0; Service Layer will

        legs = (
            session.query(Transaction)
            .filter(Transaction.transfer_group_id == transfer_group_id)
            .all()
        )
        assert len(legs) == 2
    engine.dispose()


def test_financial_target_has_effective_from_versioning_field() -> None:
    table = Base.metadata.tables["financial_targets"]
    assert "effective_from" in table.columns
    assert table.columns["effective_from"].nullable is False


def test_monthly_target_has_effective_from_versioning_field() -> None:
    table = Base.metadata.tables["monthly_targets"]
    assert "effective_from" in table.columns
    assert table.columns["effective_from"].nullable is False


def test_financial_target_does_not_conflate_target_and_actual() -> None:
    # FinancialTarget only stores a target definition -- no "actual" column
    # exists anywhere in this table; actuals are always derived elsewhere.
    table = Base.metadata.tables["financial_targets"]
    assert "target_amount_minor" in table.columns
    assert not any("actual" in name.lower() for name in table.columns.keys())


def test_multiple_versions_of_a_monthly_target_are_representable() -> None:
    engine = _engine_with_schema()
    with Session(engine) as session:
        metric = FinancialMetric(
            key="SELF_GENERATED_REVENUE", display_name="Self-generated revenue",
            created_at=dt.datetime.now(dt.timezone.utc),
        )
        session.add(metric)
        session.flush()

        v1 = MonthlyTarget(
            metric_key=metric.key, year=2027, month=1,
            target_amount_minor=100000, currency_code="JPY",
            effective_from=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
            created_at=dt.datetime.now(dt.timezone.utc),
        )
        v2 = MonthlyTarget(
            metric_key=metric.key, year=2027, month=1,
            target_amount_minor=150000, currency_code="JPY",
            effective_from=dt.datetime(2026, 6, 1, tzinfo=dt.timezone.utc),
            created_at=dt.datetime.now(dt.timezone.utc),
        )
        session.add_all([v1, v2])
        session.commit()  # must not raise: different effective_from -> different version

        count = (
            session.query(MonthlyTarget)
            .filter(MonthlyTarget.metric_key == metric.key)
            .count()
        )
        assert count == 2
    engine.dispose()
