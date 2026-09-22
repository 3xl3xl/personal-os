"""
FinancialTarget persistence model — supports Q4 (Distance from
Financial Target). Column set confirmed by the user's Step 4 review.

Stores a *target definition* only. The corresponding *actual* value is
always derived from other facts (Account balances, bucket allocations,
transactions) at query time — never stored here (Schema Design §10,
Target vs Actual Model: target and actual must never be conflated;
there is deliberately no "actual" column anywhere in this table).

Versioning (confirmed, Step 4 Decision 3): rows are append/version-
only, never overwritten. For a given evaluation_time, the effective
version is:

    SELECT * FROM financial_targets
    WHERE metric_key = :metric_key
      AND effective_from <= :evaluation_time
    ORDER BY effective_from DESC
    LIMIT 1

i.e. the row with MAX(effective_from) among those whose effective_from
is at or before evaluation_time. This selection is a Service-Layer
responsibility, not something this schema module performs itself.
There is no `effective_to` column in v0.1 — a version's end is
implicit (the next version's effective_from), never stored explicitly.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from personal_os.database.schema.base import Base


class FinancialTarget(Base):
    __tablename__ = "financial_targets"
    __table_args__ = (
        CheckConstraint("length(currency_code) = 3", name="ck_financial_targets_currency_code_length"),
        CheckConstraint("currency_code = upper(currency_code)", name="ck_financial_targets_currency_code_upper"),
        UniqueConstraint(
            "metric_key", "effective_from", name="uq_financial_targets_metric_effective_from"
        ),
        Index("ix_financial_targets_metric_key", "metric_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    metric_key: Mapped[str] = mapped_column(ForeignKey("financial_metrics.key"), nullable=False)
    target_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    effective_from: Mapped[dt.datetime] = mapped_column(nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(nullable=False)
