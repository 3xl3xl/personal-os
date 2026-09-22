"""Verifies money/currency column typing and enforcement per ADR-005."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import BigInteger, CheckConstraint, Float, Numeric, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from personal_os.database.schema import Account, Base
from personal_os.domain.enums import AccountType

MONEY_COLUMNS = [
    ("transactions", "amount_minor"),
    ("bucket_allocations", "amount_minor"),
    ("financial_targets", "target_amount_minor"),
    ("monthly_targets", "target_amount_minor"),
]

CURRENCY_COLUMN_TABLES = [
    "accounts",
    "transactions",
    "bucket_allocations",
    "financial_targets",
    "monthly_targets",
]


def test_money_columns_are_integer_typed_not_float_or_numeric() -> None:
    for table_name, column_name in MONEY_COLUMNS:
        col = Base.metadata.tables[table_name].columns[column_name]
        assert isinstance(col.type, BigInteger), (
            f"{table_name}.{column_name} must be BigInteger (integer minor units), "
            f"got {type(col.type).__name__}"
        )
        assert not isinstance(col.type, (Float, Numeric))


def test_currency_code_columns_are_required() -> None:
    for table_name in CURRENCY_COLUMN_TABLES:
        col = Base.metadata.tables[table_name].columns["currency_code"]
        assert col.nullable is False


def test_currency_code_columns_have_length_and_uppercase_check_constraints() -> None:
    for table_name in CURRENCY_COLUMN_TABLES:
        table = Base.metadata.tables[table_name]
        check_texts = [
            str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)
        ]
        assert any("length(currency_code)" in text for text in check_texts), table_name
        assert any("upper(currency_code)" in text for text in check_texts), table_name


def test_currency_code_check_constraint_is_enforced_on_insert() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        bad_account = Account(
            name="Bad",
            account_type=AccountType.CASH,
            currency_code="usd",  # lowercase -- violates the upper() CHECK
            opened_at=dt.datetime.now(dt.timezone.utc),
            status="ACTIVE",
        )
        session.add(bad_account)
        raised = False
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raised = True
        assert raised, "lowercase currency_code should violate the CHECK constraint"
    engine.dispose()
