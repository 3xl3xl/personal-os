"""
AuditLog repository -- Repository Layer access to the `audit_logs`
table (append-only; PERSONAL_OS_SPEC.md Sec.22).

No update/delete method: an audit log entry is append-only by nature.
This Step implements only the plain read/write path; no audit
service, automatic logging, or Service-Layer integration exists yet
(same scope note as Step 4's schema module).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from personal_os.database.schema import AuditLog
from personal_os.domain.records import AuditLogRecord
from personal_os.repository._datetime_adapter import from_storage, to_storage


class AuditLogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: AuditLogRecord) -> None:
        row = AuditLog(
            id=record.id,
            actor=record.actor,
            action=record.action,
            affected_entity_type=record.affected_entity_type,
            affected_entity_id=record.affected_entity_id,
            old_value=record.old_value,
            new_value=record.new_value,
            reason=record.reason,
            approval_status=record.approval_status,
            occurred_at=to_storage(record.occurred_at),
            model_or_agent=record.model_or_agent, tool=record.tool, source=record.source,
        )
        self._session.add(row)
        self._session.flush()

    def list_all(self) -> list[AuditLogRecord]:
        stmt = select(AuditLog).order_by(AuditLog.occurred_at)
        rows = self._session.execute(stmt).scalars().all()
        return [_to_record(row) for row in rows]


def _to_record(row: AuditLog) -> AuditLogRecord:
    return AuditLogRecord(
        id=row.id,
        actor=row.actor,
        action=row.action,
        affected_entity_type=row.affected_entity_type,
        approval_status=row.approval_status,
        occurred_at=from_storage(row.occurred_at),
        affected_entity_id=row.affected_entity_id,
        old_value=row.old_value,
        new_value=row.new_value,
        reason=row.reason,
        model_or_agent=row.model_or_agent, tool=row.tool, source=row.source,
    )
