"""Tests for personal_os.domain.money — see ADR-005 and Finance v0.1 Schema Design §6."""

from __future__ import annotations

import dataclasses

import pytest

from personal_os.domain.money import CurrencyMismatchError, Money, MoneyValidationError


def test_same_currency_addition() -> None:
    a = Money(1000, "USD")
    b = Money(250, "USD")
    assert a + b == Money(1250, "USD")


def test_same_currency_subtraction() -> None:
    a = Money(1000, "USD")
    b = Money(250, "USD")
    assert a - b == Money(750, "USD")


def test_cross_currency_addition_rejected() -> None:
    a = Money(1000, "USD")
    b = Money(1000, "JPY")
    with pytest.raises(CurrencyMismatchError):
        a + b


def test_cross_currency_subtraction_rejected() -> None:
    a = Money(1000, "USD")
    b = Money(1000, "JPY")
    with pytest.raises(CurrencyMismatchError):
        a - b


def test_float_amount_rejected() -> None:
    with pytest.raises(MoneyValidationError):
        Money(10.5, "USD")  # type: ignore[arg-type]


def test_bool_amount_rejected() -> None:
    with pytest.raises(MoneyValidationError):
        Money(True, "USD")  # type: ignore[arg-type]
    with pytest.raises(MoneyValidationError):
        Money(False, "JPY")  # type: ignore[arg-type]


def test_invalid_currency_rejected() -> None:
    with pytest.raises(MoneyValidationError):
        Money(1000, "US")
    with pytest.raises(MoneyValidationError):
        Money(1000, "USDD")
    with pytest.raises(MoneyValidationError):
        Money(1000, "US1")


def test_lowercase_currency_is_rejected_not_normalized() -> None:
    """
    Explicit v0.1 design decision: a lowercase or mixed-case currency
    code is rejected outright, not silently uppercased. Callers must
    supply an already-uppercase 3-letter code.
    """
    with pytest.raises(MoneyValidationError):
        Money(1000, "usd")
    with pytest.raises(MoneyValidationError):
        Money(1000, "Usd")


def test_immutability() -> None:
    m = Money(1000, "USD")
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.amount_minor = 2000  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.currency_code = "JPY"  # type: ignore[misc]


def test_equality() -> None:
    assert Money(1000, "USD") == Money(1000, "USD")
    assert Money(1000, "USD") != Money(1000, "JPY")
    assert Money(1000, "USD") != Money(999, "USD")


def test_amount_minor_can_be_negative_and_zero() -> None:
    # Signed ledger entries (bucket_allocations legs, transfer legs)
    # require negative amounts; zero is a valid, if unusual, amount.
    assert Money(-500, "USD").amount_minor == -500
    assert Money(0, "JPY").amount_minor == 0
