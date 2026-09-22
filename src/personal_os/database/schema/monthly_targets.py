"""
MonthlyTarget persistence model — supports Q5 (Monthly Target vs
Actual). Column set confirmed by the user's Step 4 review.

Stores a *target definition* for a specific (metric_key, year, month);
the *actual* value is always derived from transactions at query time
(Schema Design §2, Q5: Actual(metric_key, month) = Σ transaction.amount
WHERE ...). `year`/`month` are plain integers, not a date column —
deciding which month "now" falls into is a timezone-sensitive
determination that belongs to the Service Layer at evaluation time
(ADR-006: local-time evaluation only at the point of business-rule
evaluation), not to this schema.

`year` intentionally has no arbitrary range CHECK (e.g. no
2000–2100-style bound) — confirmed, Step 4 Decision 4. `month` keeps
its 1–12 CHECK, since that range is a structural fact about what a
month is, not an arbitrary business assumption.

Versioning (confirmed, Step 4 Decision 3, applied identically here):
rows are append/version-only, never overwritten. For a given
evaluation_time, the effective version for a (metric_key, year, month)
is the row with MAX(effective_from) among those whose effective_from
is at or before evaluation_time — a Service-Layer responsibility, not
performed by this schema module. There is no `effective_to` column.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from personal_os.database.schema.base import Base


class MonthlyTarget(Base):
    __tablename__ = "monthly_targets"
    __table_args__ = (
        CheckConstraint("length(currency_code) = 3", name="ck_monthly_targets_currency_code_length"),
        CheckConstraint("currency_code = upper(currency_code)", name="ck_monthly_targets_currency_code_upper"),
        CheckConstraint("month >= 1 AND month <= 12", name="ck_monthly_targets_month_range"),
        UniqueConstraint(
            "metric_key", "year", "month", "effective_from",
            name="uq_monthly_targets_metric_year_month_effective_from",
        ),
        Index("ix_monthly_targets_metric_key", "metric_key"),
        Index("ix_monthly_targets_year_month", "year", "month"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    metric_key: Mapped[str] = mapped_column(ForeignKey("financial_metrics.key"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    target_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    effective_from: Mapped[dt.datetime] = mapped_column(nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(nullable=False)
