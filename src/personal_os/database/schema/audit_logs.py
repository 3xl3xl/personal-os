"""
AuditLog persistence model — ARCHITECTURE.md §6 / Schema Design §11.

Records AI-initiated write actions and their approval status. This
model only defines storage; no audit service, automatic logging, or
Service-Layer integration is implemented in Step 4 (per explicit
instruction).

`approval_status`'s value set was never confirmed by any prior design
decision (unlike bucket_role, transaction status, etc.), so it is
stored as an unconstrained string rather than an Enum/CHECK-restricted
column — adding a CHECK here would mean inventing values that no
Schema Design or ADR has actually decided on. Flagged in the Step 4
report as an open item for the future Permission/Service Layer work.

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
