"""
Domain enums for Personal OS v0.1.

Every enum here corresponds to a value set explicitly confirmed in
Finance v0.1 Schema Design v0.3 (and, for AccountType, that same
document's `accounts` table). No enum values are added speculatively
ahead of an actual confirmed need — see each enum's docstring for the
part of the Schema Design it comes from.
"""

from __future__ import annotations

from enum import StrEnum


class AccountType(StrEnum):
    """accounts.account_type — Finance v0.1 Schema Design §5.1."""

    CASH = "CASH"
    INVESTMENT = "INVESTMENT"
    LIABILITY = "LIABILITY"


class TransactionKind(StrEnum):
    """
    transactions.transaction_type — Finance v0.1 Schema Design §5.2.

    NORMAL: an ordinary transaction.
    OPENING_BALANCE: synthetic transaction used to bootstrap a
        pre-existing account balance (see Balance Strategy, §7).
    TRANSFER: one leg of an account-to-account transfer, sharing a
        transfer_group_id with its counterpart leg (Decision 2,
        Transfer atomicity).
    """

    NORMAL = "NORMAL"
    OPENING_BALANCE = "OPENING_BALANCE"
    TRANSFER = "TRANSFER"


class TransactionStatus(StrEnum):
    """
    transactions.status — Finance v0.1 Schema Design §5.2 / §11 (Audit Strategy).

    Ledger entries are append-only: corrections are made via a new row
    referencing correction_of, or by marking the original VOIDED —
    never by update or delete.
    """

    ACTIVE = "ACTIVE"
    VOIDED = "VOIDED"


class BucketRole(StrEnum):
    """
    capital_buckets.bucket_role — Finance v0.1 Schema Design v0.3,
    "Final correction — semantic bucket role".

    v0.1 defines the minimum two values only. GENERAL covers any bucket
    that does not require role-specific calculation behavior (Europe
    fund, emergency fund, business cash, etc. — display name and
    is_protected carry that meaning instead). TAX_RESERVE is the only
    role with calculation-specific meaning in v0.1: Q3 (Tax Reserved)
    aggregates every bucket with this role, regardless of bucket.name,
    and multiple TAX_RESERVE buckets are allowed and summed together.

    Do not add further roles speculatively — a new role is added only
    once a Schema Design decision gives it actual calculation
    semantics (per the user's explicit instruction for this step).
    """

    GENERAL = "GENERAL"
    TAX_RESERVE = "TAX_RESERVE"


class EntryType(StrEnum):
    """
    bucket_allocations.entry_type — Finance v0.1 Schema Design §5.4
    (Decision 2, Transfer/Reallocation atomicity).

    CASH_LINKED: created alongside a real cash-moving Transaction,
        linked via originating_transaction_id.
    REALLOCATION: pure relabeling between buckets within the same
        account, no cash movement; two legs share a
        reallocation_group_id and sum to zero.
    """

    CASH_LINKED = "CASH_LINKED"
    REALLOCATION = "REALLOCATION"
