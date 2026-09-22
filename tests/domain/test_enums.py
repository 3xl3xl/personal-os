"""Tests for personal_os.domain.enums — verifies v0.1 confirmed value sets only."""

from __future__ import annotations

from personal_os.domain.enums import (
    AccountType,
    BucketRole,
    EntryType,
    TransactionKind,
    TransactionStatus,
)


def test_account_type_v0_1_values() -> None:
    assert {member.value for member in AccountType} == {"CASH", "INVESTMENT", "LIABILITY"}


def test_transaction_kind_v0_1_values() -> None:
    assert {member.value for member in TransactionKind} == {
        "NORMAL",
        "OPENING_BALANCE",
        "TRANSFER",
    }


def test_transaction_status_v0_1_values() -> None:
    assert {member.value for member in TransactionStatus} == {"ACTIVE", "VOIDED"}


def test_bucket_role_v0_1_values_are_exactly_general_and_tax_reserve() -> None:
    """
    Per Finance v0.1 Schema Design v0.3's "Final correction — semantic
    bucket role" and the user's explicit confirmation for this step:
    v0.1 has exactly these two values. No speculative future roles
    (e.g. EMERGENCY_RESERVE) exist yet.
    """
    assert {member.value for member in BucketRole} == {"GENERAL", "TAX_RESERVE"}


def test_entry_type_v0_1_values() -> None:
    assert {member.value for member in EntryType} == {"CASH_LINKED", "REALLOCATION"}
