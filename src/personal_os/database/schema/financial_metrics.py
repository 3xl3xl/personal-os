"""
FinancialMetric persistence model — Finance v0.1 Schema Design
(Decision 3): a lookup table that exists ONLY to support Target-vs-
Actual KPI tracking (Q4, Q5). Confirmed by the user's Step 4 review:
FinancialMetric is a tracked KPI, never a stand-in for revenue source,
business category, or accounting category — those belong to a future,
separate Business domain.

`key` is the natural identifier referenced by transactions.metric_key,
financial_targets.metric_key, and monthly_targets.metric_key. A
separate UUID `id` primary key is kept for ADR-007 consistency
("every table uses a UUID primary key column"); `key` carries its own
UNIQUE constraint and is what the other tables' foreign keys actually
target.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from personal_os.database.schema.base import Base


class FinancialMetric(Base):
    __tablename__ = "financial_metrics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(nullable=False)
