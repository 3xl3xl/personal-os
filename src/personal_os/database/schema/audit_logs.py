"""
AuditLog persistence model — ARCHITECTURE.md §6 / Schema Design §11.

Records write actions and approval status. Step 19's service records
EXPLICITLY_APPROVED; the column remains a string for historical compatibility.
Step 20 adds nullable model_or_agent/tool/source for historical records whose
provenance was not captured. New writes require those fields at the Service
boundary rather than inventing provenance for old rows.

`affected_entity_type` + `affected_entity_id` intentionally carry no
foreign key: an audit log entry may reference any entity type in the
system (Account, Transaction, CapitalBucket, ...), so this is a
deliberately loose, polymorphic reference rather than a typed FK to
one specific table.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from personal_os.database.schema.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    affected_entity_type: Mapped[str] = mapped_column(String, nullable=False)
    affected_entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_status: Mapped[str] = mapped_column(String, nullable=False)
    occurred_at: Mapped[dt.datetime] = mapped_column(nullable=False)

    # Nullable only for historical records whose provenance was not recorded.
    model_or_agent: Mapped[str | None] = mapped_column(String, nullable=True)
    tool: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
