"""
Money value object for Personal OS v0.1.

Source of truth: ADR-005 (Money Representation) and Finance v0.1
Schema Design §6 (Money & Currency Semantics).

Rules enforced here:
- Binary float is never accepted as an amount, anywhere — including
  via implicit bool-as-int coercion. Python treats bool as a subclass
  of int; this module rejects bool explicitly rather than silently
  treating True/False as 1/0.
- Stored representation is always a signed integer count of minor
  units (e.g. cents) — never a float, never a Decimal at rest.
- currency_code is required on every Money value and is validated as
  an uppercase 3-letter code. This is a *format* check only — it does
  NOT validate against the real ISO 4217 currency registry, and it
  does NOT assume JPY (or any other single currency). Whether to add
  full registry validation, and with what data source, is an
  explicitly deferred decision for a later step.
- A lowercase or mixed-case currency code is rejected outright, not
  silently normalized to uppercase — this is a deliberate design
  choice (see test_lowercase_currency_is_rejected_not_normalized).
- Money is immutable (frozen dataclass).
- Arithmetic (+, -) is defined only between Money values of the same
  currency_code. Cross-currency arithmetic raises
  CurrencyMismatchError — Personal OS never silently aggregates
  across currencies (per Finance v0.1 Schema Design §6).
- Equality compares both amount_minor and currency_code (the frozen
  dataclass's generated __eq__ does this already).

No global rounding default exists anywhere in this module, and this
module intentionally does not implement multiplication, division,
percentage, or allocation. Those are business/tax-rule-specific
operations, and ADR-005 requires each one to declare its own explicit,
testable rounding rule at its own call site. The boundary this module
offers such future operations is simply the raw `amount_minor`
integer: any operation that needs Decimal precision is expected to
build its own Decimal from that integer, apply its own explicit
rounding rule, and construct a new Money from the resulting integer
minor units — converting a float into a Decimal as a workaround is
not an acceptable substitute for that.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CURRENCY_CODE_PATTERN = re.compile(r"^[A-Z]{3}$")


class MoneyValidationError(ValueError):
    """Raised when Money is constructed with an invalid amount or currency_code."""


class CurrencyMismatchError(ValueError):
    """Raised when an operation is attempted between Money values of different currencies."""


@dataclass(frozen=True, slots=True)
class Money:
    """An immutable amount of money in integer minor units of a single currency."""

    amount_minor: int
    currency_code: str

    def __post_init__(self) -> None:
        self._validate_amount(self.amount_minor)
        self._validate_currency_code(self.currency_code)

    @staticmethod
    def _validate_amount(amount_minor: object) -> None:
        if isinstance(amount_minor, bool):
            raise MoneyValidationError(
                f"amount_minor must be int, not bool: {amount_minor!r}"
            )
        if not isinstance(amount_minor, int):
            raise MoneyValidationError(
                "amount_minor must be int (integer minor units); got "
                f"{type(amount_minor).__name__}: {amount_minor!r}. "
                "Binary float is never accepted as a money amount."
            )

    @staticmethod
    def _validate_currency_code(currency_code: object) -> None:
        if not isinstance(currency_code, str):
            raise MoneyValidationError(
                f"currency_code must be str; got {type(currency_code).__name__}: {currency_code!r}"
            )
        if not _CURRENCY_CODE_PATTERN.fullmatch(currency_code):
            raise MoneyValidationError(
                "currency_code must be an uppercase 3-letter code (format check "
                f"only, not a full ISO 4217 registry lookup); got {currency_code!r}. "
                "Lowercase or mixed-case codes are rejected, not normalized."
            )

    def _require_same_currency(self, other: "Money") -> None:
        if not isinstance(other, Money):
            raise TypeError(f"expected Money, got {type(other).__name__}: {other!r}")
        if self.currency_code != other.currency_code:
            raise CurrencyMismatchError(
                f"cannot combine {self.currency_code} with {other.currency_code}"
            )

    def __add__(self, other: "Money") -> "Money":
        self._require_same_currency(other)
        return Money(self.amount_minor + other.amount_minor, self.currency_code)

    def __sub__(self, other: "Money") -> "Money":
        self._require_same_currency(other)
        return Money(self.amount_minor - other.amount_minor, self.currency_code)
